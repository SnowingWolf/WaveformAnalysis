"""CPU Streaming Signal Peaks Plugin - 兼容 shim。

``SignalPeaksStreamPlugin``（provides="signal_peaks_stream"）已迁至
:mod:`waveform_analysis.core.plugins.builtin.signal_peaks_stream`。
本模块仅向后兼容转发全部符号。
"""

from waveform_analysis.core.plugins.builtin.signal_peaks_stream import (
    SignalPeaksStreamPlugin,
)

__all__ = ["SignalPeaksStreamPlugin"]
