"""waveform_width bundle - provides 'waveform_width'。

WaveformWidthPlugin 基于峰值检测结果计算波形的上升/下降时间与总宽度，
输出 ``WAVEFORM_WIDTH_DTYPE``。支持使用原始波形或滤波后的波形。
"""

from waveform_analysis.core.plugins.builtin.waveform_width.plugin import (
    WAVEFORM_WIDTH_DTYPE,
    WaveformWidthPlugin,
)

__all__ = ["WaveformWidthPlugin", "WAVEFORM_WIDTH_DTYPE"]
