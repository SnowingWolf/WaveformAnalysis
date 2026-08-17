"""Backward-compatible shim. Implementation moved to builtin.hit_merged_features.

``HitMergedFeaturesPlugin``（provides='hit_merged_features'）及其私有 helper / Numba 内核现由
:mod:`waveform_analysis.core.plugins.builtin.hit_merged_features` bundle 属主，本模块仅转发兼容符号。
"""

import numba as nb

from waveform_analysis.core.plugins.builtin.hit_merged_features.plugin import (
    HIT_MERGED_FEATURES_DTYPE,
    HitMergedFeaturesPlugin,
    _empty_features,
    _features_fast_kernel,
    _field_or_default,
    _fill_nonoverlap_fallback_pool_kernel,
    _polarity_sign_array,
    _raise_fallback_validation_error,
    _resolve_record_indices,
    _validate_fallback_components_kernel,
)

__all__ = [
    "HIT_MERGED_FEATURES_DTYPE",
    "HitMergedFeaturesPlugin",
    "_empty_features",
    "_features_fast_kernel",
    "_field_or_default",
    "_fill_nonoverlap_fallback_pool_kernel",
    "_polarity_sign_array",
    "_raise_fallback_validation_error",
    "_resolve_record_indices",
    "_validate_fallback_components_kernel",
    "nb",
]
