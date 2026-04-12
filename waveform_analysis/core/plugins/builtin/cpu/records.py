"""
Records/wave_pool plugins backed by an internal shared RecordsBundle cache.
"""

from typing import Any, Optional

import numpy as np

from waveform_analysis.core.plugins.builtin.cpu._dt_compat import resolve_dt_config
from waveform_analysis.core.plugins.builtin.cpu.filtering import (
    FILTER_ENGINE_VERSION,
    build_filter_batches,
    filter_wave_pool_batch,
)
from waveform_analysis.core.plugins.builtin.cpu.waveforms import (
    _build_polarity_lookup,
    _validate_baseline_samples,
)
from waveform_analysis.core.plugins.core.base import Option, Plugin
from waveform_analysis.core.processing.dtypes import RECORDS_DTYPE
from waveform_analysis.core.processing.records_builder import (
    RecordsBundle,
    build_records_from_raw_files,
    build_records_from_v1725_files,
)

_BUNDLE_CACHE_NAME = "_records_bundle"


def get_records_bundle_cache_key(context: Any, run_id: str) -> str:
    """Return the internal memory-cache key used for the shared bundle."""
    data_name = "records"
    plugins = getattr(context, "_plugins", {})
    if data_name not in plugins and "wave_pool" in plugins:
        data_name = "wave_pool"
    bundle_key = context.key_for(run_id, data_name)
    return f"{_BUNDLE_CACHE_NAME}-{bundle_key}"


def _apply_records_polarity(context: Any, run_id: str, bundle: RecordsBundle) -> RecordsBundle:
    records = bundle.records
    if (
        records.dtype.names is None
        or "polarity" not in records.dtype.names
        or "board" not in records.dtype.names
        or "channel" not in records.dtype.names
    ):
        return bundle

    if len(records) == 0:
        return bundle

    records["polarity"] = "unknown"
    polarity_map = _build_polarity_lookup(context, run_id, records["board"], records["channel"])
    if not polarity_map:
        return bundle

    from waveform_analysis.core.hardware.channel import HardwareChannel

    for idx in range(len(records)):
        hw_channel = HardwareChannel(int(records["board"][idx]), int(records["channel"][idx]))
        records["polarity"][idx] = polarity_map.get(hw_channel, "unknown")
    return bundle


def _resolve_dt_ns(context: Any, plugin: Plugin, adapter_name: str | None = None) -> int:
    dt_ns = resolve_dt_config(
        context, plugin, deprecated_keys=("records_dt_ns", "dt_ns", "sampling_interval_ns")
    )
    if dt_ns is None:
        daq_adapter = adapter_name or context.config.get("daq_adapter")
        if daq_adapter:
            try:
                from waveform_analysis.utils.formats import get_adapter

                adapter = get_adapter(daq_adapter)
                sampling_rate = adapter.sampling_rate_hz
                if sampling_rate:
                    dt_ns = int(round(1e9 / float(sampling_rate)))
            except Exception:
                dt_ns = None

    if dt_ns is None:
        dt_ns = 1

    if dt_ns > np.iinfo(np.int32).max or dt_ns < 0:
        raise ValueError(f"records_dt_ns out of int32 range: {dt_ns}")
    return int(dt_ns)


def _resolve_adapter_name(context: Any, plugin: Plugin | None) -> str | None:
    adapter = None
    if plugin is not None and "daq_adapter" in plugin.options:
        adapter = context.get_config(plugin, "daq_adapter")
    if adapter is None:
        adapter = context.config.get("daq_adapter")
    if isinstance(adapter, str):
        return adapter.lower()
    return None


def _cleanup_stale_bundles(context: Any, run_id: str, keep_key: str) -> None:
    to_remove = []
    for (rid, name), value in context._results.items():
        if rid != run_id:
            continue
        if name == keep_key:
            continue
        if not isinstance(value, RecordsBundle):
            continue
        if not name.startswith(_BUNDLE_CACHE_NAME):
            continue
        to_remove.append((rid, name))

    for key in to_remove:
        del context._results[key]


