"""Backward-compatible shim. Implementation moved to builtin.hit_grouped.

``HitGroupedPlugin``（provides='hit_grouped'）现由
:mod:`waveform_analysis.core.plugins.builtin.hit_grouped` bundle 属主，本模块仅转发兼容符号。
"""

from waveform_analysis.core.plugins.builtin.hit_grouped import HitGroupedPlugin

__all__ = ["HitGroupedPlugin"]
