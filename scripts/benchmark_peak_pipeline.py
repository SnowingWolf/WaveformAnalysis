#!/usr/bin/env python3
"""Benchmark the peak pipeline with isolated repeats and reproducible golden hashes."""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import math
import os
from pathlib import Path
import statistics
import subprocess
import sys
import tempfile
import threading
import time
from typing import Any
import warnings

import numpy as np
import psutil

PIPELINE_TARGETS = (
    "peaklet_components",
    "peaklets",
    "peaklet_waveforms",
    "peaklet_waveform_pool",
    "peaklet_features",
    "peaklet_channels",
    "peaks",
)
DIRECT_PIPELINE_TARGETS = (
    "peaklet_components",
    "peaklets",
    "peaklet_waveforms",
    "peaklet_features",
)
COMPUTE_IMPROVEMENT_THRESHOLDS = {
    "peaklet_components": 0.20,
    "peaklets": 0.40,
    "peaklet_waveforms": 0.25,
    "peaklet_features": 0.30,
}
END_TO_END_IMPROVEMENT_THRESHOLD = 0.30
MAX_RANGE_OVER_MEDIAN = 0.10
HASH_CHUNK_BYTES = 64 * 1024 * 1024
RSS_SAMPLE_INTERVAL_SEC = 0.1


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, str | int | bool):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else repr(value)
    if isinstance(value, np.generic):
        return _json_safe(value.item())
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list | tuple | set):
        return [_json_safe(item) for item in value]
    if isinstance(value, np.ndarray):
        return value.tolist()
    return repr(value)


