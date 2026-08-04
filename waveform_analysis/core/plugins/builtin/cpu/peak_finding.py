"""Backward-compatible shim. Implementation moved to builtin.hit.plugin.

``HIT_DTYPE``、``HitFinderPlugin``（provides='hit'）现由
:mod:`waveform_analysis.core.plugins.builtin.hit` bundle 属主，本模块仅转发兼容符号。
"""

from waveform_analysis.core.plugins.builtin.hit.plugin import (
    ADVANCED_PEAK_DTYPE,
    HIT_DTYPE,
    HitFinderPlugin,
)

__all__ = ["HIT_DTYPE", "ADVANCED_PEAK_DTYPE", "HitFinderPlugin"]
