"""
CPU 插件模块 - 使用 NumPy/SciPy 实现

本模块包含所有 CPU 实现的插件：
- raw_files.py: 原始文件扫描插件（迁移至 builtin.raw_files）
- waveforms.py: 波形提取与结构化插件（包含 WaveformStruct，迁移至 builtin.st_waveforms）
- peak_finding.py: Hit 检测插件（HitFinderPlugin）
- hit_finder.py: 阈值 hit 兼容插件（ThresholdHitPlugin）
- basic_features.py: 基础特征计算插件（迁移至 builtin.basic_features）
- dataframe.py: DataFrame 构建插件（迁移至 builtin.df）
- event_analysis.py: 事件分组与配对插件
- filtering.py: CPU 滤波插件（scipy，迁移至 builtin.filtered_waveforms）
- peak_finding.py: CPU 寻峰插件（scipy）

**加速器**: CPU (NumPy/SciPy/Numba)

已迁移为 per-plugin bundle 的插件通过 ``_LAZY_IMPORTS`` 懒加载转发，
``__all__`` 保持全量以维持向后兼容。
"""

# 已迁移插件均经 _LAZY_IMPORTS 懒加载（见下）；仅保留未迁移的 s1_s2_classifier 急切导入
from .s1_s2_classifier import (
    LABEL_S1,
    LABEL_S2,
    LABEL_UNKNOWN,
    S1_S2_CLASSIFIER_DTYPE,
    S1S2ClassifierPlugin,
)

# Lazy imports for backward compatibility - redirect to new locations
_LAZY_IMPORTS = {
    # Peaklet plugins (迁移到 peaks/)
    "PeakletPlugin": "..peaklets",
    "PeakletComponentsPlugin": "..peaklet_components",
    "PeakletWaveformPlugin": "..peaklet_waveforms",
    "PeakletWaveformPoolPlugin": "..peaklet_waveform_pool",
    "PeakletFeaturesPlugin": "..peaklet_features",
    "PeaksPlugin": "..peaks",
    "PeakletChannelsPlugin": "..peaklet_channels",
    "PEAKLET_DTYPE": "..peaklets",
    "PEAKLET_COMPONENTS_DTYPE": "..peaklet_components",
    "PEAKLET_WAVEFORMS_DTYPE": "..peaklet_waveforms",
    "PEAKLET_FEATURES_DTYPE": "..peaklet_features",
    "PEAKS_DTYPE": "..peaks",
    "PEAKLET_CHANNELS_DTYPE": "..peaklet_channels",
    # Hit plugins (迁移到 per-provides bundle)
    "HitFinderPlugin": "..hit",
    "HIT_DTYPE": "..hit",
    "HitGroupedPlugin": "..hit_grouped",
    "ThresholdHitPlugin": "..hit_threshold",
    "HitMergePlugin": "..hit_merged",
    "HitMergeClustersPlugin": "..hit_merge_clusters",
    "HitMergedComponentsPlugin": "..hit_merged_components",
    "HitMergedFeaturesPlugin": "..hit_merged_features",
    "THRESHOLD_HIT_DTYPE": "..hit_threshold",
    "HIT_MERGED_DTYPE": "..hit_merged",
    "HIT_MERGE_CLUSTERS_DTYPE": "..hit_merge_clusters",
    "HIT_MERGED_COMPONENTS_DTYPE": "..hit_merged_components",
    "HIT_MERGED_FEATURES_DTYPE": "..hit_merged_features",
    # Phase 4c 迁移：cpu 单插件模块 → per-plugin bundle
    "RawFileNamesPlugin": "..raw_files",
    "WaveformsPlugin": "..st_waveforms",
    "WaveformStruct": "..st_waveforms",
    "WaveformStructConfig": "..st_waveforms",
    "BasicFeaturesPlugin": "..basic_features",
    "BASIC_FEATURES_DTYPE": "..basic_features",
    "DataFramePlugin": "..df",
    "FilteredWaveformsPlugin": "..filtered_waveforms",
    "CacheAnalysisPlugin": "..cache_analysis",
    "PeakClassificationPlugin": "..peak_classification",
    "PEAK_CLASSIFICATION_DTYPE": "..peak_classification",
    "LABEL_S1_S2": "..peak_classification",
    "S1S2PairCandidatesPlugin": "..s1_s2_pair_candidates",
    "S1S2PairSelectionPlugin": "..s1_s2_pairs",
    "S1_S2_PAIR_CANDIDATES_DTYPE": "..s1_s2_pair_candidates",
    "FLAG_VALID_TIME": "..s1_s2_pair_candidates",
    "FLAG_RATIO_IN_RANGE": "..s1_s2_pair_candidates",
    "FLAG_S1_LOW_QUALITY": "..s1_s2_pair_candidates",
    "FLAG_S2_LOW_QUALITY": "..s1_s2_pair_candidates",
    "FLAG_MULTI_S1_CANDIDATE": "..s1_s2_pair_candidates",
    "FLAG_MULTI_S2_CANDIDATE": "..s1_s2_pair_candidates",
    "FLAG_CLOSE_COMPETITOR": "..s1_s2_pair_candidates",
    "FLAG_ORPHAN_S1": "..s1_s2_pair_candidates",
    "FLAG_ORPHAN_S2": "..s1_s2_pair_candidates",
    "FLAG_NEAR_CHUNK_BOUNDARY": "..s1_s2_pair_candidates",
    "WaveformWidthPlugin": "..waveform_width",
    "WAVEFORM_WIDTH_DTYPE": "..waveform_width",
    "WaveformWidthIntegralPlugin": "..waveform_width_integral",
    "WAVEFORM_WIDTH_INTEGRAL_DTYPE": "..waveform_width_integral",
    "EnergyReconstructionPlugin": "..energy_reconstruction",
    "ENERGY_RECONSTRUCTION_DTYPE": "..energy_reconstruction",
    "PositionReconstructionPlugin": "..position_reconstruction",
    "EventPlugin": "..events",
    # Records family (迁移到 records/ / wave_pool/ / wave_pool_filtered/)
    "RecordsPlugin": "..records",
    "WavePoolPlugin": "..wave_pool",
    "WavePoolFilteredPlugin": "..wave_pool_filtered",
    "RecordsAsymmetryMaskPlugin": "..records_asymmetry_mask",
    "RecordsDetectorMaskPlugin": "..records_detector_mask",
    "RecordsVetoMaskPlugin": "..records_veto_mask",
    # Event analysis (迁移到 df_events/ / df_paired/)
    "GroupedEventsPlugin": "..df_events",
    "PairedEventsPlugin": "..df_paired",
}