def load_config(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("--config-json must contain a JSON object")
    for wrapper in ("custom_config", "config"):
        wrapped = payload.get(wrapper)
        if isinstance(wrapped, dict):
            return wrapped.copy()
    return payload.copy()


def _dtype_from_json(value: Any) -> np.dtype:
    if isinstance(value, list):
        fields = []
        for item in value:
            if not isinstance(item, list):
                fields.append(item)
            elif len(item) == 3 and isinstance(item[2], list):
                fields.append((item[0], item[1], tuple(item[2])))
            else:
                fields.append(tuple(item))
        return np.dtype(fields)
    return np.dtype(value)


def load_direct_manifest(path: str | Path) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    """Load fixed upstream arrays as read-only memmaps from a manifest."""
    manifest_path = Path(path).resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("direct manifest must contain a JSON object")
    cache_root_value = manifest.get("cache_root")
    stems = manifest.get("stems")
    if not cache_root_value or not isinstance(stems, dict) or not stems:
        raise ValueError("direct manifest requires cache_root and a non-empty stems mapping")

    cache_root = Path(cache_root_value)
    if not cache_root.is_absolute():
        cache_root = manifest_path.parent / cache_root
    arrays: dict[str, np.ndarray] = {}
    for name, raw_spec in stems.items():
        spec = {"stem": raw_spec} if isinstance(raw_spec, str) else dict(raw_spec)
        stem = spec.get("stem", name)
        default_path = stem if Path(stem).suffix else f"{stem}.bin"
        data_path = Path(spec.get("path", default_path))
        if not data_path.is_absolute():
            data_path = cache_root / data_path
        if data_path.suffix == ".npy":
            arrays[name] = np.load(data_path, mmap_mode="r", allow_pickle=False)
            continue

        metadata_path = Path(spec.get("metadata", f"{stem}.json"))
        if not metadata_path.is_absolute():
            metadata_path = cache_root / metadata_path
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        dtype_value = spec.get("dtype_descr", spec.get("dtype"))
        if dtype_value is None:
            dtype_value = metadata.get("dtype_descr", metadata.get("dtype"))
        if dtype_value is None:
            raise ValueError(f"direct manifest stem {name!r} is missing dtype metadata")
        shape = spec.get("shape", metadata.get("shape"))
        if shape is None:
            shape = [metadata["count"]]
        arrays[name] = np.memmap(
            data_path,
            dtype=_dtype_from_json(dtype_value),
            mode="r",
            shape=tuple(shape),
        )
    return arrays, manifest.get("config", {})


class DirectCacheContext:
    """Minimal Context surface for deterministic direct plugin benchmarks."""

    def __init__(
        self,
        data: dict[str, np.ndarray],
        config: dict[str, Any] | None = None,
        output_dir: str | Path | None = None,
    ):
        from waveform_analysis.core.plugins.builtin.peaks.peaklets import (
            PeakletComponentsPlugin,
            PeakletFeaturesPlugin,
            PeakletPlugin,
            PeakletWaveformPlugin,
        )

        self.config = config or {}
        self._data = data
        self._results: dict[tuple[str, str], np.ndarray] = {}
        self._plugins = {
            "peaklet_components": PeakletComponentsPlugin(),
            "peaklets": PeakletPlugin(),
            "peaklet_waveforms": PeakletWaveformPlugin(),
            "peaklet_features": PeakletFeaturesPlugin(),
        }
        self.output_dir = Path(output_dir) if output_dir is not None else None

    def get_config(self, plugin: Any, name: str) -> Any:
        nested = self.config.get(plugin.provides)
        if isinstance(nested, dict) and name in nested:
            return nested[name]
        namespaced = f"{plugin.provides}.{name}"
        if namespaced in self.config:
            return self.config[namespaced]
        if name in self.config:
            return self.config[name]
        return plugin.options[name].default

    def get_data(self, run_id: str, name: str, **_kwargs: Any) -> np.ndarray:
        cached = self._results.get((run_id, name))
        if cached is not None:
            return cached
        if name in self._data:
            return self._data[name]
        if name == "peaklet_waveform_pool":
            self.get_data(run_id, "peaklet_waveforms")
            return self._results[(run_id, name)]
        plugin = self._plugins.get(name)
        if plugin is None:
            raise KeyError(f"direct manifest is missing required upstream {name!r}")
        result = plugin.compute(self, run_id)
        if (run_id, name) not in self._results:
            self._set_data(run_id, name, result)
        return result

    def _get_data_from_memory(self, run_id: str, name: str) -> np.ndarray | None:
        return self._results.get((run_id, name))

    def _set_data(self, run_id: str, name: str, value: np.ndarray) -> None:
        self._results[(run_id, name)] = value
        if self.output_dir is None:
            return
        self.output_dir.mkdir(parents=True, exist_ok=True)
        if value.size == 0:
            np.save(self.output_dir / f"{name}.npy", value, allow_pickle=False)
            return
        output = np.lib.format.open_memmap(
            self.output_dir / f"{name}.npy", mode="w+", dtype=value.dtype, shape=value.shape
        )
        output[...] = value
        output.flush()


def _register_peak_pipeline(ctx: Any) -> None:
    from waveform_analysis.core.plugins.plugin_sets import (
        plugins_hit,
        plugins_io,
        plugins_peaks,
        plugins_waveform,
    )

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        ctx.register(*plugins_io(), *plugins_waveform(), *plugins_hit(), *plugins_peaks())


def build_context(storage_dir: str | Path, config: dict[str, Any]) -> Any:
    from waveform_analysis.core.context import Context

    ctx = Context(storage_dir=str(storage_dir), config=config.copy(), stats_mode="off")
    _register_peak_pipeline(ctx)
    return ctx


def _process_tree_rss(process: psutil.Process) -> int:
    total = 0
    processes = [process]
    try:
        processes.extend(process.children(recursive=True))
    except (psutil.Error, OSError):
        pass
    for item in processes:
        try:
            total += int(item.memory_info().rss)
        except (psutil.Error, OSError):
            continue
    return total


class PeakRssSampler:
    """Sample current-process and child-process RSS at a fixed interval."""

    def __init__(self, interval_sec: float = RSS_SAMPLE_INTERVAL_SEC):
        self.interval_sec = interval_sec
        self.process = psutil.Process(os.getpid())
        self.baseline_bytes = 0
        self.peak_bytes = 0
        self.samples = 0
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def _sample(self) -> None:
        value = _process_tree_rss(self.process)
        self.peak_bytes = max(self.peak_bytes, value)
        self.samples += 1

    def _run(self) -> None:
        while not self._stop.wait(self.interval_sec):
            self._sample()

    def __enter__(self) -> PeakRssSampler:
        self.baseline_bytes = _process_tree_rss(self.process)
        self.peak_bytes = self.baseline_bytes
        self.samples = 1
        self._thread = threading.Thread(target=self._run, name="peak-rss-sampler", daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *_exc_info: object) -> None:
        self._sample()
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=max(1.0, self.interval_sec * 2.0))

    def to_dict(self) -> dict[str, int | float]:
        return {
            "sample_interval_sec": self.interval_sec,
            "sample_count": self.samples,
            "baseline_bytes": self.baseline_bytes,
            "peak_bytes": self.peak_bytes,
            "incremental_peak_bytes": max(0, self.peak_bytes - self.baseline_bytes),
        }


