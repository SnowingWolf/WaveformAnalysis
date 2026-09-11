"""signal_peaks_stream bundle - provides 'signal_peaks_stream'。

SignalPeaksStreamPlugin 基于滤波后的波形流式检测峰值，返回峰值特征的
chunk 流。继承 :class:`~waveform_analysis.core.plugins.core.streaming.StreamingPlugin`。
"""

from waveform_analysis.core.plugins.builtin.signal_peaks_stream.plugin import (
    SignalPeaksStreamPlugin,
)

__all__ = ["SignalPeaksStreamPlugin"]