def _build_records_bundle(
    context: Any,
    run_id: str,
    plugin: Plugin,
    adapter_name: str | None,
    part_size: int,
    dt_ns: int,
) -> RecordsBundle:
    cache_key = get_records_bundle_cache_key(context, run_id)
    cached = context._results.get((run_id, cache_key))
    if isinstance(cached, RecordsBundle):
        _cleanup_stale_bundles(context, run_id, cache_key)
        return cached

    if adapter_name == "v1725":
        raw_files = context.get_data(run_id, "raw_files")
        file_list = []
        for group in raw_files:
            if group:
                file_list.extend(group)
        # Remove duplicates but keep order
        seen = set()
        deduped = []
        for path in file_list:
            if path in seen:
                continue
            seen.add(path)
            deduped.append(path)

        bundle = build_records_from_v1725_files(deduped, dt_ns=dt_ns)
        bundle = _apply_records_polarity(context, run_id, bundle)
        context._set_data(run_id, cache_key, bundle)
        _cleanup_stale_bundles(context, run_id, cache_key)
        return bundle

    raw_files = context.get_data(run_id, "raw_files")
    if not isinstance(raw_files, list):
        raise ValueError("records expects raw_files as a list of per-channel file groups")

    baseline_samples = context.get_config(plugin, "baseline_samples")
    _validate_baseline_samples(baseline_samples)
    parse_engine = context.get_config(plugin, "parse_engine")
    n_jobs = context.get_config(plugin, "n_jobs")
    chunksize = context.get_config(plugin, "chunksize")
    use_process_pool = context.get_config(plugin, "use_process_pool")
    channel_workers = context.get_config(plugin, "channel_workers")
    channel_executor = context.get_config(plugin, "channel_executor")
    profiler = getattr(context, "profiler", None)

    epoch_ns = None
    if adapter_name:
        from pathlib import Path

        from waveform_analysis.utils.formats import get_adapter

        adapter = get_adapter(adapter_name)
        first_file = next((group[0] for group in raw_files if group), None)
        if first_file is not None:
            try:
                epoch_ns = adapter.get_file_epoch(Path(first_file))
            except (FileNotFoundError, OSError):
                epoch_ns = None

    bundle = build_records_from_raw_files(
        raw_files,
        adapter_name=adapter_name or "vx2730",
        default_dt_ns=dt_ns,
        part_size=part_size,
        baseline_samples=baseline_samples,
        epoch_ns=epoch_ns,
        show_progress=bool(context.config.get("show_progress", True)),
        parse_engine=parse_engine,
        n_jobs=n_jobs,
        chunksize=chunksize,
        use_process_pool=use_process_pool,
        channel_workers=channel_workers,
        channel_executor=channel_executor,
        profiler=profiler,
    )
    bundle = _apply_records_polarity(context, run_id, bundle)
    context._set_data(run_id, cache_key, bundle)
    _cleanup_stale_bundles(context, run_id, cache_key)
    return bundle


def _resolve_records_upstream_depends(context: Any, plugin: Plugin) -> list[str]:
    """Resolve the shared upstream inputs for records-backed derived products."""
    return ["raw_files"]


