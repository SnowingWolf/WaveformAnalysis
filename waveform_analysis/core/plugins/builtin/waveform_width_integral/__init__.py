"""waveform_width_integral bundle - provides 'waveform_width_integral'。

WaveformWidthIntegralPlugin 对每条事件波形计算积分分位数宽度
(t_low/t_high)，输出 ``WAVEFORM_WIDTH_INTEGRAL_DTYPE``。
"""

from waveform_analysis.core.plugins.builtin.waveform_width_integral.plugin import (
    WAVEFORM_WIDTH_INTEGRAL_DTYPE,
    WaveformWidthIntegralPlugin,
)

__all__ = ["WaveformWidthIntegralPlugin", "WAVEFORM_WIDTH_INTEGRAL_DTYPE"]
