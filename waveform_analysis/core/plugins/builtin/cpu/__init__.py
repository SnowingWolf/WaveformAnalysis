# -*- coding: utf-8 -*-
"""
CPU 插件模块 - 使用 NumPy/SciPy 实现

本模块包含所有 CPU 实现的插件：
- raw_files.py: 原始文件扫描插件
- waveforms.py: 波形提取插件
- st_waveforms.py: 波形结构化插件
- hit_finder.py: Hit 检测插件
- basic_features.py: 基础特征计算插件
- dataframe.py: DataFrame 构建插件
- event_analysis.py: 事件分组与配对插件
- filtering.py: CPU 滤波插件（scipy）
- peak_finding.py: CPU 寻峰插件（scipy）

**加速器**: CPU (NumPy/SciPy/Numba)
"""

# 数据加载插件
from .waveforms import RawFileNamesPlugin, WaveformsPlugin

# 波形结构化插件
from .st_waveforms import StWaveformsPlugin

# 特征提取插件
from .hit_finder import HitFinderPlugin
from .basic_features import BASIC_FEATURES_DTYPE, BasicFeaturesPlugin

# 数据整合插件
from .dataframe import DataFramePlugin

# 事件分析插件
from .event_analysis import GroupedEventsPlugin, PairedEventsPlugin

# Cache analysis plugin
from .cache_analysis import CacheAnalysisPlugin

# CPU 滤波插件
from .filtering import FilteredWaveformsPlugin

# CPU 寻峰插件
from .peak_finding import ADVANCED_PEAK_DTYPE, SignalPeaksPlugin

# Events 插件
from .events import EventFramePlugin, EventsGroupedPlugin, EventsPlugin

# Records 插件
from .records import RecordsPlugin

# CPU 波形宽度插件
from .waveform_width import WAVEFORM_WIDTH_DTYPE, WaveformWidthPlugin
from .waveform_width_integral import (
    WAVEFORM_WIDTH_INTEGRAL_DTYPE,
    WaveformWidthIntegralPlugin,
)

standard_plugins = [
    RawFileNamesPlugin(),
    WaveformsPlugin(),
    StWaveformsPlugin(),
    HitFinderPlugin(),
    BasicFeaturesPlugin(),
    DataFramePlugin(),
    GroupedEventsPlugin(),
    PairedEventsPlugin(),
]

__all__ = [
    # 标准插件
    "RawFileNamesPlugin",
    "WaveformsPlugin",
    "StWaveformsPlugin",
    "HitFinderPlugin",
    "BasicFeaturesPlugin",
    "BASIC_FEATURES_DTYPE",
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
    # Events
    "EventsPlugin",
    "EventFramePlugin",
    "EventsGroupedPlugin",
    # Records
    "RecordsPlugin",
    "standard_plugins",
]
