# -*- coding: utf-8 -*-
"""
Cache tools for inspecting stored data.
"""

import inspect
from typing import Any, List

from waveform_analysis.core.foundation.utils import exporter

export, __all__ = exporter()


@export
def list_channel_cache_keys(ctx: Any, run_id: str, data_name: str) -> List[str]:
    """List cache keys matching {key}_ch* for a run/data_name."""
    if data_name not in ctx._plugins:
        raise KeyError(f"Unknown data name: {data_name}")

    key = ctx.key_for(run_id, data_name)
    storage = ctx._get_storage_for_data_name(data_name)
    if hasattr(ctx, "_list_channel_keys"):
        return ctx._list_channel_keys(storage, run_id, key)

    keys: List[str] = []
    if hasattr(storage, "list_keys"):
        try:
            params = inspect.signature(storage.list_keys).parameters
            if "run_id" in params:
                keys = storage.list_keys(run_id=run_id)
            else:
                keys = storage.list_keys()
        except Exception:
            keys = []

    prefix = f"{key}_ch"
    matches = [k for k in keys if k.startswith(prefix)]
    if matches:
        def _ch_index(k: str) -> float:
            suffix = k[len(prefix):]
            try:
                return float(int(suffix))
            except ValueError:
                return float("inf")

        matches.sort(key=_ch_index)
        return matches

    if hasattr(ctx, "_storage_exists"):
        ch_idx = 0
        while ctx._storage_exists(storage, f"{key}_ch{ch_idx}", run_id):
            matches.append(f"{key}_ch{ch_idx}")
            ch_idx += 1

    return matches
