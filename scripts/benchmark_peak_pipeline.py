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
import platform
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
PEAKLET_WAVEFORM_TARGET = "peaklet_waveforms"
PEAKLET_WAVEFORM_POOL = "peaklet_waveform_pool"
DIRECT_PIPELINE_TARGETS = (
    "peaklet_components",
    "peaklets",
    "peaklet_waveforms",
    "peaklet_features",
)
DIRECT_PEAKLET_WAVEFORM_DEPENDENCIES = (
    "peaklets",
    "peaklet_components",
    "hit_merged",
    "hit_merged_components",
    "hit_threshold",
    "records",
    "wave_pool",
)
DIRECT_PEAKLET_WAVEFORM_FILTERED_DEPENDENCY = "wave_pool_filtered"
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


def _read_direct_manifest(path: str | Path) -> tuple[Path, dict[str, Any]]:
    manifest_path = Path(path).resolve()
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"direct manifest does not exist: {manifest_path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"direct manifest is not valid JSON: {manifest_path}") from exc
    if not isinstance(manifest, dict):
        raise ValueError("direct manifest must contain a JSON object")
    return manifest_path, manifest


def _manifest_stem_spec(stems: dict[str, Any], name: str) -> dict[str, Any]:
    if name not in stems:
        raise ValueError(f"direct manifest is missing required stem {name!r}")
    raw_spec = stems[name]
    if isinstance(raw_spec, str):
        return {"stem": raw_spec}
    if not isinstance(raw_spec, dict):
        raise ValueError(f"direct manifest stem {name!r} must be a string or object")
    return dict(raw_spec)


def _shape_from_metadata(metadata: dict[str, Any], spec: dict[str, Any]) -> tuple[int, ...] | None:
    shape = spec.get("shape", metadata.get("shape"))
    if shape is None and "count" in metadata:
        shape = [metadata["count"]]
    if shape is None:
        return None
    if isinstance(shape, int):
        shape = [shape]
    if not isinstance(shape, list | tuple) or any(
        not isinstance(item, int) or item < 0 for item in shape
    ):
        raise ValueError("direct manifest shape must be a non-negative integer sequence")
    return tuple(int(item) for item in shape)


