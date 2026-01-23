# -*- coding: utf-8 -*-
"""
CPU 插件模块 - 使用 NumPy/SciPy 实现

本模块包含所有 CPU 实现的插件：
- standard.py: 标准数据处理插件（RawFiles, Waveforms, Features, etc.）
- filtering.py: CPU 滤波插件（scipy）
- peak_finding.py: CPU 寻峰插件（scipy）

**加速器**: CPU (NumPy/SciPy/Numba)
"""

# 标准数据处理插件
# Cache analysis plugin
from .cache_analysis import CacheAnalysisPlugin

# CPU 滤波插件
from .filtering import FilteredWaveformsPlugin

# CPU 寻峰插件
from .peak_finding import ADVANCED_PEAK_DTYPE, SignalPeaksPlugin
from .standard import (
    ChargesPlugin,
    DataFramePlugin,
    GroupedEventsPlugin,
    HitFinderPlugin,
    PairedEventsPlugin,
    PeaksPlugin,
    RawFilesPlugin,
    StWaveformsPlugin,
    WaveformsPlugin,
)

# CPU 波形宽度插件
from .waveform_width import WAVEFORM_WIDTH_DTYPE, WaveformWidthPlugin
from .waveform_width_integral import (
    WAVEFORM_WIDTH_INTEGRAL_DTYPE,
    WaveformWidthIntegralPlugin,
)

standard_plugins = [
    RawFilesPlugin(),
    WaveformsPlugin(),
    StWaveformsPlugin(),
    HitFinderPlugin(),
    PeaksPlugin(),
    ChargesPlugin(),
    DataFramePlugin(),
    GroupedEventsPlugin(),
    PairedEventsPlugin(),
]

__all__ = [
    # 标准插件
    "RawFilesPlugin",
    "WaveformsPlugin",
    "StWaveformsPlugin",
    "HitFinderPlugin",
    "PeaksPlugin",
    "ChargesPlugin",
    "DataFramePlugin",
    "GroupedEventsPlugin",
    "PairedEventsPlugin",
    # 滤波插件
    "FilteredWaveformsPlugin",
    # 寻峰插件
    "SignalPeaksPlugin",
    "ADVANCED_PEAK_DTYPE",
    # 波形宽度插件
    "WaveformWidthPlugin",
    "WAVEFORM_WIDTH_DTYPE",
    "WaveformWidthIntegralPlugin",
    "WAVEFORM_WIDTH_INTEGRAL_DTYPE",
    # Cache analysis
    "CacheAnalysisPlugin",
    "standard_plugins",
]
