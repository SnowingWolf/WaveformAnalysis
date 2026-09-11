"""CPU Waveform Width Plugin - 兼容 shim。

``WaveformWidthPlugin``（provides="waveform_width"）与 ``WAVEFORM_WIDTH_DTYPE``
已迁至 :mod:`waveform_analysis.core.plugins.builtin.waveform_width`。
本模块仅向后兼容转发全部符号。
"""

from waveform_analysis.core.plugins.builtin.waveform_width import (
    WAVEFORM_WIDTH_DTYPE,
    WaveformWidthPlugin,
)

__all__ = ["WaveformWidthPlugin", "WAVEFORM_WIDTH_DTYPE"]
