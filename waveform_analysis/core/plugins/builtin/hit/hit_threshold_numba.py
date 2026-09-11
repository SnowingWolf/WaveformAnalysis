"""Backward-compatible shim. Implementation moved to builtin.hit_threshold._compute.

Numba 内核（count_ragged_hits / fill_ragged_hits / batch_prefilter_records /
contiguous_regions_numba）现由 :mod:`waveform_analysis.core.plugins.builtin.hit_threshold`
bundle 属主，本模块仅转发兼容符号。
"""

from waveform_analysis.core.plugins.builtin.hit_threshold._compute import (
    batch_prefilter_records,
    contiguous_regions_numba,
    count_ragged_hits,
    fill_ragged_hits,
)

__all__ = [
    "batch_prefilter_records",
    "contiguous_regions_numba",
    "count_ragged_hits",
    "fill_ragged_hits",
]
