"""CPU Waveform Width Integral Plugin - 兼容 shim。

``WaveformWidthIntegralPlugin``（provides="waveform_width_integral"）与
``WAVEFORM_WIDTH_INTEGRAL_DTYPE`` 已迁至
:mod:`waveform_analysis.core.plugins.builtin.waveform_width_integral`。
本模块仅向后兼容转发全部符号。
"""

from waveform_analysis.core.plugins.builtin.waveform_width_integral import (
    WAVEFORM_WIDTH_INTEGRAL_DTYPE,
    WaveformWidthIntegralPlugin,
)

__all__ = ["WaveformWidthIntegralPlugin", "WAVEFORM_WIDTH_INTEGRAL_DTYPE"]
