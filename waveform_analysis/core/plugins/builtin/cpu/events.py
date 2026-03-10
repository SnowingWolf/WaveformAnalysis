"""
Events plugins built on the records bundle.
"""

import logging
from typing import Any, Optional

import numpy as np

from waveform_analysis.core.foundation.constants import FeatureDefaults
from waveform_analysis.core.foundation.utils import exporter
from waveform_analysis.core.plugins.core.base import Option, Plugin
from waveform_analysis.core.processing.dtypes import EVENTS_DTYPE
from waveform_analysis.core.processing.records_builder import (
    RecordsBundle,
    build_records_from_st_waveforms_sharded,
    build_records_from_v1725_files,
)

export, __all__ = exporter()
logger = logging.getLogger(__name__)

_BUNDLE_CACHE_NAME = "_events_bundle"


def _bundle_cache_key(context: Any, run_id: str, plugin_name: str) -> str:
    key = context.key_for(run_id, plugin_name)
    return f"{_BUNDLE_CACHE_NAME}-{key}"


def _resolve_adapter_name(context: Any) -> str | None:
    adapter = context.config.get("daq_adapter")
    if isinstance(adapter, str):
        return adapter.lower()
    return None


def _resolve_dt_ns(context: Any, plugin: Plugin, adapter_name: str | None = None) -> int:
    dt_ns = context.get_config(plugin, "events_dt_ns")
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
        raise ValueError(f"events_dt_ns out of int32 range: {dt_ns}")
    return int(dt_ns)


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


def _flatten_raw_files(raw_files: Any) -> list:
    file_list = []
    for group in raw_files:
        if group:
            file_list.extend(group)

    seen = set()
    deduped = []
    for path in file_list:
        if path in seen:
            continue
        seen.add(path)
        deduped.append(path)
    return deduped


def _coerce_range(
    value: tuple[int | None, int | None] | None,
    default_value: tuple[int | None, int | None],
) -> tuple[int, int | None]:
    if value is None:
        value = default_value
    if len(value) != 2:
        raise ValueError("range must be a tuple of (start, end)")
    start, end = value
    start = 0 if start is None else int(start)
    end = None if end is None else int(end)
    return start, end


def _slice_bounds(length: int, start: int, end: int | None) -> tuple[int, int]:
    if start < 0:
        start = 0
    if end is None or end > length:
        end = length
    if start > length:
        start = length
    return start, end


def _compute_event_features(
    records: np.ndarray,
    wave_pool: np.ndarray,
    peaks_range: tuple[int | None, int | None] | None,
    charge_range: tuple[int | None, int | None] | None,
    fixed_baseline: dict | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    n_records = len(records)
    heights = np.zeros(n_records, dtype=np.float64)
    amps = np.zeros(n_records, dtype=np.float64)
    areas = np.zeros(n_records, dtype=np.float64)

    p_start, p_end = _coerce_range(peaks_range, FeatureDefaults.PEAK_RANGE)
    c_start, c_end = _coerce_range(charge_range, FeatureDefaults.CHARGE_RANGE)

    for idx in range(n_records):
        length = int(records["event_length"][idx])
        if length <= 0:
            continue
        offset = int(records["wave_offset"][idx])
        wave = wave_pool[offset : offset + length]
        ch = int(records["channel"][idx])
        if fixed_baseline and ch in fixed_baseline:
            baseline = float(fixed_baseline[ch])
        else:
            baseline = float(records["baseline"][idx])

        start, end = _slice_bounds(length, p_start, p_end)
        if start < end:
            segment = wave[start:end]
            heights[idx] = baseline - float(segment.min())
            amps[idx] = float(segment.max() - segment.min())

        start, end = _slice_bounds(length, c_start, c_end)
        if start < end:
            segment = wave[start:end].astype(np.float64, copy=False)
            areas[idx] = float(np.sum(baseline - segment))

    return heights, amps, areas


def get_events_bundle(context: Any, run_id: str) -> RecordsBundle:
    """Get events + wave_pool bundle for a run (internal cache)."""
    plugin = context.get_plugin("events")
    adapter_name = _resolve_adapter_name(context)
    dt_ns = _resolve_dt_ns(context, plugin, adapter_name=adapter_name)
    part_size = context.get_config(plugin, "events_part_size")
    use_filtered = context.get_config(plugin, "use_filtered")

    cache_key = _bundle_cache_key(context, run_id, plugin.provides)
    cached = context._results.get((run_id, cache_key))
    if isinstance(cached, RecordsBundle):
        _cleanup_stale_bundles(context, run_id, cache_key)
        return cached

    if adapter_name == "v1725":
        raw_files = context.get_data(run_id, "raw_files")
        file_list = _flatten_raw_files(raw_files)
        bundle = build_records_from_v1725_files(file_list, dt_ns=dt_ns)
    else:
        # 根据 use_filtered 选择数据源
        if use_filtered:
            waveform_data = context.get_data(run_id, "filtered_waveforms")
        else:
            waveform_data = context.get_data(run_id, "st_waveforms")
        bundle = build_records_from_st_waveforms_sharded(
            waveform_data,
            part_size=part_size,
            default_dt_ns=dt_ns,
        )

    context._set_data(run_id, cache_key, bundle)
    _cleanup_stale_bundles(context, run_id, cache_key)
    return bundle


@export
class EventsPlugin(Plugin):
    """Provide event index data backed by the records bundle."""

    provides = "events"
    depends_on = []  # 动态依赖，由 resolve_depends_on 决定
    save_when = "always"
    output_dtype = EVENTS_DTYPE
    options = {
        "events_part_size": Option(
            default=200_000,
            type=int,
            help="Max events per shard in the records bundle; <=0 disables sharding.",
        ),
        "events_dt_ns": Option(
            default=None,
            type=int,
            help="Sample interval in ns (defaults to adapter rate or 1ns).",
        ),
        "use_filtered": Option(
            default=False,
            type=bool,
            help="是否使用 filtered_waveforms（需要先注册 FilteredWaveformsPlugin）",
        ),
    }
    version = "2.0.0"  # 版本升级：支持动态依赖切换

    def resolve_depends_on(self, context: Any, run_id: str | None = None) -> list[str]:
        adapter_name = _resolve_adapter_name(context)
        if adapter_name == "v1725":
            return ["raw_files"]
        # 根据 use_filtered 动态选择依赖
        if context.get_config(self, "use_filtered"):
            return ["filtered_waveforms"]
        return ["st_waveforms"]

    def get_lineage(self, context: Any) -> dict:
        adapter_name = _resolve_adapter_name(context)
        config = {}
        for key in self.config_keys:
            option = self.options.get(key)
            if option and getattr(option, "track", True):
                config[key] = context.get_config(self, key)
        if adapter_name:
            config["daq_adapter"] = adapter_name

        lineage = {
            "plugin_class": self.__class__.__name__,
            "plugin_version": getattr(self, "version", "0.0.0"),
            "description": getattr(self, "description", ""),
            "config": config,
            "depends_on": self._build_depends_lineage(context),
            "dtype": np.dtype(self.output_dtype).descr,
        }
        return lineage

    def compute(self, context: Any, run_id: str, **kwargs) -> np.ndarray:
        bundle = get_events_bundle(context, run_id)
        return bundle.records
