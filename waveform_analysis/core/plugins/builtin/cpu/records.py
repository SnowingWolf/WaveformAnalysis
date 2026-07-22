"""
Records/wave_pool plugins backed by an internal shared RecordsBundle cache.
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from waveform_analysis.core.plugins.builtin.cpu._dt_compat import resolve_dt_config
from waveform_analysis.core.plugins.builtin.cpu.filtering import (
    FILTER_ENGINE_VERSION,
    build_filter_batches,
    filter_wave_pool_batch,
)
from waveform_analysis.core.plugins.builtin.cpu.waveforms import (
    _build_polarity_lookup,
)
from waveform_analysis.core.plugins.core.base import Option, Plugin
from waveform_analysis.core.processing.dtypes import RECORDS_DTYPE
from waveform_analysis.core.processing.records_builder import (
    RecordsBundle,
    RecordsBundleRef,
    build_records_from_raw_files,
    build_records_from_st_waveforms_sharded,
    build_records_from_v1725_files,
)
from waveform_analysis.core.utils.baseline import (
    validate_baseline_samples as _validate_baseline_samples,
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


def _records_from_bundle(bundle: RecordsBundle | RecordsBundleRef) -> np.ndarray:
    if isinstance(bundle, RecordsBundleRef):
        if len(bundle.part_refs) != 1:
            return bundle.get_records_view()
        part = bundle.part_refs[0]
        return np.memmap(part.records_path, dtype=RECORDS_DTYPE, mode="r+", shape=(part.n_records,))
    return bundle.records


def _wave_pool_from_bundle(bundle: RecordsBundle | RecordsBundleRef) -> np.ndarray:
    if isinstance(bundle, RecordsBundleRef):
        if len(bundle.part_refs) != 1:
            raise ValueError("wave_pool requires a merged single-part RecordsBundleRef")
        part = bundle.part_refs[0]
        return np.memmap(
            part.wave_pool_path,
            dtype=np.uint16,
            mode="r",
            shape=(part.n_samples,),
        )
    return bundle.wave_pool


def _apply_records_polarity(
    context: Any,
    run_id: str,
    bundle: RecordsBundle | RecordsBundleRef,
) -> RecordsBundle | RecordsBundleRef:
    records = _records_from_bundle(bundle)
    names = records.dtype.names
    if names is None or "polarity" not in names or "board" not in names or "channel" not in names:
        return bundle

    if len(records) == 0:
        return bundle

    records["polarity"] = "unknown"
    polarity_map = _build_polarity_lookup(context, run_id, records["board"], records["channel"])
    if not polarity_map:
        return bundle

    from waveform_analysis.core.hardware.channel import HardwareChannel

    boards = records["board"]
    channels = records["channel"]

    # 向量化实现：使用 np.unique 的 return_inverse 参数一次性分组和赋值
    pairs = np.empty(
        len(records),
        dtype=[("board", boards.dtype), ("channel", channels.dtype)],
    )
    pairs["board"] = boards
    pairs["channel"] = channels

    # 获取唯一对及其逆索引映射（inverse_indices[i] 表示 records[i] 对应 unique_pairs 的索引）
    unique_pairs, inverse_indices = np.unique(pairs, return_inverse=True)

    # 为每个唯一的 (board, channel) 构建极性查找数组
    polarity_lookup = np.full(len(unique_pairs), "unknown", dtype=records["polarity"].dtype)
    for idx, pair in enumerate(unique_pairs):
        hw_ch = HardwareChannel(int(pair["board"]), int(pair["channel"]))
        polarity = polarity_map.get(hw_ch, "unknown")
        polarity_lookup[idx] = polarity

    # 向量化赋值：通过 inverse_indices 一次性映射所有记录的极性
    records["polarity"] = polarity_lookup[inverse_indices]
    flush = getattr(records, "flush", None)
    if callable(flush):
        flush()

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


def _parse_utc_epoch_ns(value: Any) -> int | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        return None
    dt_utc = dt.astimezone(timezone.utc)
    return int(round(dt_utc.timestamp() * 1_000_000_000))


def _resolve_run_start_epoch_ns(context: Any, run_id: str) -> int | None:
    get_run_config = getattr(context, "get_run_config", None)
    if not callable(get_run_config):
        return None
    try:
        run_config = get_run_config(run_id)
    except Exception:
        return None
    if not isinstance(run_config, dict):
        return None
    daq = run_config.get("daq")
    if not isinstance(daq, dict):
        return None
    return _parse_utc_epoch_ns(daq.get("start_time"))


def _resolve_file_epoch_ns(adapter_name: str | None, raw_files: list) -> int | None:
    if not adapter_name:
        return None

    from waveform_analysis.utils.formats import get_adapter

    adapter = get_adapter(adapter_name)
    first_file = next((group[0] for group in raw_files if group), None)
    if first_file is None:
        return None
    try:
        return adapter.get_file_epoch(Path(first_file))
    except (FileNotFoundError, OSError):
        return None


def _cleanup_stale_bundles(context: Any, run_id: str, keep_key: str) -> None:
    to_remove = []
    for (rid, name), value in context._results.items():
        if rid != run_id:
            continue
        if name == keep_key:
            continue
        if not isinstance(value, RecordsBundle | RecordsBundleRef):
            continue
        if not name.startswith(_BUNDLE_CACHE_NAME):
            continue
        to_remove.append((rid, name))

    for key in to_remove:
        value = context._results.pop(key)
        cleanup = getattr(value, "cleanup", None)
        if callable(cleanup):
            cleanup()


def _resolve_bundle_config_plugin(context: Any, plugin: Plugin) -> Plugin:
    """Return the plugin whose config controls the shared records bundle."""
    if getattr(plugin, "provides", None) == "wave_pool":
        records_plugin = getattr(context, "_plugins", {}).get("records")
        if records_plugin is not None:
            return records_plugin
    return plugin


def _build_records_bundle(
    context: Any,
    run_id: str,
    plugin: Plugin,
    adapter_name: str | None,
    part_size: int,
    dt_ns: int,
) -> RecordsBundle | RecordsBundleRef:
    cache_key = get_records_bundle_cache_key(context, run_id)
    cached = context._results.get((run_id, cache_key))
    if isinstance(cached, RecordsBundle | RecordsBundleRef):
        return cached

    input_source = str(context.get_config(plugin, "input_source") or "raw_files").lower()
    if input_source not in {"raw_files", "st_waveforms"}:
        raise ValueError(
            f"Invalid records input_source: {input_source!r}. "
            "Expected 'raw_files' or 'st_waveforms'."
        )
    if adapter_name == "v1725" and input_source == "st_waveforms":
        raise ValueError("records input_source='st_waveforms' is not supported for v1725")

    # V1725 采集卡路径
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

        # 获取并行配置
        n_jobs = context.get_config(plugin, "n_jobs")
        channel_executor = context.get_config(plugin, "channel_executor")
        v1725_part_size = context.get_config(plugin, "v1725_part_size")
        keep_on_disk = context.get_config(plugin, "keep_on_disk")
        memory_budget_gb = context.get_config(plugin, "memory_budget_gb")
        profiler = getattr(context, "profiler", None)

        bundle = build_records_from_v1725_files(
            deduped,
            dt_ns=dt_ns,
            n_jobs=n_jobs,
            executor_type=channel_executor,
            v1725_part_size=v1725_part_size,
            keep_on_disk=True if keep_on_disk is None else bool(keep_on_disk),
            memory_budget_gb=memory_budget_gb,
            show_progress=bool(context.config.get("show_progress", True)),
            profiler=profiler,
        )
        bundle = _apply_records_polarity(context, run_id, bundle)
        context._set_data(run_id, cache_key, bundle)
        _cleanup_stale_bundles(context, run_id, cache_key)
        return bundle

    if input_source == "st_waveforms":
        st_waveforms = context.get_data(run_id, "st_waveforms", output="array")
        bundle = build_records_from_st_waveforms_sharded(
            st_waveforms,
            part_size=part_size,
            default_dt_ns=dt_ns,
        )
        bundle = _apply_records_polarity(context, run_id, bundle)
        context._set_data(run_id, cache_key, bundle)
        _cleanup_stale_bundles(context, run_id, cache_key)
        return bundle

    # 通用适配器路径：从 raw_files 构建 RecordsBundle，适用于非 V1725 适配器
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

    epoch_ns = _resolve_run_start_epoch_ns(context, run_id)
    if epoch_ns is None:
        epoch_ns = _resolve_file_epoch_ns(adapter_name, raw_files)

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
    plugin = _resolve_bundle_config_plugin(context, plugin)
    input_source = str(context.get_config(plugin, "input_source") or "raw_files").lower()
    if input_source == "st_waveforms":
        adapter_name = _resolve_adapter_name(context, plugin)
        if adapter_name == "v1725":
            raise ValueError("records input_source='st_waveforms' is not supported for v1725")
        return ["st_waveforms"]
    if input_source != "raw_files":
        raise ValueError(
            f"Invalid records input_source: {input_source!r}. "
            "Expected 'raw_files' or 'st_waveforms'."
        )
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
            help="Executor type for channel-level loading and records merge: 'thread' or 'process'.",
            track=False,
        ),
        "n_jobs": Option(
            default=None,
            type=int,
            help="Workers per channel for file-level parsing; V1725 None=auto caps file readers at 4.",
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
        "v1725_part_size": Option(
            default=100_000,
            type=int,
            help="Max V1725 waves per per-file records shard; <=0 uses one shard per file.",
        ),
        "keep_on_disk": Option(
            default=None,
            type=None,
            validate=lambda v: v is None or isinstance(v, bool),
            help="Keep merged records bundle disk-backed. None defaults to True for V1725 and False otherwise.",
        ),
        "memory_budget_gb": Option(
            default=50.0,
            type=float,
            help="Memory budget in GB for in-memory records bundle materialization.",
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
        "input_source": Option(
            default="raw_files",
            type=str,
            help="Input source for records bundle: 'raw_files' or 'st_waveforms'. "
            "Use 'st_waveforms' for the materialized waveform path.",
        ),
    }
    version = "0.14.1"

    def resolve_depends_on(self, context: Any, run_id: str | None = None) -> list[str]:
        """Resolve raw-file upstream data for shared records bundle outputs."""
        return _resolve_records_upstream_depends(context, self)

    #
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
    options = {
        **_RecordsBundlePluginBase.options,
        "channel_workers": Option(
            default=16,
            help="Workers for channel-level waveform loading.",
            track=False,
        ),
        "channel_executor": Option(
            default="process",
            type=str,
            help="Executor type for channel-level loading and records merge: 'thread' or 'process'.",
            track=False,
        ),
        "n_jobs": Option(
            default=16,
            type=int,
            help="Workers per channel for file-level parsing; V1725 None=auto caps file readers at 4.",
            track=False,
        ),
        "use_process_pool": Option(
            default=True,
            type=bool,
            help="Use a process pool for file-level parsing (False=thread pool).",
            track=False,
        ),
        "v1725_part_size": Option(
            default=20_000,
            type=int,
            help="Max V1725 waves per per-file records shard; <=0 uses one shard per file.",
        ),
        "keep_on_disk": Option(
            default=True,
            type=None,
            validate=lambda v: v is None or isinstance(v, bool),
            help="Keep merged records bundle disk-backed. None defaults to True for V1725 and False otherwise.",
        ),
    }

    def compute(self, context: Any, run_id: str, **kwargs) -> np.ndarray:
        bundle = get_records_bundle(context, run_id)
        return _records_from_bundle(bundle)


class WavePoolPlugin(_RecordsBundlePluginBase):
    """Expose wave_pool as a formal plugin output backed by RecordsBundle."""

    provides = "wave_pool"
    depends_on = []
    description = "Build wave_pool from the shared internal records bundle."
    output_dtype = np.dtype(np.uint16)

    def compute(self, context: Any, run_id: str, **kwargs) -> np.ndarray:
        bundle = get_records_bundle(context, run_id)
        return _wave_pool_from_bundle(bundle)


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