class _RecordsBundlePluginBase(Plugin):
    """Shared configuration and lineage for records-backed bundle outputs."""

    uses_run_config = True
    save_when = "always"
    options = {
        "daq_adapter": Option(
            default="vx2730",
            type=str,
            help="DAQ adapter name for records bundle (e.g., 'vx2730', 'v1725').",
        ),
        "channel_workers": Option(
            default=None,
            help="Workers for channel-level waveform loading (None=auto).",
            track=False,
        ),
        "channel_executor": Option(
            default="thread",
            type=str,
            help="Channel-level executor type: 'thread' or 'process'.",
            track=False,
        ),
        "n_jobs": Option(
            default=None,
            type=int,
            help="Workers per channel for file-level parsing (None=auto).",
            track=False,
        ),
        "use_process_pool": Option(
            default=False,
            type=bool,
            help="Use a process pool for file-level parsing (False=thread pool).",
            track=False,
        ),
        "chunksize": Option(
            default=None,
            type=int,
            help="CSV read chunk size; None reads full file (PyArrow if available).",
            track=False,
        ),
        "parse_engine": Option(
            default="auto",
            type=str,
            help="CSV engine: auto | polars | pyarrow | pandas",
            track=False,
        ),
        "records_part_size": Option(
            default=250_000,
            type=int,
            help="Max events per records shard; <=0 disables sharding.",
        ),
        "dt": Option(
            default=None,
            type=int,
            help="Sample interval in ns for records.dt (defaults to adapter rate or 1ns).",
        ),
        "baseline_samples": Option(
            default=None,
            type=None,
            validate=lambda v: (
                v is None
                or isinstance(v, int)
                or (
                    (isinstance(v, tuple) or isinstance(v, list))
                    and len(v) == 2
                    and all(isinstance(x, int) for x in v)
                )
            ),
            help="Baseline range: int (sample count from adapter start) or tuple (start, end) "
            "relative to samples_start. JSON lists like [0, 800] are also accepted. "
            "None=adapter default.",
        ),
    }
    version = "0.10.0"

    def resolve_depends_on(self, context: Any, run_id: str | None = None) -> list[str]:
        """Resolve raw-file upstream data for shared records bundle outputs."""
        return _resolve_records_upstream_depends(context, self)

    def get_lineage(self, context: Any) -> dict:
        adapter_name = _resolve_adapter_name(context, self)
        config = {}
        for key in self.config_keys:
            option = self.options.get(key)
            if option and getattr(option, "track", True):
                config[key] = context.get_config(self, key)
        if adapter_name:
            config["daq_adapter"] = adapter_name

        return {
            "plugin_class": self.__class__.__name__,
            "plugin_version": getattr(self, "version", "0.0.0"),
            "description": getattr(self, "description", ""),
            "config": config,
            "depends_on": self._build_depends_lineage(context),
            "dtype": np.dtype(self.output_dtype).descr,
        }


class RecordsPlugin(_RecordsBundlePluginBase):
    """Build records (event index table) from the shared internal bundle."""

    provides = "records"
    depends_on = []
    description = "Build records (event index table) from the shared internal records bundle."
    output_dtype = RECORDS_DTYPE

    def compute(self, context: Any, run_id: str, **kwargs) -> np.ndarray:
        bundle = get_records_bundle(context, run_id)
        return bundle.records


class WavePoolPlugin(_RecordsBundlePluginBase):
    """Expose wave_pool as a formal plugin output backed by RecordsBundle."""

    provides = "wave_pool"
    depends_on = []
    description = "Build wave_pool from the shared internal records bundle."
    output_dtype = np.dtype(np.uint16)

    def compute(self, context: Any, run_id: str, **kwargs) -> np.ndarray:
        bundle = get_records_bundle(context, run_id)
        return bundle.wave_pool