# 兼容别名（懒解析，保持 __all__ 中同名导出与主符号同一对象）
_ALIASES = {
    "StWaveformsPlugin": "WaveformsPlugin",
    "RawFilesPlugin": "RawFileNamesPlugin",
}


def __getattr__(name):
    """Lazy loading for backward compatibility."""
    if name in _LAZY_IMPORTS:
        module_path = _LAZY_IMPORTS[name]
        from importlib import import_module

        module = import_module(module_path, __package__)
        return getattr(module, name)
    if name in _ALIASES:
        return __getattr__(_ALIASES[name])
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


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
    "EventPlugin",
    "GroupedEventsPlugin",
    "PairedEventsPlugin",
    "PositionReconstructionPlugin",
    "EnergyReconstructionPlugin",
    "ENERGY_RECONSTRUCTION_DTYPE",
    # 滤波插件
    "FilteredWaveformsPlugin",
    # Peak classification (S1/S2)
    "PeakClassificationPlugin",
    "PEAK_CLASSIFICATION_DTYPE",
    "LABEL_S1",
    "LABEL_S2",
    "LABEL_S1_S2",
    "LABEL_UNKNOWN",
    # 寻峰插件
    "HIT_DTYPE",
    # 波形宽度插件
    "WaveformWidthPlugin",
    "WAVEFORM_WIDTH_DTYPE",
    "WaveformWidthIntegralPlugin",
    "WAVEFORM_WIDTH_INTEGRAL_DTYPE",
    # S1-S2 pairing
    "S1S2PairCandidatesPlugin",
    "S1S2PairSelectionPlugin",
    "S1_S2_PAIR_CANDIDATES_DTYPE",
    "FLAG_VALID_TIME",
    "FLAG_RATIO_IN_RANGE",
    "FLAG_S1_LOW_QUALITY",
    "FLAG_S2_LOW_QUALITY",
    "FLAG_MULTI_S1_CANDIDATE",
    "FLAG_MULTI_S2_CANDIDATE",
    "FLAG_CLOSE_COMPETITOR",
    "FLAG_ORPHAN_S1",
    "FLAG_ORPHAN_S2",
    "FLAG_NEAR_CHUNK_BOUNDARY",
    # Cache analysis
    "CacheAnalysisPlugin",
    # Records
    "RecordsPlugin",
    "WavePoolPlugin",
    "WavePoolFilteredPlugin",
    "RecordsAsymmetryMaskPlugin",
    "RecordsDetectorMaskPlugin",
    "RecordsVetoMaskPlugin",
    "standard_plugins",
    # Backward compatibility - hit plugins (now in hit/)
    "HitGroupedPlugin",
    "ThresholdHitPlugin",
    "HitMergePlugin",
    "HitMergeClustersPlugin",
    "HitMergedComponentsPlugin",
    "HitMergedFeaturesPlugin",
    "THRESHOLD_HIT_DTYPE",
    "HIT_MERGED_DTYPE",
    "HIT_MERGE_CLUSTERS_DTYPE",
    "HIT_MERGED_COMPONENTS_DTYPE",
    "HIT_MERGED_FEATURES_DTYPE",
    # Backward compatibility - peaklet plugins (now in peaks/)
    "PeakletPlugin",
    "PeakletComponentsPlugin",
    "PeakletWaveformPlugin",
    "PeakletWaveformPoolPlugin",
    "PeakletFeaturesPlugin",
    "PeakletChannelsPlugin",
    "PeaksPlugin",
    "PEAKLET_DTYPE",
    "PEAKLET_COMPONENTS_DTYPE",
    "PEAKLET_WAVEFORMS_DTYPE",
    "PEAKLET_FEATURES_DTYPE",
    "PEAKLET_CHANNELS_DTYPE",
    "PEAKS_DTYPE",
]
