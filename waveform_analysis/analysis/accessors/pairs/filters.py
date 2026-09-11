"""S1-S2 pair filtering implementation."""

from typing import Any

import numpy as np


def mask(
    self,
    drift_time_ns_range: tuple[float, float] | None = None,
    log10_s2_s1_range: tuple[float, float] | None = None,
    score_total_range: tuple[float, float] | None = None,
    flags_any: int | None = None,
    flags_all: int | None = None,
    flags_none: int | None = None,
    selected: bool | None = None,
    custom_filter: Any = None,
) -> np.ndarray:
    if not self._pairs_loaded:
        self._load_pairs()
    pairs = self._pairs
    assert pairs is not None
    result = np.ones(len(pairs), dtype=bool)
    for limits, field in (
        (drift_time_ns_range, "drift_time_ns"),
        (log10_s2_s1_range, "log10_s2_s1"),
        (score_total_range, "score_total"),
    ):
        if limits is None or field not in pairs.dtype.names:
            continue
        lower, upper = limits
        if lower is not None:
            result &= pairs[field] >= lower
        if upper is not None:
            result &= pairs[field] <= upper
    if "flags" in pairs.dtype.names:
        if flags_any is not None:
            result &= (pairs["flags"] & flags_any) != 0
        if flags_all is not None:
            result &= (pairs["flags"] & flags_all) == flags_all
        if flags_none is not None:
            result &= (pairs["flags"] & flags_none) == 0
    if selected is not None and "selected" in pairs.dtype.names:
        result &= pairs["selected"] == selected
    if custom_filter is not None:
        result &= custom_filter(pairs)
    return result


__all__ = ["mask"]