def _canonical_sha256(value: Any) -> str:
    encoded = json.dumps(_json_safe(value), sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _merge_config(manifest_config: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    """Merge benchmark overrides without discarding nested manifest settings."""
    merged = dict(manifest_config)
    for key, value in overrides.items():
        existing = merged.get(key)
        if isinstance(existing, dict) and isinstance(value, dict):
            nested = dict(existing)
            nested.update(value)
            merged[key] = nested
        else:
            merged[key] = value
    return merged


def _wave_pool_dependency_name(config: dict[str, Any]) -> str:
    nested = config.get(PEAKLET_WAVEFORM_TARGET)
    if isinstance(nested, dict) and "use_filtered" in nested:
        use_filtered = nested["use_filtered"]
    else:
        use_filtered = config.get(f"{PEAKLET_WAVEFORM_TARGET}.use_filtered", False)
    return DIRECT_PEAKLET_WAVEFORM_FILTERED_DEPENDENCY if bool(use_filtered) else "wave_pool"


def _direct_required_dependencies(target: str, config: dict[str, Any]) -> tuple[str, ...]:
    if target == PEAKLET_WAVEFORM_TARGET:
        dependencies = list(DIRECT_PEAKLET_WAVEFORM_DEPENDENCIES)
        pool_name = _wave_pool_dependency_name(config)
        if pool_name != "wave_pool":
            dependencies[-1] = pool_name
        return tuple(dependencies)
    if target == "peaklet_features":
        return ("peaklets", "peaklet_components", PEAKLET_WAVEFORM_TARGET, PEAKLET_WAVEFORM_POOL)
    if target == "peaklets":
        return ("peaklet_components", "hit_merged")
    if target == "peaklet_components":
        return ("hit_merged",)
    raise ValueError(f"unsupported direct benchmark target: {target!r}")


def _validate_manifest_lineage(
    manifest: dict[str, Any],
    stems: dict[str, Any],
    required: tuple[str, ...],
    loaded_lineage: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a deterministic lineage mapping and reject incomplete manifests."""
    raw_lineage = manifest.get("lineage")
    if raw_lineage is None:
        raw_lineage = {
            name: stems[name].get("lineage")
            for name in required
            if isinstance(stems.get(name), dict) and "lineage" in stems[name]
        }
    if not isinstance(raw_lineage, dict):
        raise ValueError("direct manifest requires a lineage object for the selected target")
    if isinstance(raw_lineage, dict) and isinstance(raw_lineage.get("dependencies"), dict):
        raw_lineage = raw_lineage["dependencies"]
    merged_lineage = dict(loaded_lineage or {})
    merged_lineage.update(raw_lineage)
    raw_lineage = merged_lineage
    missing = [name for name in required if name not in raw_lineage]
    if missing:
        raise ValueError("direct manifest lineage is missing required stems: " + ", ".join(missing))
    expected_hash = manifest.get("lineage_sha256")
    if expected_hash is not None:
        actual_hash = _canonical_sha256(raw_lineage)
        if str(expected_hash) != actual_hash:
            raise ValueError("direct manifest lineage_sha256 does not match the manifest lineage")
    return _json_safe(raw_lineage)


def _load_direct_manifest_with_metadata(
    path: str | Path,
    *,
    target: str | None = None,
    config: dict[str, Any] | None = None,
) -> tuple[dict[str, np.ndarray], dict[str, Any], dict[str, Any]]:
    """Load read-only direct arrays and validate a selected target manifest."""
    manifest_path, manifest = _read_direct_manifest(path)
    cache_root_value = manifest.get("cache_root")
    stems = manifest.get("stems")
    if not cache_root_value or not isinstance(stems, dict) or not stems:
        raise ValueError("direct manifest requires cache_root and a non-empty stems mapping")

    cache_root = Path(cache_root_value)
    if not cache_root.is_absolute():
        cache_root = manifest_path.parent / cache_root
    manifest_config = manifest.get("config", {})
    if not isinstance(manifest_config, dict):
        raise ValueError("direct manifest config must be an object")
    effective_config = _merge_config(manifest_config, config or {})
    if target is not None and "config" not in manifest:
        raise ValueError("direct manifest requires a config object for the selected target")
    manifest_target = manifest.get("target")
    if manifest_target is not None and target is not None and manifest_target != target:
        raise ValueError(
            f"direct manifest target={manifest_target!r} does not match requested target={target!r}"
        )
    if target == PEAKLET_WAVEFORM_TARGET:
        manifest_pool = _wave_pool_dependency_name(manifest_config)
        manifest_waveform_config = manifest_config.get(PEAKLET_WAVEFORM_TARGET)
        has_manifest_filter = isinstance(manifest_waveform_config, dict) and (
            "use_filtered" in manifest_waveform_config
        )
        has_manifest_filter = has_manifest_filter or (
            f"{PEAKLET_WAVEFORM_TARGET}.use_filtered" in manifest_config
        )
        explicit_waveform_config = (config or {}).get(PEAKLET_WAVEFORM_TARGET)
        has_explicit_filter = isinstance(explicit_waveform_config, dict) and (
            "use_filtered" in explicit_waveform_config
        )
        has_explicit_filter = has_explicit_filter or (
            f"{PEAKLET_WAVEFORM_TARGET}.use_filtered" in (config or {})
        )
        explicit_pool = (
            _wave_pool_dependency_name(config or {}) if has_explicit_filter else manifest_pool
        )
        if has_explicit_filter and has_manifest_filter and manifest_pool != explicit_pool:
            raise ValueError("direct manifest peaklet_waveforms.use_filtered conflicts with config")
    required: tuple[str, ...] = ()
    if target is not None:
        required = _direct_required_dependencies(target, effective_config)
    arrays: dict[str, np.ndarray] = {}
    loaded_metadata: dict[str, dict[str, Any]] = {}
    loaded_lineage: dict[str, Any] = {}
    for name in stems:
        spec = _manifest_stem_spec(stems, name)
        stem = spec.get("stem", name)
        default_path = stem if Path(stem).suffix else f"{stem}.bin"
        data_path = Path(spec.get("path", default_path))
        if not data_path.is_absolute():
            data_path = cache_root / data_path
        data_path = data_path.resolve()
        if not data_path.is_file():
            raise ValueError(f"direct manifest stem {name!r} path does not exist: {data_path}")

        metadata: dict[str, Any] = {}
        metadata_value = spec.get("metadata")
        if metadata_value is not None:
            metadata_path = Path(metadata_value)
            if not metadata_path.is_absolute():
                metadata_path = cache_root / metadata_path
            metadata_path = metadata_path.resolve()
            if not metadata_path.is_file():
                raise ValueError(
                    f"direct manifest stem {name!r} metadata does not exist: {metadata_path}"
                )
            try:
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise ValueError(
                    f"direct manifest stem {name!r} metadata is not valid JSON"
                ) from exc
            if not isinstance(metadata, dict):
                raise ValueError(f"direct manifest stem {name!r} metadata must be an object")

        if data_path.suffix == ".npy":
            try:
                arrays[name] = np.load(data_path, mmap_mode="r", allow_pickle=False)
            except (OSError, ValueError) as exc:
                raise ValueError(f"could not load direct manifest stem {name!r}") from exc
        else:
            if not metadata:
                metadata_path = Path(spec.get("metadata", f"{stem}.json"))
                if not metadata_path.is_absolute():
                    metadata_path = cache_root / metadata_path
                metadata_path = metadata_path.resolve()
                if not metadata_path.is_file():
                    raise ValueError(
                        f"direct manifest stem {name!r} metadata does not exist: {metadata_path}"
                    )
                try:
                    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError) as exc:
                    raise ValueError(
                        f"direct manifest stem {name!r} metadata is not valid JSON"
                    ) from exc
                if not isinstance(metadata, dict):
                    raise ValueError(f"direct manifest stem {name!r} metadata must be an object")

        dtype_value = spec.get("dtype_descr", spec.get("dtype"))
        if dtype_value is None:
            dtype_value = metadata.get("dtype_descr", metadata.get("dtype"))
        if target is not None and name in required and dtype_value is None:
            raise ValueError(f"direct manifest stem {name!r} is missing dtype metadata")
        if data_path.suffix != ".npy" and dtype_value is None:
            raise ValueError(f"direct manifest stem {name!r} is missing dtype metadata")
        shape = _shape_from_metadata(metadata, spec)
        if target is not None and name in required and shape is None:
            raise ValueError(f"direct manifest stem {name!r} is missing shape metadata")
        if data_path.suffix != ".npy":
            if shape is None:
                raise ValueError(f"direct manifest stem {name!r} is missing shape metadata")
            arrays[name] = np.memmap(
                data_path,
                dtype=_dtype_from_json(dtype_value),
                mode="r",
                shape=shape,
            )
        if not isinstance(arrays[name], np.ndarray):
            raise ValueError(f"direct manifest stem {name!r} did not load as an ndarray")
        if arrays[name].flags.writeable:
            raise ValueError(f"direct manifest stem {name!r} must be opened read-only")

        if dtype_value is not None and arrays[name].dtype != _dtype_from_json(dtype_value):
            raise ValueError(
                f"direct manifest stem {name!r} dtype does not match its metadata: "
                f"{arrays[name].dtype} != {_dtype_from_json(dtype_value)}"
            )
        if shape is not None and tuple(arrays[name].shape) != shape:
            raise ValueError(
                f"direct manifest stem {name!r} shape does not match its metadata: "
                f"{tuple(arrays[name].shape)} != {shape}"
            )
        loaded_metadata[name] = {
            "path": str(data_path),
            "dtype": (
                arrays[name].dtype.descr if arrays[name].dtype.names else arrays[name].dtype.str
            ),
            "shape": list(arrays[name].shape),
            "nbytes": int(arrays[name].nbytes),
        }
        if "lineage" in metadata:
            loaded_lineage[name] = metadata["lineage"]

    lineage: dict[str, Any] = {}
    if target is not None:
        required = _direct_required_dependencies(target, effective_config)
        missing = [name for name in required if name not in arrays]
        if missing:
            raise ValueError(
                "direct manifest is missing required dependencies for "
                f"{target!r}: {', '.join(missing)}"
            )
        lineage = _validate_manifest_lineage(manifest, stems, required, loaded_lineage)
    config_hash = manifest.get("config_sha256")
    if config_hash is not None and str(config_hash) != _canonical_sha256(manifest_config):
        raise ValueError("direct manifest config_sha256 does not match the manifest config")

    metadata = {
        "manifest_path": str(manifest_path),
        "cache_root": str(cache_root.resolve()),
        "target": target,
        "required_dependencies": list(required),
        "lineage": lineage,
        "lineage_sha256": _canonical_sha256(lineage) if lineage else None,
        "config_sha256": _canonical_sha256(effective_config),
        "stems": loaded_metadata,
    }
    return arrays, manifest_config, metadata


def load_direct_manifest(path: str | Path) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    """Load direct arrays as read-only memmaps (legacy two-value API)."""
    arrays, config, _metadata = _load_direct_manifest_with_metadata(path)
    return arrays, config


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


def validate_offset_pool_contract(waveforms: np.ndarray, pool: np.ndarray) -> dict[str, Any]:
    """Validate the ragged index/pool relationship without copying the pool."""
    if not isinstance(waveforms, np.ndarray):
        raise TypeError("waveform index must be a numpy array")
    if not isinstance(pool, np.ndarray):
        raise TypeError("waveform pool must be a numpy array")
    names = waveforms.dtype.names or ()
    missing = [name for name in ("wave_offset", "wave_length") if name not in names]
    if missing:
        raise ValueError("waveform index is missing contract fields: " + ", ".join(missing))
    if pool.ndim != 1:
        raise ValueError(f"waveform pool must be one-dimensional, got shape={pool.shape}")

    offsets = np.asarray(waveforms["wave_offset"], dtype=np.int64)
    lengths = np.asarray(waveforms["wave_length"], dtype=np.int64)
    invalid_negative = np.flatnonzero((offsets < 0) | (lengths < 0))
    ends = offsets + lengths
    invalid_bounds = np.flatnonzero(ends > len(pool))
    if len(invalid_negative) or len(invalid_bounds):
        examples = np.unique(np.concatenate((invalid_negative[:5], invalid_bounds[:5])))
        raise ValueError(
            "waveform index references samples outside its pool: "
            + ", ".join(str(int(item)) for item in examples)
        )

    # Offsets are allowed to repeat for empty rows, but a valid builder must
    # never move backwards through the flattened pool.
    non_monotonic = np.flatnonzero(offsets[1:] < offsets[:-1])
    if len(non_monotonic):
        raise ValueError(f"waveform offsets are not monotonic at row={int(non_monotonic[0]) + 1}")
    return {
        "valid": True,
        "rows_checked": int(len(waveforms)),
        "pool_length": int(len(pool)),
        "max_referenced_end": int(ends.max()) if len(ends) else 0,
        "offset_field": "wave_offset",
        "length_field": "wave_length",
        "pool_ndim": int(pool.ndim),
    }


def paired_output_summary(waveforms: Any, pool: Any) -> dict[str, Any]:
    """Return paired index/pool hashes and the offset contract."""
    contract = validate_offset_pool_contract(waveforms, pool)
    return {
        "paired_output": array_summary(pool),
        "offset_pool_contract": contract,
    }


def _selected_targets(available: tuple[str, ...], target: str | None) -> tuple[str, ...]:
    if target is None:
        return available
    if target not in available:
        raise ValueError(
            f"unsupported benchmark target {target!r}; choose one of {', '.join(available)}"
        )
    return (target,)


def _runtime_environment() -> dict[str, Any]:
    """Capture reproducibility metadata without importing optional thread tools."""
    repository = Path(__file__).resolve().parent.parent

    def git(*arguments: str) -> str | None:
        try:
            completed = subprocess.run(
                ["git", *arguments],
                cwd=repository,
                capture_output=True,
                text=True,
                check=True,
            )
        except (OSError, subprocess.CalledProcessError):
            return None
        return completed.stdout.strip()

    try:
        git_diff = subprocess.run(
            ["git", "diff", "--binary", "HEAD"],
            cwd=repository,
            capture_output=True,
            check=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        git_diff_sha256 = None
    else:
        git_diff_sha256 = hashlib.sha256(git_diff).hexdigest()

    thread_env = {
        key: value
        for key, value in sorted(os.environ.items())
        if key.startswith(("OMP_", "MKL_", "OPENBLAS_", "NUMBA_", "VECLIB_", "BLAS_"))
    }
    try:
        import numba

        numba_version = numba.__version__
    except ImportError:
        numba_version = None
    return {
        "git_sha": git("rev-parse", "HEAD"),
        "git_dirty": git("status", "--porcelain") not in (None, ""),
        "git_diff_sha256": git_diff_sha256,
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "python_executable": sys.executable,
        "numpy_version": np.__version__,
        "numba_version": numba_version,
        "thread_environment": thread_env,
    }


WARMUP_TYPE = "warm_jit_warm_page_cache"


def _resolved_config_summary(ctx: Any, targets: tuple[str, ...] | None = None) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for target in targets or PIPELINE_TARGETS:
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


def _lineage_summary(ctx: Any, targets: tuple[str, ...] | None = None) -> dict[str, Any]:
    return {
        target: _lineage_node_summary(ctx.get_lineage(target))
        for target in (targets or PIPELINE_TARGETS)
    }


def _plugin_dependencies(plugin: Any, ctx: Any, run_id: str) -> list[str]:
    resolver = getattr(plugin, "resolve_depends_on", None)
    if callable(resolver):
        return list(resolver(ctx, run_id=run_id))
    return list(getattr(plugin, "depends_on", ()))


def run_compute_only(
    *,
    run_id: str,
    storage_dir: str | Path,
    config: dict[str, Any],
    target: str | None = None,
) -> dict[str, Any]:
    targets: dict[str, Any] = {}
    resolved_config: dict[str, Any] | None = None
    lineage: dict[str, Any] | None = None
    selected_targets = _selected_targets(PIPELINE_TARGETS, target)
    warmup_elapsed_total = 0.0

    for target_name in selected_targets:
        warmup_started = time.perf_counter()
        warmup_ctx = build_context(storage_dir, config)
        warmup_plugin = warmup_ctx.get_plugin(target_name)
        for dependency in _plugin_dependencies(warmup_plugin, warmup_ctx, run_id):
            warmup_ctx.get_data(run_id, dependency)
        warmup_plugin.compute(warmup_ctx, run_id)
        del warmup_plugin, warmup_ctx
        gc.collect()
        warmup_elapsed = time.perf_counter() - warmup_started
        warmup_elapsed_total += warmup_elapsed

        ctx = build_context(storage_dir, config)
        plugin = ctx.get_plugin(target_name)
        dependencies = _plugin_dependencies(plugin, ctx, run_id)

        preload_started = time.perf_counter()
        for dependency in dependencies:
            ctx.get_data(run_id, dependency)
        preload_elapsed = time.perf_counter() - preload_started
        if resolved_config is None:
            if target is None:
                # Keep the historical full-pipeline call shape for callers that
                # monkeypatch these reporting helpers.
                resolved_config = _resolved_config_summary(ctx)
                lineage = _lineage_summary(ctx)
            else:
                resolved_config = _resolved_config_summary(ctx, selected_targets)
                lineage = _lineage_summary(ctx, selected_targets)

        with PeakRssSampler() as rss:
            started = time.perf_counter()
            result = plugin.compute(ctx, run_id)
            elapsed = time.perf_counter() - started

        target_result: dict[str, Any] = {
            "elapsed_sec": elapsed,
            "preload_elapsed_sec": preload_elapsed,
            "dependencies": dependencies,
            "warmup_elapsed_sec": warmup_elapsed,
            "warmup_type": WARMUP_TYPE,
            "rss": rss.to_dict(),
            "output": array_summary(result),
        }
        if target_name == PEAKLET_WAVEFORM_TARGET:
            pool = ctx.get_data(run_id, PEAKLET_WAVEFORM_POOL)
            target_result.update(paired_output_summary(result, pool))
        targets[target_name] = target_result
        del result, plugin, ctx
        gc.collect()

    return {
        "mode": "compute",
        "targets": targets,
        "total_compute_sec": sum(item["elapsed_sec"] for item in targets.values()),
        "warmup_type": WARMUP_TYPE,
        "warmup_elapsed_sec": warmup_elapsed_total,
        "resolved_config": resolved_config or {},
        "lineage": lineage or {},
    }


def run_end_to_end(
    *,
    run_id: str,
    storage_dir: str | Path,
    config: dict[str, Any],
    target: str | None = None,
) -> dict[str, Any]:
    effective_config = config.copy()
    effective_config.setdefault("data_root", str(storage_dir))
    storage_path = Path(storage_dir).resolve()
    cache_parent = storage_path.parent

    with tempfile.TemporaryDirectory(
        prefix=".wa-peak-benchmark-cache-", dir=str(cache_parent)
    ) as cache_dir:
        ctx = build_context(cache_dir, effective_config)
        selected_targets = _selected_targets(PIPELINE_TARGETS, target)
        with PeakRssSampler() as rss:
            started = time.perf_counter()
            if target is None:
                # Preserve the historical end-to-end entry point: the final
                # ``peaks`` request drives the complete dependency graph.
                ctx.get_data(run_id, "peaks")
            else:
                ctx.get_data(run_id, target)
            elapsed = time.perf_counter() - started

        if target is None:
            resolved_config = _resolved_config_summary(ctx)
            lineage = _lineage_summary(ctx)
        else:
            resolved_config = _resolved_config_summary(ctx, selected_targets)
            lineage = _lineage_summary(ctx, selected_targets)
        targets: dict[str, Any] = {}
        for target_name in selected_targets:
            result = ctx.get_data(run_id, target_name)
            target_summary = array_summary(result)
            if target_name == PEAKLET_WAVEFORM_TARGET:
                target_summary.update(
                    paired_output_summary(result, ctx.get_data(run_id, PEAKLET_WAVEFORM_POOL))
                )
            targets[target_name] = target_summary
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
            "target": target,
            "warmup_type": "none_cold_end_to_end",
            "warmup_elapsed_sec": 0.0,
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
    *,
    run_id: str,
    manifest_path: str | Path,
    config: dict[str, Any],
    target: str | None = None,
) -> dict[str, Any]:
    data, manifest_config, manifest_metadata = _load_direct_manifest_with_metadata(
        manifest_path,
        target=target,
        config=config,
    )
    effective_config = _merge_config(manifest_config, config)
    targets: dict[str, Any] = {}
    selected_targets = _selected_targets(DIRECT_PIPELINE_TARGETS, target)
    warmup_elapsed_total = 0.0
    for target_name in selected_targets:
        stage_data = _direct_stage_data(data, target_name)
        warmup_started = time.perf_counter()
        warmup = DirectCacheContext(stage_data, effective_config)
        for dependency in _direct_required_dependencies(target_name, effective_config):
            warmup.get_data(run_id, dependency)
        warmup.get_data(run_id, target_name)
        del warmup
        gc.collect()
        warmup_elapsed = time.perf_counter() - warmup_started
        warmup_elapsed_total += warmup_elapsed

        context = DirectCacheContext(stage_data, effective_config)
        dependencies = _direct_required_dependencies(target_name, effective_config)
        preload_started = time.perf_counter()
        for dependency in dependencies:
            context.get_data(run_id, dependency)
        preload_elapsed = time.perf_counter() - preload_started
        with PeakRssSampler() as rss:
            started = time.perf_counter()
            result = context.get_data(run_id, target_name)
            elapsed = time.perf_counter() - started
        target_result: dict[str, Any] = {
            "elapsed_sec": elapsed,
            "preload_elapsed_sec": preload_elapsed,
            "dependencies": list(dependencies),
            "warmup_elapsed_sec": warmup_elapsed,
            "warmup_type": WARMUP_TYPE,
            "rss": rss.to_dict(),
            "output": array_summary(result),
        }
        if target_name == PEAKLET_WAVEFORM_TARGET:
            pool = context.get_data(run_id, PEAKLET_WAVEFORM_POOL)
            target_result.update(paired_output_summary(result, pool))
            plugins = getattr(context, "_plugins", {})
            plugin = plugins.get(target_name) if isinstance(plugins, dict) else None
            diagnostics = getattr(plugin, "_last_waveform_diagnostics", None)
            if isinstance(diagnostics, dict):
                diagnostics = _json_safe(diagnostics)
                phase_timings = dict(diagnostics.get("phase_timings", {}))
                # Direct compute deliberately does not persist a cache.  Keep
                # the fifth phase explicit so reports cannot confuse an
                # unmeasured disk write with plugin compute time.
                phase_timings["save_cache"] = 0.0
                diagnostics["phase_timings"] = phase_timings
                diagnostics["save_cache_applicable"] = False
                target_result["diagnostics"] = diagnostics
        targets[target_name] = target_result
        del result, context
        gc.collect()
    return {
        "mode": "compute",
        "source": "direct-cache",
        "targets": targets,
        "total_compute_sec": sum(entry["elapsed_sec"] for entry in targets.values()),
        "warmup_type": WARMUP_TYPE,
        "warmup_elapsed_sec": warmup_elapsed_total,
        "manifest": manifest_metadata,
        "resolved_config": _json_safe(effective_config),
        "lineage": manifest_metadata.get("lineage", {}),
    }


def run_direct_end_to_end(
    *,
    run_id: str,
    manifest_path: str | Path,
    config: dict[str, Any],
    target: str | None = None,
) -> dict[str, Any]:
    data, manifest_config, manifest_metadata = _load_direct_manifest_with_metadata(
        manifest_path,
        target=target,
        config=config,
    )
    effective_config = _merge_config(manifest_config, config)
    stage_data = _direct_end_to_end_data(data)
    selected_targets = _selected_targets(DIRECT_PIPELINE_TARGETS, target)
    warmup_started = time.perf_counter()
    warmup = DirectCacheContext(stage_data, effective_config)
    for target_name in selected_targets:
        warmup.get_data(run_id, target_name)
    del warmup
    gc.collect()
    warmup_elapsed = time.perf_counter() - warmup_started
    with tempfile.TemporaryDirectory(prefix="wa-peak-direct-cache-") as cache_dir:
        context = DirectCacheContext(stage_data, effective_config, output_dir=cache_dir)
        stage_elapsed = {}
        with PeakRssSampler() as rss:
            total_started = time.perf_counter()
            for target_name in selected_targets:
                started = time.perf_counter()
                context.get_data(run_id, target_name)
                stage_elapsed[target_name] = time.perf_counter() - started
            elapsed = time.perf_counter() - total_started
        targets: dict[str, Any] = {}
        for target_name in selected_targets:
            result = context.get_data(run_id, target_name)
            target_summary = array_summary(result)
            if target_name == PEAKLET_WAVEFORM_TARGET:
                target_summary.update(
                    paired_output_summary(result, context.get_data(run_id, PEAKLET_WAVEFORM_POOL))
                )
            targets[target_name] = target_summary
        return {
            "mode": "end-to-end",
            "source": "direct-cache",
            "elapsed_sec": elapsed,
            "stage_elapsed_sec": stage_elapsed,
            "rss": rss.to_dict(),
            "targets": targets,
            "fresh_cache": True,
            "warmup_type": WARMUP_TYPE,
            "warmup_elapsed_sec": warmup_elapsed,
            "manifest": manifest_metadata,
            "resolved_config": _json_safe(effective_config),
            "lineage": manifest_metadata.get("lineage", {}),
        }


def run_worker(args: argparse.Namespace) -> dict[str, Any]:
    config = load_config(args.config_json)
    target = getattr(args, "target", None)
    if args.direct_manifest and args.worker_mode == "compute":
        result = run_direct_compute(
            run_id=args.run_id,
            manifest_path=args.direct_manifest,
            config=config,
            target=target,
        )
    elif args.direct_manifest:
        result = run_direct_end_to_end(
            run_id=args.run_id,
            manifest_path=args.direct_manifest,
            config=config,
            target=target,
        )
    elif args.worker_mode == "compute":
        result = run_compute_only(
            run_id=args.run_id,
            storage_dir=args.storage_dir,
            config=config,
            target=target,
        )
    else:
        result = run_end_to_end(
            run_id=args.run_id,
            storage_dir=args.storage_dir,
            config=config,
            target=target,
        )
    result["repeat"] = args.repeat_index
    result["pid"] = os.getpid()
    result["target"] = target
    result["runtime_environment"] = _runtime_environment()
    result["environment"] = result["runtime_environment"]
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
    if any(sample.get("mode") != mode for sample in samples[1:]):
        raise ValueError("benchmark samples do not have the same mode")

    def output_for(sample: dict[str, Any], target: str) -> dict[str, Any]:
        target_result = sample["targets"][target]
        return target_result["output"] if mode == "compute" else target_result

    def output_identity(output: dict[str, Any]) -> tuple[Any, ...]:
        golden = output.get("golden", {})
        return (
            output.get("row_count"),
            output.get("nbytes"),
            repr(output.get("dtype")),
            repr(output.get("shape")),
            golden.get("golden_sha256"),
        )

    def output_aggregate(outputs: list[dict[str, Any]]) -> dict[str, Any]:
        first = outputs[0]
        golden = first.get("golden", {})
        result = {
            "row_count": first.get("row_count"),
            "nbytes": first.get("nbytes"),
            "dtype": first.get("dtype"),
            "shape": first.get("shape"),
            "golden_consistent": len({output_identity(item) for item in outputs}) == 1,
            "golden_sha256": golden.get("golden_sha256"),
        }
        # Keep the raw-data digest available for a paired-output audit while
        # retaining golden_sha256 as the comparison identity.
        if "golden" in first and "data_sha256" in golden:
            result["data_sha256"] = golden["data_sha256"]
        return result

    def paired_for(sample: dict[str, Any], target: str) -> dict[str, Any] | None:
        target_result = sample["targets"][target]
        if mode == "compute":
            return target_result.get("paired_output")
        return target_result.get("paired_output")

    def contract_for(sample: dict[str, Any], target: str) -> dict[str, Any] | None:
        return sample["targets"][target].get("offset_pool_contract")

    target_names = list(samples[0]["targets"])
    if any(set(sample["targets"]) != set(target_names) for sample in samples[1:]):
        raise ValueError("benchmark samples do not contain the same targets")
    golden_consistent = {}
    golden_sha256 = {}
    output_summaries: dict[str, dict[str, Any]] = {}
    paired_summaries: dict[str, dict[str, Any] | None] = {}
    contract_summaries: dict[str, dict[str, Any] | None] = {}
    for target in target_names:
        outputs = [output_for(sample, target) for sample in samples]
        output_summaries[target] = output_aggregate(outputs)
        golden_consistent[target] = output_summaries[target]["golden_consistent"]
        golden_sha256[target] = output_summaries[target]["golden_sha256"]

        paired_outputs = [paired_for(sample, target) for sample in samples]
        if any(item is not None for item in paired_outputs):
            if not all(item is not None for item in paired_outputs):
                raise ValueError(f"paired output is missing from some {target!r} samples")
            paired_summaries[target] = output_aggregate(
                [item for item in paired_outputs if item is not None]
            )
        else:
            paired_summaries[target] = None

        contracts = [contract_for(sample, target) for sample in samples]
        if any(item is not None for item in contracts):
            if not all(item is not None for item in contracts):
                raise ValueError(f"offset/pool contract is missing from some {target!r} samples")
            first_contract = contracts[0]
            assert first_contract is not None
            contract_summaries[target] = {
                **first_contract,
                "valid": all(bool(item.get("valid")) for item in contracts if item is not None),
            }
        else:
            contract_summaries[target] = None

    if mode == "compute":
        targets = {}
        for target in target_names:
            entries = [sample["targets"][target] for sample in samples]
            target_summary = {
                "elapsed_sec": _metric_summary([entry["elapsed_sec"] for entry in entries]),
                "incremental_peak_rss_bytes": _metric_summary(
                    [entry["rss"]["incremental_peak_bytes"] for entry in entries]
                ),
                **output_summaries[target],
                "golden_consistent": golden_consistent[target],
                "golden_sha256": golden_sha256[target],
            }
            if paired_summaries[target] is not None:
                target_summary["paired_output"] = paired_summaries[target]
                target_summary["offset_pool_contract"] = contract_summaries[target]
            diagnostics = [entry.get("diagnostics") for entry in entries]
            if any(item is not None for item in diagnostics):
                if not all(isinstance(item, dict) for item in diagnostics):
                    raise ValueError(f"diagnostics are missing from some {target!r} samples")
                phase_names = sorted(
                    {phase for item in diagnostics for phase in item.get("phase_timings", {})}
                )
                target_summary["diagnostics"] = {
                    "phase_timings": {
                        phase: _metric_summary(
                            [float(item["phase_timings"].get(phase, 0.0)) for item in diagnostics]
                        )
                        for phase in phase_names
                    },
                    "fallback_peaklets": [
                        int(item.get("fallback_peaklets", 0)) for item in diagnostics
                    ],
                    "used_compact_hmc": [
                        bool(item.get("used_compact_hmc", False)) for item in diagnostics
                    ],
                    "save_cache_applicable": all(
                        bool(item.get("save_cache_applicable", False)) for item in diagnostics
                    ),
                }
            targets[target] = target_summary
        sample_rss = []
        for sample in samples:
            selected_target = sample.get("target")
            if selected_target in sample["targets"]:
                selected_entry = sample["targets"][selected_target]
                sample_rss.append(selected_entry["rss"]["incremental_peak_bytes"])
            else:
                sample_rss.append(
                    max(
                        entry["rss"]["incremental_peak_bytes"]
                        for entry in sample["targets"].values()
                    )
                )
        return {
            "mode": mode,
            "targets": targets,
            "incremental_peak_rss_bytes": _metric_summary(sample_rss),
            "total_compute_sec": _metric_summary(
                [sample["total_compute_sec"] for sample in samples]
            ),
            "warmup_type": samples[0].get("warmup_type"),
            "warmup_elapsed_sec": _metric_summary(
                [float(sample.get("warmup_elapsed_sec", 0.0)) for sample in samples]
            ),
        }

    result = {
        "mode": mode,
        "elapsed_sec": _metric_summary([sample["elapsed_sec"] for sample in samples]),
        "incremental_peak_rss_bytes": _metric_summary(
            [sample["rss"]["incremental_peak_bytes"] for sample in samples]
        ),
        "targets": {
            target: {
                **output_summaries[target],
                "golden_consistent": golden_consistent[target],
                "golden_sha256": golden_sha256[target],
                **(
                    {
                        "paired_output": paired_summaries[target],
                        "offset_pool_contract": contract_summaries[target],
                    }
                    if paired_summaries[target] is not None
                    else {}
                ),
            }
            for target in target_names
        },
    }
    result["warmup_type"] = samples[0].get("warmup_type")
    result["warmup_elapsed_sec"] = _metric_summary(
        [float(sample.get("warmup_elapsed_sec", 0.0)) for sample in samples]
    )
    return result


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

    def target_scope(report: dict[str, Any]) -> tuple[str | None, set[str]]:
        summary = report.get("summary", {})
        compute_targets = summary.get("compute", {}).get("targets", {})
        end_to_end_targets = summary.get("end-to-end", {}).get("targets", {})
        declared_targets = report.get("targets")
        if declared_targets is None:
            target_set = set(compute_targets) | set(end_to_end_targets)
        else:
            target_set = {str(item) for item in declared_targets}
        declared_target = report.get("target")
        return (str(declared_target) if declared_target is not None else None, target_set)

    current_scope, current_target_set = target_scope(current)
    baseline_scope, baseline_target_set = target_scope(baseline)
    scope_matches = current_scope == baseline_scope and current_target_set == baseline_target_set
    _comparison_check(
        checks,
        name="target_scope",
        passed=scope_matches,
        current_target=current_scope,
        baseline_target=baseline_scope,
        current_targets=sorted(current_target_set),
        baseline_targets=sorted(baseline_target_set),
    )
    if not scope_matches:
        return {"passed": False, "checks": checks}

    target_names = [current_scope] if current_scope is not None else sorted(current_targets)

    def compare_target_outputs(
        current_mode_targets: dict[str, Any],
        baseline_mode_targets: dict[str, Any],
        targets: list[str],
    ) -> None:
        for target in targets:
            current_target = current_mode_targets.get(target)
            baseline_target = baseline_mode_targets.get(target)
            if current_target is None:
                # The selected target is the source of truth for a scoped
                # report; a missing current entry is always a failed check.
                current_hash = None
                baseline_hash = baseline_target.get("golden_sha256") if baseline_target else None
                consistent = False
            else:
                current_hash = current_target.get("golden_sha256")
                baseline_hash = baseline_target.get("golden_sha256") if baseline_target else None
                consistent = bool(
                    baseline_target
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

            if not current_target or not baseline_target:
                continue
            current_pair = current_target.get("paired_output")
            baseline_pair = baseline_target.get("paired_output")
            if current_pair is not None or baseline_pair is not None:
                current_pair_hash = current_pair.get("golden_sha256") if current_pair else None
                baseline_pair_hash = baseline_pair.get("golden_sha256") if baseline_pair else None
                pair_consistent = bool(
                    current_pair
                    and baseline_pair
                    and current_pair.get("golden_consistent")
                    and baseline_pair.get("golden_consistent")
                )
                _comparison_check(
                    checks,
                    name="paired_golden_hash",
                    target=target,
                    passed=bool(
                        current_pair_hash
                        and current_pair_hash == baseline_pair_hash
                        and pair_consistent
                    ),
                    current=current_pair_hash,
                    baseline=baseline_pair_hash,
                )

            contract = current_target.get("offset_pool_contract")
            if contract is not None:
                _comparison_check(
                    checks,
                    name="offset_pool_contract",
                    target=target,
                    passed=bool(contract.get("valid")),
                    current=contract,
                )

    if current_targets:
        compare_target_outputs(current_targets, baseline_targets, target_names)
    elif current_scope is not None:
        compare_target_outputs({}, baseline_targets, target_names)

    for target in target_names:
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
        threshold = COMPUTE_IMPROVEMENT_THRESHOLDS.get(target)
        if threshold is None:
            continue
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
        diagnostics = current_target.get("diagnostics", {}) if current_target else {}
        fallback_peaklets = diagnostics.get("fallback_peaklets")
        if fallback_peaklets is not None:
            _comparison_check(
                checks,
                name="fallback_peaklets",
                target=target,
                passed=bool(fallback_peaklets)
                and all(int(value) == 0 for value in fallback_peaklets),
                values=fallback_peaklets,
            )

    if current_compute and baseline_compute:
        total_variance = current_compute.get("total_compute_sec", {}).get("range_over_median")
        _comparison_check(
            checks,
            name="variance",
            target="total_compute",
            passed=total_variance is not None and total_variance <= MAX_RANGE_OVER_MEDIAN,
            range_over_median=total_variance,
            maximum=MAX_RANGE_OVER_MEDIAN,
        )

        if current_scope is not None:
            current_rss = (
                current_targets.get(current_scope, {})
                .get("incremental_peak_rss_bytes", {})
                .get("median")
            )
            baseline_rss = (
                baseline_targets.get(baseline_scope, {})
                .get("incremental_peak_rss_bytes", {})
                .get("median")
            )
        else:
            current_rss = current_compute.get("incremental_peak_rss_bytes", {}).get("median")
            baseline_rss = baseline_compute.get("incremental_peak_rss_bytes", {}).get("median")
        _comparison_check(
            checks,
            name="rss_regression",
            passed=(
                current_rss is not None
                and baseline_rss is not None
                and current_rss <= baseline_rss * 1.05
            ),
            current_median_bytes=current_rss,
            baseline_median_bytes=baseline_rss,
            maximum_ratio=1.05,
        )

    current_e2e = current_summary.get("end-to-end", {})
    baseline_e2e = baseline_summary.get("end-to-end", {})
    if current_e2e and baseline_e2e:
        current_e2e_targets = current_e2e.get("targets", {})
        baseline_e2e_targets = baseline_e2e.get("targets", {})
        if current_e2e_targets:
            compare_target_outputs(current_e2e_targets, baseline_e2e_targets, target_names)
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
    if getattr(args, "target", None):
        command.extend(["--target", str(args.target)])
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
    parser.add_argument(
        "--target",
        help=(
            "benchmark only one target; omit to preserve the historical full-pipeline run "
            "(peaklet_waveforms also reports its paired waveform pool)"
        ),
    )
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


def _samples_need_extension(samples: dict[str, list[dict[str, Any]]]) -> bool:
    """Return whether any measured mode exceeds the repeat-stability gate."""
    for mode_samples in samples.values():
        if not mode_samples:
            continue
        summary = aggregate_samples(mode_samples)
        if mode_samples[0].get("mode") == "compute":
            target_summaries = summary.get("targets", {}).values()
            if any(
                item.get("elapsed_sec", {}).get("range_over_median", 0.0) > MAX_RANGE_OVER_MEDIAN
                for item in target_summaries
            ):
                return True
            if (
                summary.get("total_compute_sec", {}).get("range_over_median", 0.0)
                > MAX_RANGE_OVER_MEDIAN
            ):
                return True
        elif summary.get("elapsed_sec", {}).get("range_over_median", 0.0) > MAX_RANGE_OVER_MEDIAN:
            return True
    return False


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

    available_targets = DIRECT_PIPELINE_TARGETS if args.direct_manifest else PIPELINE_TARGETS
    if args.target is not None and args.target not in available_targets:
        raise SystemExit(
            f"unsupported benchmark target {args.target!r}; choose one of "
            + ", ".join(available_targets)
        )
    if args.direct_manifest and args.target is not None:
        # Validate all paths, dtype/shape declarations, the selected dynamic
        # wave-pool dependency, config hash and lineage before starting any
        # worker. The actual benchmark workers repeat this validation too.
        try:
            _load_direct_manifest_with_metadata(
                args.direct_manifest,
                target=args.target,
                config=load_config(args.config_json),
            )
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc

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
    initial_repeats = args.repeats
    auto_extended = False
    extension_reason = None
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
        if args.repeats < 5 and _samples_need_extension(samples):
            auto_extended = True
            extension_reason = f"range_over_median>{MAX_RANGE_OVER_MEDIAN:.0%}"
            for mode in modes:
                for repeat_index in range(args.repeats, 5):
                    output_path = Path(tmpdir) / f"{mode}-{repeat_index}.json"
                    samples[mode].append(
                        _run_worker_subprocess(
                            args=args,
                            mode=mode,
                            repeat_index=repeat_index,
                            output_path=output_path,
                        )
                    )

    actual_repeats = max((len(mode_samples) for mode_samples in samples.values()), default=0)
    first_sample = next(
        (sample for mode_samples in samples.values() for sample in mode_samples), {}
    )

    payload = {
        "schema_version": 1,
        "run_id": args.run_id,
        "storage_dir": str(Path(args.storage_dir).resolve()) if args.storage_dir else None,
        "direct_manifest": (
            str(Path(args.direct_manifest).resolve()) if args.direct_manifest else None
        ),
        "config_json": str(Path(args.config_json).resolve()),
        "repeats": actual_repeats,
        "requested_repeats": initial_repeats,
        "repeat_policy": {
            "initial_repeats": initial_repeats,
            "max_repeats": 5,
            "auto_extended": auto_extended,
            "extension_reason": extension_reason,
            "stability_threshold_range_over_median": MAX_RANGE_OVER_MEDIAN,
            "extension_owner": "main_process",
        },
        "mode": args.mode,
        "target": args.target,
        "target_scope": "single" if args.target else "full_pipeline",
        "rss_sample_interval_sec": RSS_SAMPLE_INTERVAL_SEC,
        "targets": [args.target] if args.target else list(available_targets),
        "runtime_environment": first_sample.get("runtime_environment"),
        "warmup": {
            "type": first_sample.get("warmup_type"),
            "elapsed_sec": first_sample.get("warmup_elapsed_sec"),
        },
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
