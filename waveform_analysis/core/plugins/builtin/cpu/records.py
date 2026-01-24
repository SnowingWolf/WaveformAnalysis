# -*- coding: utf-8 -*-
"""
Records + wave_pool plugins (CPU).
"""

from typing import Any

import numpy as np

from waveform_analysis.core.plugins.core.base import Option, Plugin
from waveform_analysis.core.processing.records import (
    RECORDS_DTYPE,
    RecordsBundle,
    build_records_from_st_waveforms_sharded,
)

_BUNDLE_CACHE_NAME = "_records_bundle"


def _bundle_cache_key(context: Any, run_id: str) -> str:
    st_key = context.key_for(run_id, "st_waveforms")
    return f"{_BUNDLE_CACHE_NAME}-{st_key}"


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


def _get_records_bundle(context: Any, run_id: str, part_size: int) -> RecordsBundle:
    cache_key = _bundle_cache_key(context, run_id)
    cached = context._results.get((run_id, cache_key))
    if isinstance(cached, RecordsBundle):
        _cleanup_stale_bundles(context, run_id, cache_key)
        return cached

    st_waveforms = context.get_data(run_id, "st_waveforms")
    bundle = build_records_from_st_waveforms_sharded(st_waveforms, part_size=part_size)
    context._set_data(run_id, cache_key, bundle)
    _cleanup_stale_bundles(context, run_id, cache_key)
    return bundle


class RecordsPlugin(Plugin):
    """Build records (event index table) from st_waveforms."""

    provides = "records"
    depends_on = ["st_waveforms"]
    save_when = "always"
    output_dtype = RECORDS_DTYPE
    options = {
        "records_part_size": Option(
            default=200_000,
            type=int,
            help="Max events per records shard; <=0 disables sharding.",
        ),
    }
    version = "0.1.0"

    def compute(self, context: Any, run_id: str, **kwargs) -> np.ndarray:
        part_size = context.get_config(self, "records_part_size")
        bundle = _get_records_bundle(context, run_id, part_size)
        return bundle.records


class WavePoolPlugin(Plugin):
    """Build wave_pool (uint16) from st_waveforms."""

    provides = "wave_pool"
    depends_on = ["st_waveforms"]
    save_when = "always"
    output_dtype = np.dtype(np.uint16)
    options = {
        "records_part_size": Option(
            default=200_000,
            type=int,
            help="Max events per records shard; <=0 disables sharding.",
        ),
    }
    version = "0.1.0"

    def compute(self, context: Any, run_id: str, **kwargs) -> np.ndarray:
        part_size = context.get_config(self, "records_part_size")
        bundle = _get_records_bundle(context, run_id, part_size)
        return bundle.wave_pool
