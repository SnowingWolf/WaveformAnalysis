"""
流式 CPU 插件模块

本模块包含 CPU 实现的流式插件：
- signal_peaks.py: SignalPeaksStreamPlugin

其余流式插件正在规划中。

**加速器**: CPU (NumPy)
**流式支持**: ✓
"""

from waveform_analysis._lazy_exports import LazyExport as _LazyExport
from waveform_analysis._lazy_exports import lazy_dir as _lazy_dir
from waveform_analysis._lazy_exports import (
    resolve_lazy_attribute as _resolve_lazy_attribute,
)
from waveform_analysis.core.foundation.utils import exporter

# Preserve the historical helper names without importing signal_peaks.py.
export, _exported = exporter()

__all__ = ["SignalPeaksStreamPlugin"]

_LAZY_EXPORTS: dict[str, _LazyExport] = {
    "SignalPeaksStreamPlugin": (
        "waveform_analysis.core.plugins.builtin.signal_peaks_stream",
        "SignalPeaksStreamPlugin",
    ),
    "signal_peaks": (f"{__name__}.signal_peaks", None),
}

_LAZY_ATTRS = _LAZY_EXPORTS


def __getattr__(name: str):
    return _resolve_lazy_attribute(name, _LAZY_EXPORTS, globals())


def __dir__():
    return _lazy_dir(globals(), _LAZY_EXPORTS, __all__)
