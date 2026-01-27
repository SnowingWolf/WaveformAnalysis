# -*- coding: utf-8 -*-
"""
Events plugins built on the records bundle.
"""

from typing import Any, List, Optional, Tuple

import numpy as np
import pandas as pd

from waveform_analysis.core.foundation.constants import FeatureDefaults
from waveform_analysis.core.foundation.utils import exporter
from waveform_analysis.core.plugins.core.base import Option, Plugin
from waveform_analysis.core.processing.records_builder import (
    EVENTS_DTYPE,
    RecordsBundle,
    build_records_from_st_waveforms_sharded,
    build_records_from_v1725_files,
)

export, __all__ = exporter()

_BUNDLE_CACHE_NAME = "_events_bundle"


def _bundle_cache_key(context: Any, run_id: str, plugin_name: str) -> str:
    key = context.key_for(run_id, plugin_name)
    return f"{_BUNDLE_CACHE_NAME}-{key}"


def _resolve_adapter_name(context: Any) -> Optional[str]:
    adapter = context.config.get("daq_adapter")
    if isinstance(adapter, str):
        return adapter.lower()
    return None


def _resolve_dt_ns(context: Any, plugin: Plugin, adapter_name: Optional[str] = None) -> int:
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
    value: Optional[Tuple[Optional[int], Optional[int]]],
    default_value: Tuple[Optional[int], Optional[int]],
) -> Tuple[int, Optional[int]]:
    if value is None:
        value = default_value
    if len(value) != 2:
        raise ValueError("range must be a tuple of (start, end)")
    start, end = value
    start = 0 if start is None else int(start)
    end = None if end is None else int(end)
    return start, end


def _slice_bounds(length: int, start: int, end: Optional[int]) -> Tuple[int, int]:
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
    peaks_range: Optional[Tuple[Optional[int], Optional[int]]],
    charge_range: Optional[Tuple[Optional[int], Optional[int]]],
) -> Tuple[np.ndarray, np.ndarray]:
    n_records = len(records)
    peaks = np.zeros(n_records, dtype=np.float64)
    charges = np.zeros(n_records, dtype=np.float64)

    p_start, p_end = _coerce_range(peaks_range, FeatureDefaults.PEAK_RANGE)
    c_start, c_end = _coerce_range(charge_range, FeatureDefaults.CHARGE_RANGE)

    for idx in range(n_records):
        length = int(records["event_length"][idx])
        if length <= 0:
            continue
        offset = int(records["wave_offset"][idx])
        wave = wave_pool[offset:offset + length]

        start, end = _slice_bounds(length, p_start, p_end)
        if start < end:
            segment = wave[start:end]
            peaks[idx] = float(segment.max() - segment.min())

        start, end = _slice_bounds(length, c_start, c_end)
        if start < end:
            baseline = float(records["baseline"][idx])
            segment = wave[start:end].astype(np.float64, copy=False)
            charges[idx] = float(np.sum(baseline - segment))

    return peaks, charges


def get_events_bundle(context: Any, run_id: str) -> RecordsBundle:
    """Get events + wave_pool bundle for a run (internal cache)."""
    plugin = context.get_plugin("events")
    adapter_name = _resolve_adapter_name(context)
    dt_ns = _resolve_dt_ns(context, plugin, adapter_name=adapter_name)
    part_size = context.get_config(plugin, "events_part_size")

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
        st_waveforms = context.get_data(run_id, "st_waveforms")
        bundle = build_records_from_st_waveforms_sharded(
            st_waveforms,
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
    depends_on = []
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
    }
    version = "0.1.0"

    def resolve_depends_on(self, context: Any, run_id: Optional[str] = None) -> List[str]:
        adapter_name = _resolve_adapter_name(context)
        if adapter_name == "v1725":
            return ["raw_files"]
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

        depends = {dep: context.get_lineage(dep) for dep in self.resolve_depends_on(context)}

        lineage = {
            "plugin_class": self.__class__.__name__,
            "plugin_version": getattr(self, "version", "0.0.0"),
            "description": getattr(self, "description", ""),
            "config": config,
            "depends_on": depends,
            "dtype": np.dtype(self.output_dtype).descr,
        }
        return lineage

    def compute(self, context: Any, run_id: str, **kwargs) -> np.ndarray:
        bundle = get_events_bundle(context, run_id)
        return bundle.records


@export
class EventFramePlugin(Plugin):
    """Build an events DataFrame from the events bundle."""

    provides = "events_df"
    depends_on = ["events"]
    save_when = "always"
    options = {
        "peaks_range": Option(
            default=FeatureDefaults.PEAK_RANGE,
            type=tuple,
            help="Peak range in samples (start, end); end=None uses full length.",
        ),
        "charge_range": Option(
            default=FeatureDefaults.CHARGE_RANGE,
            type=tuple,
            help="Charge range in samples (start, end); end=None uses full length.",
        ),
        "include_event_id": Option(
            default=True,
            type=bool,
            help="Include event_id column in events_df output.",
        ),
    }
    version = "0.1.0"

    def compute(self, context: Any, run_id: str, **kwargs) -> Any:
        bundle = get_events_bundle(context, run_id)
        records = bundle.records

        peaks_range = context.get_config(self, "peaks_range")
        charge_range = context.get_config(self, "charge_range")
        peaks, charges = _compute_event_features(
            records,
            bundle.wave_pool,
            peaks_range=peaks_range,
            charge_range=charge_range,
        )

        payload = {
            "timestamp": records["timestamp"],
            "charge": charges,
            "peak": peaks,
            "channel": records["channel"],
        }
        if context.get_config(self, "include_event_id"):
            payload["event_id"] = records["event_id"]

        df = pd.DataFrame(payload)
        return df.sort_values("timestamp")


@export
class EventsGroupedPlugin(Plugin):
    """Group events_df into multi-channel events by time window."""

    provides = "events_grouped"
    depends_on = ["events_df"]
    save_when = "always"
    options = {
        "time_window_ns": Option(
            default=100.0,
            type=float,
            help="Grouping window in ns (converted to ps internally).",
        ),
        "use_numba": Option(
            default=True,
            type=bool,
            help="Use numba-accelerated boundary search when available.",
        ),
        "n_processes": Option(
            default=None,
            type=int,
            help="Worker processes for grouping; None or <=1 disables it.",
        ),
    }
    version = "0.1.0"

    def compute(self, context: Any, run_id: str, **kwargs) -> Any:
        from waveform_analysis.core.processing.processor import group_multi_channel_hits

        df = context.get_data(run_id, "events_df")
        time_window_ns = context.get_config(self, "time_window_ns")
        use_numba = context.get_config(self, "use_numba")
        n_processes = context.get_config(self, "n_processes")
        return group_multi_channel_hits(
            df,
            time_window_ns=time_window_ns,
            use_numba=use_numba,
            n_processes=n_processes,
        )
