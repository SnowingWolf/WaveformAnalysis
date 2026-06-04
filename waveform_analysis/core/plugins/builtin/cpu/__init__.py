"""
CPU 插件模块 - 使用 NumPy/SciPy 实现

本模块包含所有 CPU 实现的插件：
- raw_files.py: 原始文件扫描插件
- waveforms.py: 波形提取与结构化插件（包含 WaveformStruct）
- peak_finding.py: Hit 检测插件（HitFinderPlugin）
- hit_finder.py: 阈值 hit 兼容插件（ThresholdHitPlugin）
- basic_features.py: 基础特征计算插件
- dataframe.py: DataFrame 构建插件
- event_analysis.py: 事件分组与配对插件
- filtering.py: CPU 滤波插件（scipy）
- peak_finding.py: CPU 寻峰插件（scipy）

**加速器**: CPU (NumPy/SciPy/Numba)
"""

# 数据加载与结构化插件
from .basic_features import BASIC_FEATURES_DTYPE, BasicFeaturesPlugin

# Cache analysis plugin
from .cache_analysis import CacheAnalysisPlugin

# 数据整合插件
from .dataframe import DataFramePlugin

# 事件分析插件
from .event_analysis import GroupedEventsPlugin, HitGroupedPlugin, PairedEventsPlugin

# CPU 滤波插件
from .filtering import FilteredWaveformsPlugin
from .hit_finder import THRESHOLD_HIT_DTYPE, ThresholdHitPlugin
from .hit_merge import (
    HIT_MERGE_CLUSTERS_DTYPE,
    HIT_MERGED_COMPONENTS_DTYPE,
    HIT_MERGED_DTYPE,
    HitMergeClustersPlugin,
    HitMergedComponentsPlugin,
    HitMergePlugin,
)
from .hit_merged_features import HIT_MERGED_FEATURES_DTYPE, HitMergedFeaturesPlugin

# CPU 寻峰插件
from .peak_finding import HIT_DTYPE, HitFinderPlugin
from .peaklet_channels import PEAKLET_CHANNELS_DTYPE, PeakletChannelsPlugin
from .peaklets import (
    PEAKLET_COMPONENTS_DTYPE,
    PEAKLET_DTYPE,
    PeakletComponentsPlugin,
    PeakletPlugin,
)

# Records 插件
from .records import RecordsPlugin, WavePoolFilteredPlugin, WavePoolPlugin
from .records_asymmetry import RecordsAsymmetryMaskPlugin
from .s1_s2_classifier import (
    LABEL_S1,
    LABEL_S2,
    LABEL_UNKNOWN,
    S1_S2_CLASSIFIER_DTYPE,
    S1S2ClassifierPlugin,
)

# CPU 波形宽度插件
from .waveform_width import WAVEFORM_WIDTH_DTYPE, WaveformWidthPlugin
from .waveform_width_integral import (
    WAVEFORM_WIDTH_INTEGRAL_DTYPE,
    WaveformWidthIntegralPlugin,
)
from .waveforms import (
    RawFileNamesPlugin,
    WaveformsPlugin,
    WaveformStruct,
    WaveformStructConfig,
)

# Backward-compatible aliases
RawFilesPlugin = RawFileNamesPlugin
StWaveformsPlugin = WaveformsPlugin

from waveform_analysis.core.plugins.profiles import cpu_default

standard_plugins = cpu_default()

__all__ = [
    # 标准插件
    "RawFileNamesPlugin",
    "RawFilesPlugin",
    "WaveformsPlugin",
    "StWaveformsPlugin",
    "WaveformStruct",
    "WaveformStructConfig",
    "HitFinderPlugin",
    "BasicFeaturesPlugin",
    "BASIC_FEATURES_DTYPE",
    "DataFramePlugin",
    "GroupedEventsPlugin",
    "HitGroupedPlugin",
    "PairedEventsPlugin",
    # 滤波插件
    "FilteredWaveformsPlugin",
    "ThresholdHitPlugin",
    "THRESHOLD_HIT_DTYPE",
    "HitMergeClustersPlugin",
    "HitMergePlugin",
    "HitMergedComponentsPlugin",
    "HIT_MERGE_CLUSTERS_DTYPE",
    "HIT_MERGED_DTYPE",
    "HIT_MERGED_COMPONENTS_DTYPE",
    "HitMergedFeaturesPlugin",
    "HIT_MERGED_FEATURES_DTYPE",
    "PeakletPlugin",
    "PeakletComponentsPlugin",
    "PeakletChannelsPlugin",
    "RecordsAsymmetryMaskPlugin",
    "PEAKLET_DTYPE",
    "PEAKLET_COMPONENTS_DTYPE",
    "PEAKLET_CHANNELS_DTYPE",
    # 寻峰插件
    "HIT_DTYPE",
    # 波形宽度插件
    "WaveformWidthPlugin",
    "WAVEFORM_WIDTH_DTYPE",
    "WaveformWidthIntegralPlugin",
    "WAVEFORM_WIDTH_INTEGRAL_DTYPE",
    # S1/S2 classifier
    "S1S2ClassifierPlugin",
    "S1_S2_CLASSIFIER_DTYPE",
    "LABEL_S1",
    "LABEL_S2",
    "LABEL_UNKNOWN",
    # Cache analysis
    "CacheAnalysisPlugin",
    # Records
    "RecordsPlugin",
    "WavePoolPlugin",
    "WavePoolFilteredPlugin",
    "standard_plugins",
]
