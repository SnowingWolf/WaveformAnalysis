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
from .standard import (
    RawFilesPlugin,
    WaveformsPlugin,
    StWaveformsPlugin,
    HitFinderPlugin,
    PeaksPlugin,
    ChargesPlugin,
    DataFramePlugin,
    GroupedEventsPlugin,
    PairedEventsPlugin,
)

# CPU 滤波插件
from .filtering import FilteredWaveformsPlugin

# CPU 寻峰插件
from .peak_finding import SignalPeaksPlugin, ADVANCED_PEAK_DTYPE

# CPU 波形宽度插件
from .waveform_width import WaveformWidthPlugin, WAVEFORM_WIDTH_DTYPE

# Cache analysis plugin
from .cache_analysis import CacheAnalysisPlugin

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
    # Cache analysis
    "CacheAnalysisPlugin",
]
