# -*- coding: utf-8 -*-
"""
Records plugin with internal wave_pool bundle (CPU).
"""

from pathlib import Path
from typing import Any, Optional

import numpy as np

from waveform_analysis.core.plugins.core.base import Option, Plugin
from waveform_analysis.core.processing.dtypes import RECORDS_DTYPE
from waveform_analysis.core.processing.records_builder import (
    RecordsBundle,
    build_records_from_st_waveforms_sharded,
    build_records_from_v1725_files,
)
from waveform_analysis.core.plugins.builtin.cpu.waveforms import WaveformStruct, WaveformStructConfig

_BUNDLE_CACHE_NAME = "_records_bundle"


def _bundle_cache_key(context: Any, run_id: str) -> str:
    records_key = context.key_for(run_id, "records")
    return f"{_BUNDLE_CACHE_NAME}-{records_key}"


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


def _resolve_adapter_name(context: Any, plugin: Optional[Plugin]) -> Optional[str]:
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


def _resolve_epoch_ns(adapter_name: Optional[str], raw_files: list) -> Optional[int]:
    if not adapter_name or not raw_files or not raw_files[0]:
        return None

    try:
        from waveform_analysis.utils.formats import get_adapter

        adapter = get_adapter(adapter_name)
        first_file = Path(raw_files[0][0])
        return adapter.get_file_epoch(first_file)
    except Exception:
        return None


def _load_waveforms_for_records(
    context: Any,
    raw_files: list,
    plugin: Plugin,
    adapter_name: Optional[str],
) -> list:
    if not raw_files:
        return []

    from waveform_analysis.core.processing.loader import get_waveforms

    return get_waveforms(
        raw_filess=raw_files,
        n_channels=len(raw_files),
        show_progress=context.config.get("show_progress", True),
        channel_workers=context.get_config(plugin, "channel_workers"),
        channel_executor=context.get_config(plugin, "channel_executor"),
        n_jobs=context.get_config(plugin, "n_jobs"),
        use_process_pool=context.get_config(plugin, "use_process_pool"),
        chunksize=context.get_config(plugin, "chunksize"),
        daq_adapter=adapter_name,
    )


def _build_records_bundle(
    context: Any,
    run_id: str,
    plugin: Plugin,
    adapter_name: Optional[str],
    part_size: int,
    dt_ns: int,
) -> RecordsBundle:
    cache_key = _bundle_cache_key(context, run_id)
    cached = context._results.get((run_id, cache_key))
    if isinstance(cached, RecordsBundle):
        _cleanup_stale_bundles(context, run_id, cache_key)
        return cached

    raw_files = context.get_data(run_id, "raw_files")

    if adapter_name == "v1725":
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

    waveforms = _load_waveforms_for_records(context, raw_files, plugin, adapter_name)
    if adapter_name:
        config = WaveformStructConfig.from_adapter(adapter_name)
    else:
        config = WaveformStructConfig.default_vx2730()
    config.epoch_ns = _resolve_epoch_ns(adapter_name, raw_files)

    waveform_struct = WaveformStruct(waveforms, config=config)
    st_waveforms = waveform_struct.structure_waveforms(
        show_progress=context.config.get("show_progress", True),
    )

    bundle = build_records_from_st_waveforms_sharded(
        st_waveforms,
        part_size=part_size,
        default_dt_ns=dt_ns,
    )
    context._set_data(run_id, cache_key, bundle)
    _cleanup_stale_bundles(context, run_id, cache_key)
    return bundle


class RecordsPlugin(Plugin):
    """Build records (event index table) from raw_files."""

    provides = "records"
    depends_on = ["raw_files"]
    save_when = "always"
    output_dtype = RECORDS_DTYPE
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
        "records_part_size": Option(
            default=200_000,
            type=int,
            help="Max events per records shard; <=0 disables sharding.",
        ),
        "records_dt_ns": Option(
            default=None,
            type=int,
            help="Sample interval in ns (defaults to adapter rate or 1ns).",
        ),
    }
    version = "0.4.0"

    def get_lineage(self, context: Any) -> dict:
        adapter_name = _resolve_adapter_name(context, self)
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
        bundle = get_records_bundle(context, run_id)
        return bundle.records


def get_records_bundle(context: Any, run_id: str) -> RecordsBundle:
    """Get records + wave_pool bundle for a run (internal cache)."""
    plugin = context.get_plugin("records")
    adapter_name = _resolve_adapter_name(context, plugin)
    dt_ns = _resolve_dt_ns(context, plugin, adapter_name=adapter_name)
    part_size = context.get_config(plugin, "records_part_size")
    return _build_records_bundle(
        context,
        run_id,
        plugin,
        adapter_name,
        part_size,
        dt_ns,
    )
