"""Helpers for migrating plugin configs from legacy sampling interval keys to ``dt``."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any
import warnings

import numpy as np


def get_raw_config_value(context: Any, plugin: Any, name: str) -> Any:
    """Read a config value without requiring the key to exist in ``plugin.options``."""
    provides = plugin.provides

    if provides in context.config and isinstance(context.config[provides], dict):
        if name in context.config[provides]:
            return context.config[provides][name]

    namespaced_key = f"{provides}.{name}"
    if namespaced_key in context.config:
        return context.config[namespaced_key]

    return context.config.get(name)


def resolve_dt_config(
    context: Any,
    plugin: Any,
    deprecated_keys: Iterable[str] = (),
) -> Any:
    """Resolve canonical ``dt`` and fall back to deprecated keys with warnings."""
    dt = get_raw_config_value(context, plugin, "dt")
    if dt is not None:
        return dt

    for old_key in deprecated_keys:
        legacy_value = get_raw_config_value(context, plugin, old_key)
        if legacy_value is None:
            continue
        warnings.warn(
            f"[{plugin.provides}] Config '{old_key}' is deprecated and will be removed in a "
            "future release. Use 'dt' instead.",
            DeprecationWarning,
            stacklevel=3,
        )
        return legacy_value
    return None


def require_dt_array(
    data: np.ndarray,
    *,
    explicit_dt: Any = None,
    plugin_name: str,
    data_name: str,
) -> np.ndarray:
    """Return per-row ``dt`` values as ``int32`` using data first, explicit config second."""
    names = data.dtype.names or ()
    if "dt" in names:
        dt = np.asarray(data["dt"], dtype=np.int64)
        if len(dt) != len(data):
            raise ValueError(f"[{plugin_name}] {data_name}.dt length mismatch")
        if np.any(dt <= 0):
            raise ValueError(f"[{plugin_name}] {data_name}.dt must be positive for every row")
        if np.any(dt > np.iinfo(np.int32).max):
            raise ValueError(f"[{plugin_name}] {data_name}.dt exceeds int32 range")
        return dt.astype(np.int32, copy=False)

    if explicit_dt is None:
        raise ValueError(
            f"[{plugin_name}] Input '{data_name}' is missing required field 'dt'; "
            "provide explicit config 'dt' for this migration period."
        )

    dt_scalar = int(explicit_dt)
    if dt_scalar <= 0:
        raise ValueError(f"[{plugin_name}] dt must be > 0")
    if dt_scalar > np.iinfo(np.int32).max:
        raise ValueError(f"[{plugin_name}] dt exceeds int32 range: {dt_scalar}")
    return np.full(len(data), dt_scalar, dtype=np.int32)