def chunked_hash(array: np.ndarray, chunk_bytes: int = HASH_CHUNK_BYTES) -> dict[str, Any]:
    """Hash a numeric ndarray in bounded row chunks without materializing a full copy."""
    if not isinstance(array, np.ndarray):
        raise TypeError("golden hashing requires a numpy array")
    if array.dtype.hasobject:
        raise TypeError("golden hashing does not support object dtype arrays")
    if chunk_bytes <= 0:
        raise ValueError("chunk_bytes must be positive")

    rows = int(array.shape[0]) if array.ndim else 1
    bytes_per_row = max(1, int(array.nbytes // max(1, rows)))
    rows_per_chunk = max(1, chunk_bytes // bytes_per_row)
    chunk_hashes: list[str] = []
    whole = hashlib.sha256()

    flat_rows = array.reshape((rows,) + array.shape[1:]) if array.ndim else array.reshape(1)
    for start in range(0, rows, rows_per_chunk):
        raw = np.ascontiguousarray(flat_rows[start : start + rows_per_chunk]).view(np.uint8)
        digest = hashlib.sha256(raw).hexdigest()
        chunk_hashes.append(digest)
        whole.update(raw)

    metadata = {
        "dtype": array.dtype.descr if array.dtype.names else array.dtype.str,
        "shape": list(array.shape),
        "nbytes": int(array.nbytes),
    }
    golden = hashlib.sha256()
    golden.update(json.dumps(metadata, sort_keys=True, default=str).encode("utf-8"))
    for digest in chunk_hashes:
        golden.update(digest.encode("ascii"))
    return {
        **metadata,
        "algorithm": "sha256",
        "chunk_bytes": chunk_bytes,
        "chunk_hashes": chunk_hashes,
        "data_sha256": whole.hexdigest(),
        "golden_sha256": golden.hexdigest(),
    }


def array_summary(value: Any, *, include_hash: bool = True) -> dict[str, Any]:
    if not isinstance(value, np.ndarray):
        raise TypeError(f"peak pipeline target returned non-array output: {type(value).__name__}")
    result = {
        "row_count": int(len(value)) if value.ndim else 1,
        "nbytes": int(value.nbytes),
        "dtype": value.dtype.descr if value.dtype.names else value.dtype.str,
        "shape": list(value.shape),
    }
    if include_hash:
        result["golden"] = chunked_hash(value)
    return result


def _resolved_config_summary(ctx: Any) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for target in PIPELINE_TARGETS:
        resolved = ctx.get_resolved_config(target)
        summary[target] = {
            "adapter_name": resolved.adapter_name,
            "values": _json_safe(resolved.to_dict()),
        }
    return summary


def _lineage_node_summary(lineage: dict[str, Any]) -> dict[str, Any]:
    depends = lineage.get("depends_on", {})
    payload = {
        "plugin_class": lineage.get("plugin_class"),
        "plugin_version": lineage.get("plugin_version"),
        "config": _json_safe(lineage.get("config", {})),
        "depends_on": sorted(depends) if isinstance(depends, dict) else _json_safe(depends),
    }
    canonical = json.dumps(_json_safe(lineage), sort_keys=True, separators=(",", ":"))
    payload["sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return payload


def _lineage_summary(ctx: Any) -> dict[str, Any]:
    return {target: _lineage_node_summary(ctx.get_lineage(target)) for target in PIPELINE_TARGETS}


def _plugin_dependencies(plugin: Any, ctx: Any, run_id: str) -> list[str]:
    resolver = getattr(plugin, "resolve_depends_on", None)
    if callable(resolver):
        return list(resolver(ctx, run_id=run_id))
    return list(getattr(plugin, "depends_on", ()))


def run_compute_only(
    *, run_id: str, storage_dir: str | Path, config: dict[str, Any]
) -> dict[str, Any]:
    targets: dict[str, Any] = {}
    resolved_config: dict[str, Any] | None = None
    lineage: dict[str, Any] | None = None

    for target in PIPELINE_TARGETS:
        warmup_ctx = build_context(storage_dir, config)
        warmup_plugin = warmup_ctx.get_plugin(target)
        for dependency in _plugin_dependencies(warmup_plugin, warmup_ctx, run_id):
            warmup_ctx.get_data(run_id, dependency)
        warmup_plugin.compute(warmup_ctx, run_id)
        del warmup_plugin, warmup_ctx
        gc.collect()

        ctx = build_context(storage_dir, config)
        plugin = ctx.get_plugin(target)
        dependencies = _plugin_dependencies(plugin, ctx, run_id)

        preload_started = time.perf_counter()
        for dependency in dependencies:
            ctx.get_data(run_id, dependency)
        preload_elapsed = time.perf_counter() - preload_started
        if resolved_config is None:
            resolved_config = _resolved_config_summary(ctx)
            lineage = _lineage_summary(ctx)

        with PeakRssSampler() as rss:
            started = time.perf_counter()
            result = plugin.compute(ctx, run_id)
            elapsed = time.perf_counter() - started

        targets[target] = {
            "elapsed_sec": elapsed,
            "preload_elapsed_sec": preload_elapsed,
            "dependencies": dependencies,
            "rss": rss.to_dict(),
            "output": array_summary(result),
        }
        del result, plugin, ctx
        gc.collect()

    return {
        "mode": "compute",
        "targets": targets,
        "total_compute_sec": sum(item["elapsed_sec"] for item in targets.values()),
        "resolved_config": resolved_config or {},
        "lineage": lineage or {},
    }


def run_end_to_end(
    *, run_id: str, storage_dir: str | Path, config: dict[str, Any]
) -> dict[str, Any]:
    effective_config = config.copy()
    effective_config.setdefault("data_root", str(storage_dir))
    storage_path = Path(storage_dir).resolve()
    cache_parent = storage_path.parent

    with tempfile.TemporaryDirectory(
        prefix=".wa-peak-benchmark-cache-", dir=str(cache_parent)
    ) as cache_dir:
        ctx = build_context(cache_dir, effective_config)
        with PeakRssSampler() as rss:
            started = time.perf_counter()
            ctx.get_data(run_id, "peaks")
            elapsed = time.perf_counter() - started

        resolved_config = _resolved_config_summary(ctx)
        lineage = _lineage_summary(ctx)
        targets = {
            target: array_summary(ctx.get_data(run_id, target)) for target in PIPELINE_TARGETS
        }
        profiler = {
            key: {"total_sec": float(value), "calls": int(ctx.profiler.counts.get(key, 0))}
            for key, value in sorted(ctx.profiler.durations.items())
            if key.startswith("plugin.") or key == "context.save_cache"
        }
        return {
            "mode": "end-to-end",
            "elapsed_sec": elapsed,
            "rss": rss.to_dict(),
            "targets": targets,
            "profiler": profiler,
            "resolved_config": resolved_config,
            "lineage": lineage,
            "fresh_cache": True,
        }


def _direct_prerequisites(target: str) -> tuple[str, ...]:
    prerequisites = {
        "peaklet_components": (),
        "peaklets": ("peaklet_components",),
        "peaklet_waveforms": ("peaklet_components", "peaklets"),
        "peaklet_features": ("peaklet_components", "peaklets", "peaklet_waveforms"),
    }
    return prerequisites[target]


def _direct_stage_data(data: dict[str, np.ndarray], target: str) -> dict[str, np.ndarray]:
    stage_data = data.copy()
    stage_data.pop(target, None)
    if target == "peaklet_waveforms":
        stage_data.pop("peaklet_waveform_pool", None)
    return stage_data


def _direct_end_to_end_data(data: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    stage_data = data.copy()
    for target in (*DIRECT_PIPELINE_TARGETS, "peaklet_waveform_pool"):
        stage_data.pop(target, None)
    return stage_data


def run_direct_compute(
    *, run_id: str, manifest_path: str | Path, config: dict[str, Any]
) -> dict[str, Any]:
    data, manifest_config = load_direct_manifest(manifest_path)
    effective_config = {**manifest_config, **config}
    targets = {}
    for target in DIRECT_PIPELINE_TARGETS:
        stage_data = _direct_stage_data(data, target)
        warmup = DirectCacheContext(stage_data, effective_config)
        warmup.get_data(run_id, target)
        del warmup
        gc.collect()

        context = DirectCacheContext(stage_data, effective_config)
        for prerequisite in _direct_prerequisites(target):
            context.get_data(run_id, prerequisite)
        with PeakRssSampler() as rss:
            started = time.perf_counter()
            result = context.get_data(run_id, target)
            elapsed = time.perf_counter() - started
        targets[target] = {
            "elapsed_sec": elapsed,
            "rss": rss.to_dict(),
            "output": array_summary(result),
        }
        del result, context
        gc.collect()
    return {
        "mode": "compute",
        "source": "direct-cache",
        "targets": targets,
        "total_compute_sec": sum(entry["elapsed_sec"] for entry in targets.values()),
    }


def run_direct_end_to_end(
    *, run_id: str, manifest_path: str | Path, config: dict[str, Any]
) -> dict[str, Any]:
    data, manifest_config = load_direct_manifest(manifest_path)
    effective_config = {**manifest_config, **config}
    stage_data = _direct_end_to_end_data(data)
    warmup = DirectCacheContext(stage_data, effective_config)
    for target in DIRECT_PIPELINE_TARGETS:
        warmup.get_data(run_id, target)
    del warmup
    gc.collect()
    with tempfile.TemporaryDirectory(prefix="wa-peak-direct-cache-") as cache_dir:
        context = DirectCacheContext(stage_data, effective_config, output_dir=cache_dir)
        stage_elapsed = {}
        with PeakRssSampler() as rss:
            total_started = time.perf_counter()
            for target in DIRECT_PIPELINE_TARGETS:
                started = time.perf_counter()
                context.get_data(run_id, target)
                stage_elapsed[target] = time.perf_counter() - started
            elapsed = time.perf_counter() - total_started
        targets = {
            target: array_summary(context.get_data(run_id, target))
            for target in DIRECT_PIPELINE_TARGETS
        }
        return {
            "mode": "end-to-end",
            "source": "direct-cache",
            "elapsed_sec": elapsed,
            "stage_elapsed_sec": stage_elapsed,
            "rss": rss.to_dict(),
            "targets": targets,
            "fresh_cache": True,
        }


def run_worker(args: argparse.Namespace) -> dict[str, Any]:
    config = load_config(args.config_json)
    if args.direct_manifest and args.worker_mode == "compute":
        result = run_direct_compute(
            run_id=args.run_id,
            manifest_path=args.direct_manifest,
            config=config,
        )
    elif args.direct_manifest:
        result = run_direct_end_to_end(
            run_id=args.run_id,
            manifest_path=args.direct_manifest,
            config=config,
        )
    elif args.worker_mode == "compute":
        result = run_compute_only(
            run_id=args.run_id,
            storage_dir=args.storage_dir,
            config=config,
        )
    else:
        result = run_end_to_end(
            run_id=args.run_id,
            storage_dir=args.storage_dir,
            config=config,
        )
    result["repeat"] = args.repeat_index
    result["pid"] = os.getpid()
    return result


def _metric_summary(values: list[float]) -> dict[str, float]:
    if not values:
        return {"median": 0.0, "min": 0.0, "max": 0.0, "range_over_median": 0.0}
    median = float(statistics.median(values))
    low = float(min(values))
    high = float(max(values))
    return {
        "median": median,
        "min": low,
        "max": high,
        "range_over_median": (high - low) / median if median else 0.0,
    }


def aggregate_samples(samples: list[dict[str, Any]]) -> dict[str, Any]:
    if not samples:
        return {}
    mode = samples[0]["mode"]

    def output_for(sample: dict[str, Any], target: str) -> dict[str, Any]:
        target_result = sample["targets"][target]
        return target_result["output"] if mode == "compute" else target_result

    target_names = list(samples[0]["targets"])
    if any(set(sample["targets"]) != set(target_names) for sample in samples[1:]):
        raise ValueError("benchmark samples do not contain the same targets")
    golden_consistent = {}
    golden_sha256 = {}
    for target in target_names:
        outputs = [output_for(sample, target) for sample in samples]
        identities = {
            (
                output["row_count"],
                output["nbytes"],
                output["golden"]["golden_sha256"],
            )
            for output in outputs
        }
        golden_consistent[target] = len(identities) == 1
        golden_sha256[target] = outputs[0]["golden"]["golden_sha256"]

    if mode == "compute":
        targets = {}
        for target in target_names:
            entries = [sample["targets"][target] for sample in samples]
            targets[target] = {
                "elapsed_sec": _metric_summary([entry["elapsed_sec"] for entry in entries]),
                "incremental_peak_rss_bytes": _metric_summary(
                    [entry["rss"]["incremental_peak_bytes"] for entry in entries]
                ),
                "row_count": entries[0]["output"]["row_count"],
                "nbytes": entries[0]["output"]["nbytes"],
                "golden_consistent": golden_consistent[target],
                "golden_sha256": golden_sha256[target],
            }
        return {
            "mode": mode,
            "targets": targets,
            "total_compute_sec": _metric_summary(
                [sample["total_compute_sec"] for sample in samples]
            ),
        }

    return {
        "mode": mode,
        "elapsed_sec": _metric_summary([sample["elapsed_sec"] for sample in samples]),
        "incremental_peak_rss_bytes": _metric_summary(
            [sample["rss"]["incremental_peak_bytes"] for sample in samples]
        ),
        "targets": {
            target: {
                "row_count": samples[0]["targets"][target]["row_count"],
                "nbytes": samples[0]["targets"][target]["nbytes"],
                "golden_consistent": golden_consistent[target],
                "golden_sha256": golden_sha256[target],
            }
            for target in target_names
        },
    }


def _comparison_check(
    checks: list[dict[str, Any]],
    *,
    name: str,
    passed: bool,
    target: str | None = None,
    **metrics: Any,
) -> None:
    checks.append({"name": name, "target": target, "passed": bool(passed), **metrics})


def compare_reports(current: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    """Apply reproducibility and performance gates to two aggregate reports."""
    checks: list[dict[str, Any]] = []
    current_summary = current.get("summary", {})
    baseline_summary = baseline.get("summary", {})
    current_compute = current_summary.get("compute", {})
    baseline_compute = baseline_summary.get("compute", {})
    current_targets = current_compute.get("targets", {})
    baseline_targets = baseline_compute.get("targets", {})

    for target in sorted(set(current_targets) | set(baseline_targets)):
        current_target = current_targets.get(target)
        baseline_target = baseline_targets.get(target)
        current_hash = current_target.get("golden_sha256") if current_target else None
        baseline_hash = baseline_target.get("golden_sha256") if baseline_target else None
        consistent = bool(
            current_target
            and baseline_target
            and current_target.get("golden_consistent")
            and baseline_target.get("golden_consistent")
        )
        _comparison_check(
            checks,
            name="golden_hash",
            target=target,
            passed=bool(current_hash and current_hash == baseline_hash and consistent),
            current=current_hash,
            baseline=baseline_hash,
        )

    for target, threshold in COMPUTE_IMPROVEMENT_THRESHOLDS.items():
        current_target = current_targets.get(target)
        baseline_target = baseline_targets.get(target)
        current_median = (
            current_target.get("elapsed_sec", {}).get("median") if current_target else None
        )
        baseline_median = (
            baseline_target.get("elapsed_sec", {}).get("median") if baseline_target else None
        )
        improvement = (
            (baseline_median - current_median) / baseline_median
            if baseline_median and current_median is not None
            else None
        )
        _comparison_check(
            checks,
            name="compute_improvement",
            target=target,
            passed=improvement is not None and improvement >= threshold,
            current_median_sec=current_median,
            baseline_median_sec=baseline_median,
            improvement=improvement,
            required_improvement=threshold,
        )
        variance = (
            current_target.get("elapsed_sec", {}).get("range_over_median")
            if current_target
            else None
        )
        _comparison_check(
            checks,
            name="variance",
            target=target,
            passed=variance is not None and variance <= MAX_RANGE_OVER_MEDIAN,
            range_over_median=variance,
            maximum=MAX_RANGE_OVER_MEDIAN,
        )

    total_variance = current_compute.get("total_compute_sec", {}).get("range_over_median")
    _comparison_check(
        checks,
        name="variance",
        target="total_compute",
        passed=total_variance is not None and total_variance <= MAX_RANGE_OVER_MEDIAN,
        range_over_median=total_variance,
        maximum=MAX_RANGE_OVER_MEDIAN,
    )

    current_e2e = current_summary.get("end-to-end", {})
    baseline_e2e = baseline_summary.get("end-to-end", {})
    current_e2e_median = current_e2e.get("elapsed_sec", {}).get("median")
    baseline_e2e_median = baseline_e2e.get("elapsed_sec", {}).get("median")
    e2e_improvement = (
        (baseline_e2e_median - current_e2e_median) / baseline_e2e_median
        if baseline_e2e_median and current_e2e_median is not None
        else None
    )
    _comparison_check(
        checks,
        name="end_to_end_improvement",
        passed=(
            e2e_improvement is not None and e2e_improvement >= END_TO_END_IMPROVEMENT_THRESHOLD
        ),
        current_median_sec=current_e2e_median,
        baseline_median_sec=baseline_e2e_median,
        improvement=e2e_improvement,
        required_improvement=END_TO_END_IMPROVEMENT_THRESHOLD,
    )
    e2e_variance = current_e2e.get("elapsed_sec", {}).get("range_over_median")
    _comparison_check(
        checks,
        name="variance",
        target="end-to-end",
        passed=e2e_variance is not None and e2e_variance <= MAX_RANGE_OVER_MEDIAN,
        range_over_median=e2e_variance,
        maximum=MAX_RANGE_OVER_MEDIAN,
    )
    return {"passed": all(check["passed"] for check in checks), "checks": checks}


def _run_worker_subprocess(
    *, args: argparse.Namespace, mode: str, repeat_index: int, output_path: Path
) -> dict[str, Any]:
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--run-id",
        args.run_id,
        "--storage-dir",
        str(args.storage_dir),
        "--config-json",
        str(args.config_json),
        "--worker-mode",
        mode,
        "--repeat-index",
        str(repeat_index),
        "--worker-output",
        str(output_path),
    ]
    if args.direct_manifest:
        command.extend(["--direct-manifest", str(args.direct_manifest)])
    completed = subprocess.run(command, capture_output=True, text=True)
    if completed.returncode != 0:
        raise RuntimeError(
            f"benchmark worker failed for mode={mode} repeat={repeat_index}\n"
            f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        )
    return json.loads(output_path.read_text(encoding="utf-8"))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id")
    parser.add_argument("--storage-dir")
    parser.add_argument("--config-json")
    parser.add_argument("--direct-manifest")
    parser.add_argument("--baseline-report")
    parser.add_argument("--current-report")
    parser.add_argument("--comparison-json-out")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--mode", choices=("compute", "end-to-end", "both"), default="both")
    parser.add_argument("--json-out")
    parser.add_argument("--worker-mode", choices=("compute", "end-to-end"), help=argparse.SUPPRESS)
    parser.add_argument("--repeat-index", type=int, default=0, help=argparse.SUPPRESS)
    parser.add_argument("--worker-output", help=argparse.SUPPRESS)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.current_report:
        if not args.baseline_report:
            raise SystemExit("--current-report requires --baseline-report")
        current = json.loads(Path(args.current_report).read_text(encoding="utf-8"))
        baseline = json.loads(Path(args.baseline_report).read_text(encoding="utf-8"))
        comparison = compare_reports(current, baseline)
        rendered = json.dumps(comparison, ensure_ascii=False, indent=2, sort_keys=True)
        if args.comparison_json_out:
            Path(args.comparison_json_out).write_text(rendered, encoding="utf-8")
        else:
            print(rendered)
        return 0 if comparison["passed"] else 1

    if args.repeats < 1:
        raise SystemExit("--repeats must be >= 1")
    if not args.run_id or not args.config_json:
        raise SystemExit("benchmark mode requires --run-id and --config-json")
    if not args.direct_manifest and not args.storage_dir:
        raise SystemExit("benchmark mode requires --storage-dir unless --direct-manifest is used")
    if not Path(args.config_json).is_file():
        raise SystemExit(f"--config-json does not exist: {args.config_json}")
    if args.direct_manifest and not Path(args.direct_manifest).is_file():
        raise SystemExit(f"--direct-manifest does not exist: {args.direct_manifest}")

    if args.worker_mode:
        if not args.worker_output:
            raise SystemExit("worker mode requires --worker-output")
        payload = run_worker(args)
        Path(args.worker_output).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"
        )
        return 0

    modes = ("compute", "end-to-end") if args.mode == "both" else (args.mode,)
    samples: dict[str, list[dict[str, Any]]] = {mode: [] for mode in modes}
    with tempfile.TemporaryDirectory(prefix="wa-peak-benchmark-workers-") as tmpdir:
        for mode in modes:
            for repeat_index in range(args.repeats):
                output_path = Path(tmpdir) / f"{mode}-{repeat_index}.json"
                samples[mode].append(
                    _run_worker_subprocess(
                        args=args,
                        mode=mode,
                        repeat_index=repeat_index,
                        output_path=output_path,
                    )
                )

    payload = {
        "schema_version": 1,
        "run_id": args.run_id,
        "storage_dir": str(Path(args.storage_dir).resolve()) if args.storage_dir else None,
        "direct_manifest": (
            str(Path(args.direct_manifest).resolve()) if args.direct_manifest else None
        ),
        "config_json": str(Path(args.config_json).resolve()),
        "repeats": args.repeats,
        "mode": args.mode,
        "rss_sample_interval_sec": RSS_SAMPLE_INTERVAL_SEC,
        "targets": list(DIRECT_PIPELINE_TARGETS if args.direct_manifest else PIPELINE_TARGETS),
        "samples": samples,
        "summary": {
            mode: aggregate_samples(mode_samples) for mode, mode_samples in samples.items()
        },
    }
    if args.baseline_report:
        baseline = json.loads(Path(args.baseline_report).read_text(encoding="utf-8"))
        payload["comparison"] = compare_reports(payload, baseline)
    rendered = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    if args.json_out:
        output = Path(args.json_out)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
        print(f"JSON report written to {output}")
    else:
        print(rendered)
    if args.comparison_json_out and "comparison" in payload:
        Path(args.comparison_json_out).write_text(
            json.dumps(payload["comparison"], ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
    return 0 if payload.get("comparison", {}).get("passed", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
