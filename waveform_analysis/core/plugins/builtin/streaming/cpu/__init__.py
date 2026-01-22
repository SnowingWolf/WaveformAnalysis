# -*- coding: utf-8 -*-
"""
流式 CPU 插件模块

本模块包含 CPU 实现的流式插件：
- signal_peaks.py: SignalPeaksStreamPlugin

其余流式插件正在规划中。

**加速器**: CPU (NumPy)
**流式支持**: ✓
"""

from waveform_analysis.core.foundation.utils import exporter

from .signal_peaks import SignalPeaksStreamPlugin

export, __all__ = exporter()

__all__.extend([
    "SignalPeaksStreamPlugin",
])
