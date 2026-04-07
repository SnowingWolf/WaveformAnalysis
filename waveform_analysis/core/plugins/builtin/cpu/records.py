"""
Records plugin with internal wave_pool bundle (CPU).
"""

from typing import Any, Optional

import numpy as np

from waveform_analysis.core.plugins.builtin.cpu._dt_compat import resolve_dt_config
from waveform_analysis.core.plugins.builtin.cpu.waveforms import (
    _build_polarity_lookup,
)
from waveform_analysis.core.plugins.core.base import Option, Plugin
from waveform_analysis.core.processing.dtypes import RECORDS_DTYPE
from waveform_analysis.core.processing.records_builder import (
    RecordsBundle,
    build_records_from_st_waveforms_sharded,
    build_records_from_v1725_files,
)

_BUNDLE_CACHE_NAME = "_records_bundle"


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


def _bundle_cache_key(context: Any, run_id: str) -> str:
    records_key = context.key_for(run_id, "records")
    return f"{_BUNDLE_CACHE_NAME}-{records_key}"


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
        bundle = _apply_records_polarity(context, run_id, bundle)
        context._set_data(run_id, cache_key, bundle)
        _cleanup_stale_bundles(context, run_id, cache_key)
        return bundle

    st_waveforms = context.get_data(run_id, "st_waveforms")
    if not isinstance(st_waveforms, np.ndarray):
        raise ValueError("records expects st_waveforms as a single structured array")

    bundle = build_records_from_st_waveforms_sharded(
        st_waveforms,
        part_size=part_size,
        default_dt_ns=dt_ns,
    )
    del st_waveforms
    bundle = _apply_records_polarity(context, run_id, bundle)
    context._set_data(run_id, cache_key, bundle)
    _cleanup_stale_bundles(context, run_id, cache_key)
    return bundle


class RecordsPlugin(Plugin):
    """Build records (event index table) from raw_files."""

    provides = "records"
    depends_on = []
    uses_run_config = True
    description = "Build records (event index table) from raw_files."
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
        "dt": Option(
            default=None,
            type=int,
            help="Sample interval in ns for records.dt (defaults to adapter rate or 1ns).",
        ),
    }
    version = "0.8.1"

    def resolve_depends_on(self, context: Any, run_id: str | None = None) -> list[str]:
        """Resolve adapter-specific upstream data for records.

        Upstream data differs by adapter:

        - Non-V1725 adapters, including VX2730: st_waveforms -> records
        - V1725 adapter: raw_files -> records

        This is why RecordsPlugin and WaveformsPlugin should be registered in
        the same plugin set: users may switch adapters, but the valid upstream
        for records changes with the adapter.
        """
        adapter_name = _resolve_adapter_name(context, self)
        if adapter_name == "v1725":
            return ["raw_files"]
        return ["st_waveforms"]

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
    """Get records + wave_pool bundle for a run (internal cache).

    For non-V1725 adapters, records reuse the already-resolved st_waveforms
    result instead of reparsing raw files. V1725 keeps its dedicated raw-file
    path for compatibility and performance.
    """
    plugin = context.get_plugin("records")
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
