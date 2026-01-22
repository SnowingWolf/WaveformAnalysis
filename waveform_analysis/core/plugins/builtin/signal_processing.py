# -*- coding: utf-8 -*-
"""
Deprecated shim for signal_processing plugins.

Use waveform_analysis.core.plugins.builtin.cpu instead.
"""

import warnings

from .cpu import (
    ADVANCED_PEAK_DTYPE,
    FilteredWaveformsPlugin,
    SignalPeaksPlugin,
)

warnings.warn(
    "waveform_analysis.core.plugins.builtin.signal_processing is deprecated; "
    "use waveform_analysis.core.plugins.builtin.cpu instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = [
    "FilteredWaveformsPlugin",
    "SignalPeaksPlugin",
    "ADVANCED_PEAK_DTYPE",
]
