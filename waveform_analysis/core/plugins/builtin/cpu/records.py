# -*- coding: utf-8 -*-
"""
Records plugin with internal wave_pool bundle (CPU).
"""

from typing import Any, Optional

import numpy as np

from waveform_analysis.core.plugins.core.base import Option, Plugin
from waveform_analysis.core.processing.records import (
    RECORDS_DTYPE,
    RecordsBundle,
    build_records_from_st_waveforms_sharded,
    build_records_from_waveforms,
    build_records_from_v1725_files,
)

_BUNDLE_CACHE_NAME = "_records_bundle"
_RAW_BUNDLE_CACHE_NAME = "_records_raw_bundle"
_WAVE_BUNDLE_CACHE_NAME = "_records_wave_bundle"


def _bundle_cache_key(context: Any, run_id: str) -> str:
    st_key = context.key_for(run_id, "st_waveforms")
    return f"{_BUNDLE_CACHE_NAME}-{st_key}"


def _raw_bundle_cache_key(context: Any, run_id: str, adapter_name: str) -> str:
    raw_key = context.key_for(run_id, "raw_files")
    return f"{_RAW_BUNDLE_CACHE_NAME}-{adapter_name}-{raw_key}"


def _wave_bundle_cache_key(context: Any, run_id: str, adapter_name: str) -> str:
    wave_key = context.key_for(run_id, "waveforms")
    return f"{_WAVE_BUNDLE_CACHE_NAME}-{adapter_name}-{wave_key}"


def _resolve_dt_ns(context: Any, plugin: Plugin, adapter_name: Optional[str] = None) -> int:
    dt_ns = context.get_config(plugin, "records_dt_ns")
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


def _resolve_adapter_name(context: Any) -> Optional[str]:
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
        if not (
            name.startswith(_BUNDLE_CACHE_NAME)
            or name.startswith(_RAW_BUNDLE_CACHE_NAME)
            or name.startswith(_WAVE_BUNDLE_CACHE_NAME)
        ):
            continue
        to_remove.append((rid, name))

    for key in to_remove:
        del context._results[key]


def _get_records_bundle(context: Any, run_id: str, part_size: int, dt_ns: int) -> RecordsBundle:
    cache_key = _bundle_cache_key(context, run_id)
    cached = context._results.get((run_id, cache_key))
    if isinstance(cached, RecordsBundle):
        _cleanup_stale_bundles(context, run_id, cache_key)
        return cached

    st_waveforms = context.get_data(run_id, "st_waveforms")
    bundle = build_records_from_st_waveforms_sharded(
        st_waveforms,
        part_size=part_size,
        default_dt_ns=dt_ns,
    )
    context._set_data(run_id, cache_key, bundle)
    _cleanup_stale_bundles(context, run_id, cache_key)
    return bundle


def _get_raw_records_bundle(
    context: Any,
    run_id: str,
    adapter_name: str,
    dt_ns: int,
) -> RecordsBundle:
    cache_key = _raw_bundle_cache_key(context, run_id, adapter_name)
    cached = context._results.get((run_id, cache_key))
    if isinstance(cached, RecordsBundle):
        _cleanup_stale_bundles(context, run_id, cache_key)
        return cached

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
    context._set_data(run_id, cache_key, bundle)
    _cleanup_stale_bundles(context, run_id, cache_key)
    return bundle


def _get_wave_records_bundle(
    context: Any,
    run_id: str,
    adapter_name: str,
    dt_ns: int,
) -> RecordsBundle:
    cache_key = _wave_bundle_cache_key(context, run_id, adapter_name)
    cached = context._results.get((run_id, cache_key))
    if isinstance(cached, RecordsBundle):
        _cleanup_stale_bundles(context, run_id, cache_key)
        return cached

    waveforms = context.get_data(run_id, "waveforms")
    bundle = build_records_from_waveforms(waveforms, dt_ns=dt_ns)
    context._set_data(run_id, cache_key, bundle)
    _cleanup_stale_bundles(context, run_id, cache_key)
    return bundle


class RecordsPlugin(Plugin):
    """Build records (event index table) from st_waveforms."""

    provides = "records"
    depends_on = ["raw_files"]
    save_when = "always"
    output_dtype = RECORDS_DTYPE
    options = {
        "records_part_size": Option(
            default=200_000,
            type=int,
            help="Max events per records shard; <=0 disables sharding.",
        ),
        "records_dt_ns": Option(
            default=None,
            type=int,
            help="Sample interval in ns (defaults to DAQ adapter rate or 1ns).",
        ),
    }
    version = "0.2.0"

    def get_lineage(self, context: Any) -> dict:
        adapter_name = _resolve_adapter_name(context)
        config = {}
        for key in self.config_keys:
            option = self.options.get(key)
            if option and getattr(option, "track", True):
                config[key] = context.get_config(self, key)
        if adapter_name:
            config["daq_adapter"] = adapter_name

        if adapter_name == "v1725":
            depends = {"raw_files": context.get_lineage("raw_files")}
        else:
            depends = {"st_waveforms": context.get_lineage("st_waveforms")}

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
        bundle = get_records_bundle(context, run_id)
        return bundle.records


def get_records_bundle(context: Any, run_id: str) -> RecordsBundle:
    """Get records + wave_pool bundle for a run (internal cache)."""
    plugin = context.get_plugin("records")
    adapter_name = _resolve_adapter_name(context)
    dt_ns = _resolve_dt_ns(context, plugin, adapter_name=adapter_name)

    if adapter_name == "v1725":
        return _get_raw_records_bundle(context, run_id, adapter_name, dt_ns)

    part_size = context.get_config(plugin, "records_part_size")
    return _get_records_bundle(context, run_id, part_size, dt_ns)
