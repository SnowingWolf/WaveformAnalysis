"""
Peaks 插件模块 - Peaklet 和 Peak 相关插件

本模块包含所有与 peaklet 构建和 peak 处理相关的插件：
- peaklets.py: Peaklet 构建、特征提取与 peak 转换插件
- peaklet_channels.py: Per-channel contribution 分析插件

**功能域**: Peaks (Peaklet 构建与特征提取)
"""

from .peaklet_channels import PEAKLET_CHANNELS_DTYPE, PeakletChannelsPlugin
from .peaklets import (
    PEAKLET_COMPONENTS_DTYPE,
    PEAKLET_DTYPE,
    PEAKLET_FEATURES_DTYPE,
    PEAKLET_WAVEFORMS_DTYPE,
    PEAKS_DTYPE,
    PeakletComponentsPlugin,
    PeakletFeaturesPlugin,
    PeakletPlugin,
    PeakletWaveformPlugin,
    PeakletWaveformPoolPlugin,
    PeaksPlugin,
)

__all__ = [
    # Peaklet 插件
    "PeakletPlugin",
    "PeakletComponentsPlugin",
    "PeakletWaveformPlugin",
    "PeakletWaveformPoolPlugin",
    "PeakletFeaturesPlugin",
    "PeakletChannelsPlugin",
    "PeaksPlugin",
    # 数据类型
    "PEAKLET_DTYPE",
    "PEAKLET_COMPONENTS_DTYPE",
    "PEAKLET_WAVEFORMS_DTYPE",
    "PEAKLET_FEATURES_DTYPE",
    "PEAKLET_CHANNELS_DTYPE",
    "PEAKS_DTYPE",
]
