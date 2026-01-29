# -*- coding: utf-8 -*-
"""
CPU Standard Plugins - 标准波形分析插件（统一导入入口）

**加速器**: CPU (NumPy/SciPy/Numba)
**功能**: 从原始文件扫描到特征计算和事件配对的完整插件链

本模块作为标准插件的统一导入入口，所有插件已拆分到独立文件中：
- RawFileNamesPlugin → waveforms.py
- WaveformsPlugin → waveforms.py (合并了原 StWaveformsPlugin)
- HitFinderPlugin → hit_finder.py
- BasicFeaturesPlugin → basic_features.py
- DataFramePlugin → dataframe.py
- GroupedEventsPlugin → event_analysis.py
- PairedEventsPlugin → event_analysis.py

使用方式：
    from waveform_analysis.core.plugins.builtin.cpu.standard import standard_plugins
    # 或者
    from waveform_analysis.core.plugins.builtin.cpu.standard import (
        RawFileNamesPlugin,
        WaveformsPlugin,
        ...
    )
"""

# 从独立文件导入所有插件
from .raw_files import RawFileNamesPlugin
from .waveforms import WaveformsPlugin, WaveformStruct, WaveformStructConfig
from .hit_finder import HitFinderPlugin
from .basic_features import BASIC_FEATURES_DTYPE, BasicFeaturesPlugin
from .dataframe import DataFramePlugin
from .event_analysis import GroupedEventsPlugin, PairedEventsPlugin

# 标准插件列表 - 按依赖顺序排列
standard_plugins = [
    RawFileNamesPlugin(),
    WaveformsPlugin(),
    HitFinderPlugin(),
    BasicFeaturesPlugin(),
    DataFramePlugin(),
    GroupedEventsPlugin(),
    PairedEventsPlugin(),
]

__all__ = [
    "RawFileNamesPlugin",
    "WaveformsPlugin",
    "WaveformStruct",
    "WaveformStructConfig",
    "HitFinderPlugin",
    "BasicFeaturesPlugin",
    "BASIC_FEATURES_DTYPE",
    "DataFramePlugin",
    "GroupedEventsPlugin",
    "PairedEventsPlugin",
    "standard_plugins",
]
