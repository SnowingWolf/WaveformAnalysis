"""Backward-compatible imports for hit merged feature plugins.

The implementation lives in :mod:`waveform_analysis.core.plugins.builtin.hit.hit_merged_features`.
"""

from waveform_analysis.core.plugins.builtin.hit import hit_merged_features as _impl
from waveform_analysis.core.plugins.builtin.hit.hit_merged_features import *  # noqa: F401,F403
from waveform_analysis.core.plugins.builtin.hit.hit_merged_features import _polarity_sign_array

__all__ = [*_impl.__all__, "_polarity_sign_array"]