class WavePoolFilteredPlugin(Plugin):
    """Build a filtered wave_pool aligned to the existing records layout."""

    provides = "wave_pool_filtered"
    depends_on = ["records", "wave_pool"]
    description = "Build filtered wave_pool from records-backed raw waveforms."
    version = FILTER_ENGINE_VERSION
    save_when = "always"
    output_dtype = np.dtype(np.float32)
    options = {
        "filter_type": Option(default="SG", type=str, help="滤波器类型: 'BW' 或 'SG'"),
        "lowcut": Option(default=0.1, type=float, help="BW 低频截止"),
        "highcut": Option(default=0.5, type=float, help="BW 高频截止"),
        "fs": Option(default=0.5, type=float, help="BW 采样率（GHz）"),
        "filter_order": Option(default=4, type=int, help="BW 阶数"),
        "sg_window_size": Option(default=11, type=int, help="SG 窗口大小（奇数）"),
        "sg_poly_order": Option(default=2, type=int, help="SG 多项式阶数"),
        "max_workers": Option(
            default=None,
            type=int,
            help="并行工作线程数；None 使用 CPU 核心数，1 或 0 禁用并行",
        ),
        "batch_size": Option(
            default=0,
            type=int,
            help="每批次记录数（0 表示不分批，整个通道一次处理）",
        ),
        "channel_config": Option(
            default=None,
            type=dict,
            help="按 (board, channel) 的插件通道覆盖配置，可覆盖滤波参数。",
        ),
    }

    def compute(self, context: Any, run_id: str, **kwargs) -> np.ndarray:
        records = context.get_data(run_id, "records")
        wave_pool = context.get_data(run_id, "wave_pool")
        if not isinstance(records, np.ndarray):
            raise ValueError("wave_pool_filtered expects records as a structured array")
        if not isinstance(wave_pool, np.ndarray):
            raise ValueError("wave_pool_filtered expects wave_pool as a numpy array")
        if records.dtype.names is None:
            raise ValueError("wave_pool_filtered expects structured records input")
        required = ("wave_offset", "event_length")
        missing = [name for name in required if name not in records.dtype.names]
        if missing:
            raise ValueError(f"wave_pool_filtered records missing required fields: {missing}")

        filtered_pool = np.zeros(len(wave_pool), dtype=np.float32)
        if len(records) == 0 or len(wave_pool) == 0:
            return filtered_pool

        boards = (
            records["board"]
            if "board" in records.dtype.names
            else np.zeros(len(records), dtype=np.int16)
        )
        channels = (
            records["channel"]
            if "channel" in records.dtype.names
            else np.zeros(len(records), dtype=np.int16)
        )

        batch_size = int(context.get_config(self, "batch_size"))
        if batch_size < 0:
            raise ValueError(f"batch_size ({batch_size}) 必须大于等于 0")

        filter_batches = build_filter_batches(context, self, run_id, boards, channels, batch_size)
        if not filter_batches:
            return filtered_pool

        max_workers = context.get_config(self, "max_workers")
        allow_parallel = max_workers is None or (isinstance(max_workers, int) and max_workers > 1)
        use_parallel = allow_parallel and len(filter_batches) > 1

        tasks = [
            (
                records,
                wave_pool,
                batch_selector,
                filter_config["filter_type"],
                filter_config["bw_sos"],
                filter_config["sg_window_size"],
                filter_config["sg_poly_order"],
            )
            for _channel, batch_selector, filter_config in filter_batches
        ]
        if use_parallel:
            from waveform_analysis.core.execution.manager import parallel_map

            results = parallel_map(
                filter_wave_pool_batch,
                tasks,
                executor_type="thread",
                max_workers=max_workers,
                executor_name="wave_pool_filtered",
            )
        else:
            results = [filter_wave_pool_batch(task) for task in tasks]

        for batch_segments in results:
            for offset, filtered_wave in batch_segments:
                filtered_pool[offset : offset + len(filtered_wave)] = filtered_wave

        return filtered_pool


def get_records_bundle(context: Any, run_id: str) -> RecordsBundle:
    """Get records + wave_pool bundle for a run (internal cache).

    Records now build from raw_files for all adapters. Non-V1725 adapters use
    the generic incremental builder, while V1725 keeps its dedicated iter_waves
    path for compatibility and performance.
    """
    try:
        plugin = context.get_plugin("records")
    except Exception:
        plugin = context.get_plugin("wave_pool")
    adapter_name = _resolve_adapter_name(context, plugin)
    dt_ns = _resolve_dt_ns(context, plugin, adapter_name=adapter_name)
    part_size = context.get_config(plugin, "records_part_size")
    if part_size is None:
        part_size = plugin.options["records_part_size"].default
    return _build_records_bundle(
        context,
        run_id,
        plugin,
        adapter_name,
        part_size,
        dt_ns,
    )
