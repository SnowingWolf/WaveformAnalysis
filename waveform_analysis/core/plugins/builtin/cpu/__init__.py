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

from waveform_analysis._lazy_exports import LazyExport as _LazyExport
from waveform_analysis._lazy_exports import lazy_dir as _lazy_dir
from waveform_analysis._lazy_exports import (
    resolve_lazy_attribute as _resolve_lazy_attribute,
)

_BUILTIN = "waveform_analysis.core.plugins.builtin"

_LAZY_EXPORTS: dict[str, _LazyExport] = {
    # Standard plugin bundles.
    "RawFileNamesPlugin": (f"{_BUILTIN}.raw_files", "RawFileNamesPlugin"),
    "RawFilesPlugin": (f"{_BUILTIN}.raw_files", "RawFileNamesPlugin"),
    "WaveformsPlugin": (f"{_BUILTIN}.st_waveforms", "WaveformsPlugin"),
    "StWaveformsPlugin": (f"{_BUILTIN}.st_waveforms", "WaveformsPlugin"),
    "WaveformStruct": (f"{_BUILTIN}.st_waveforms", "WaveformStruct"),
    "WaveformStructConfig": (f"{_BUILTIN}.st_waveforms", "WaveformStructConfig"),
    "HitFinderPlugin": (f"{_BUILTIN}.hit", "HitFinderPlugin"),
    "HIT_DTYPE": (f"{_BUILTIN}.hit", "HIT_DTYPE"),
    "BasicFeaturesPlugin": (f"{_BUILTIN}.basic_features", "BasicFeaturesPlugin"),
    "BASIC_FEATURES_DTYPE": (f"{_BUILTIN}.basic_features", "BASIC_FEATURES_DTYPE"),
    "DataFramePlugin": (f"{_BUILTIN}.df", "DataFramePlugin"),
    "EventPlugin": (f"{_BUILTIN}.events", "EventPlugin"),
    "GroupedEventsPlugin": (f"{_BUILTIN}.df_events", "GroupedEventsPlugin"),
    "PairedEventsPlugin": (f"{_BUILTIN}.df_paired", "PairedEventsPlugin"),
    "PositionReconstructionPlugin": (
        f"{_BUILTIN}.position_reconstruction",
        "PositionReconstructionPlugin",
    ),
    "EnergyReconstructionPlugin": (
        f"{_BUILTIN}.energy_reconstruction",
        "EnergyReconstructionPlugin",
    ),
    "ENERGY_RECONSTRUCTION_DTYPE": (
        f"{_BUILTIN}.energy_reconstruction",
        "ENERGY_RECONSTRUCTION_DTYPE",
    ),
    "FilteredWaveformsPlugin": (
        f"{_BUILTIN}.filtered_waveforms",
        "FilteredWaveformsPlugin",
    ),
    "PeakClassificationPlugin": (
        f"{_BUILTIN}.peak_classification",
        "PeakClassificationPlugin",
    ),
    "PEAK_CLASSIFICATION_DTYPE": (
        f"{_BUILTIN}.peak_classification",
        "PEAK_CLASSIFICATION_DTYPE",
    ),
    "LABEL_S1_S2": (f"{_BUILTIN}.peak_classification", "LABEL_S1_S2"),
    "S1S2PairCandidatesPlugin": (
        f"{_BUILTIN}.s1_s2_pair_candidates",
        "S1S2PairCandidatesPlugin",
    ),
    "S1S2PairSelectionPlugin": (
        f"{_BUILTIN}.s1_s2_pairs",
        "S1S2PairSelectionPlugin",
    ),
    "S1_S2_PAIR_CANDIDATES_DTYPE": (
        f"{_BUILTIN}.s1_s2_pair_candidates",
        "S1_S2_PAIR_CANDIDATES_DTYPE",
    ),
    "FLAG_VALID_TIME": (f"{_BUILTIN}.s1_s2_pair_candidates", "FLAG_VALID_TIME"),
    "FLAG_RATIO_IN_RANGE": (f"{_BUILTIN}.s1_s2_pair_candidates", "FLAG_RATIO_IN_RANGE"),
    "FLAG_S1_LOW_QUALITY": (f"{_BUILTIN}.s1_s2_pair_candidates", "FLAG_S1_LOW_QUALITY"),
    "FLAG_S2_LOW_QUALITY": (f"{_BUILTIN}.s1_s2_pair_candidates", "FLAG_S2_LOW_QUALITY"),
    "FLAG_MULTI_S1_CANDIDATE": (
        f"{_BUILTIN}.s1_s2_pair_candidates",
        "FLAG_MULTI_S1_CANDIDATE",
    ),
    "FLAG_MULTI_S2_CANDIDATE": (
        f"{_BUILTIN}.s1_s2_pair_candidates",
        "FLAG_MULTI_S2_CANDIDATE",
    ),
    "FLAG_CLOSE_COMPETITOR": (
        f"{_BUILTIN}.s1_s2_pair_candidates",
        "FLAG_CLOSE_COMPETITOR",
    ),
    "FLAG_ORPHAN_S1": (f"{_BUILTIN}.s1_s2_pair_candidates", "FLAG_ORPHAN_S1"),
    "FLAG_ORPHAN_S2": (f"{_BUILTIN}.s1_s2_pair_candidates", "FLAG_ORPHAN_S2"),
    "FLAG_NEAR_CHUNK_BOUNDARY": (
        f"{_BUILTIN}.s1_s2_pair_candidates",
        "FLAG_NEAR_CHUNK_BOUNDARY",
    ),
    "WaveformWidthPlugin": (f"{_BUILTIN}.waveform_width", "WaveformWidthPlugin"),
    "WAVEFORM_WIDTH_DTYPE": (f"{_BUILTIN}.waveform_width", "WAVEFORM_WIDTH_DTYPE"),
    "WaveformWidthIntegralPlugin": (
        f"{_BUILTIN}.waveform_width_integral",
        "WaveformWidthIntegralPlugin",
    ),
    "WAVEFORM_WIDTH_INTEGRAL_DTYPE": (
        f"{_BUILTIN}.waveform_width_integral",
        "WAVEFORM_WIDTH_INTEGRAL_DTYPE",
    ),
    "CacheAnalysisPlugin": (f"{_BUILTIN}.cache_analysis", "CacheAnalysisPlugin"),
    "RecordsPlugin": (f"{_BUILTIN}.records", "RecordsPlugin"),
    "WavePoolPlugin": (f"{_BUILTIN}.wave_pool", "WavePoolPlugin"),
    "WavePoolFilteredPlugin": (
        f"{_BUILTIN}.wave_pool_filtered",
        "WavePoolFilteredPlugin",
    ),
    "RecordsAsymmetryMaskPlugin": (
        f"{_BUILTIN}.records_asymmetry_mask",
        "RecordsAsymmetryMaskPlugin",
    ),
    "RecordsDetectorMaskPlugin": (
        f"{_BUILTIN}.records_detector_mask",
        "RecordsDetectorMaskPlugin",
    ),
    "RecordsVetoMaskPlugin": (
        f"{_BUILTIN}.records_veto_mask",
        "RecordsVetoMaskPlugin",
    ),
    # Hit compatibility exports.
    "HitGroupedPlugin": (f"{_BUILTIN}.hit_grouped", "HitGroupedPlugin"),
    "ThresholdHitPlugin": (f"{_BUILTIN}.hit_threshold", "ThresholdHitPlugin"),
    "HitMergePlugin": (f"{_BUILTIN}.hit_merged", "HitMergePlugin"),
    "HitMergeClustersPlugin": (
        f"{_BUILTIN}.hit_merge_clusters",
        "HitMergeClustersPlugin",
    ),
    "HitMergedComponentsPlugin": (
        f"{_BUILTIN}.hit_merged_components",
        "HitMergedComponentsPlugin",
    ),
    "HitMergedFeaturesPlugin": (
        f"{_BUILTIN}.hit_merged_features",
        "HitMergedFeaturesPlugin",
    ),
    "THRESHOLD_HIT_DTYPE": (f"{_BUILTIN}.hit_threshold", "THRESHOLD_HIT_DTYPE"),
    "HIT_MERGED_DTYPE": (f"{_BUILTIN}.hit_merged", "HIT_MERGED_DTYPE"),
    "HIT_MERGE_CLUSTERS_DTYPE": (
        f"{_BUILTIN}.hit_merge_clusters",
        "HIT_MERGE_CLUSTERS_DTYPE",
    ),
    "HIT_MERGED_COMPONENTS_DTYPE": (
        f"{_BUILTIN}.hit_merged_components",
        "HIT_MERGED_COMPONENTS_DTYPE",
    ),
    "HIT_MERGED_FEATURES_DTYPE": (
        f"{_BUILTIN}.hit_merged_features",
        "HIT_MERGED_FEATURES_DTYPE",
    ),
    # Peaklet compatibility exports.
    "PeakletPlugin": (f"{_BUILTIN}.peaklets", "PeakletPlugin"),
    "PeakletComponentsPlugin": (
        f"{_BUILTIN}.peaklet_components",
        "PeakletComponentsPlugin",
    ),
    "PeakletWaveformPlugin": (
        f"{_BUILTIN}.peaklet_waveforms",
        "PeakletWaveformPlugin",
    ),
    "PeakletWaveformPoolPlugin": (
        f"{_BUILTIN}.peaklet_waveform_pool",
        "PeakletWaveformPoolPlugin",
    ),
    "PeakletFeaturesPlugin": (
        f"{_BUILTIN}.peaklet_features",
        "PeakletFeaturesPlugin",
    ),
    "PeakletChannelsPlugin": (
        f"{_BUILTIN}.peaklet_channels",
        "PeakletChannelsPlugin",
    ),
    "PeaksPlugin": (f"{_BUILTIN}.peaks", "PeaksPlugin"),
    "PEAKLET_DTYPE": (f"{_BUILTIN}.peaklets", "PEAKLET_DTYPE"),
    "PEAKLET_COMPONENTS_DTYPE": (
        f"{_BUILTIN}.peaklet_components",
        "PEAKLET_COMPONENTS_DTYPE",
    ),
    "PEAKLET_WAVEFORMS_DTYPE": (
        f"{_BUILTIN}.peaklet_waveforms",
        "PEAKLET_WAVEFORMS_DTYPE",
    ),
    "PEAKLET_FEATURES_DTYPE": (
        f"{_BUILTIN}.peaklet_features",
        "PEAKLET_FEATURES_DTYPE",
    ),
    "PEAKLET_CHANNELS_DTYPE": (
        f"{_BUILTIN}.peaklet_channels",
        "PEAKLET_CHANNELS_DTYPE",
    ),
    "PEAKS_DTYPE": (f"{_BUILTIN}.peaks", "PEAKS_DTYPE"),
    # Legacy S1/S2 classifier exports intentionally stay on the old module.
    "S1S2ClassifierPlugin": (f"{__name__}.s1_s2_classifier", "S1S2ClassifierPlugin"),
    "S1_S2_CLASSIFIER_DTYPE": (
        f"{__name__}.s1_s2_classifier",
        "S1_S2_CLASSIFIER_DTYPE",
    ),
    "LABEL_S1": (f"{__name__}.s1_s2_classifier", "LABEL_S1"),
    "LABEL_S2": (f"{__name__}.s1_s2_classifier", "LABEL_S2"),
    "LABEL_UNKNOWN": (f"{__name__}.s1_s2_classifier", "LABEL_UNKNOWN"),
    # Compatibility profile/list entries.
    "cpu_default": ("waveform_analysis.core.plugins.profiles", "cpu_default"),
    # Historical child modules which were visible after eager imports.
    "_dt_compat": (f"{__name__}._dt_compat", None),
    "_record_utils": (f"{__name__}._record_utils", None),
    "_wave_source": (f"{__name__}._wave_source", None),
    "filtering": (f"{__name__}.filtering", None),
    "peak_finding": (f"{__name__}.peak_finding", None),
    "s1_s2_classifier": (f"{__name__}.s1_s2_classifier", None),
}

# Keep the migration-era private names available for compatibility tooling.
_ALIASES = {
    "StWaveformsPlugin": "WaveformsPlugin",
    "RawFilesPlugin": "RawFileNamesPlugin",
}
_LAZY_IMPORTS = {
    name: module_name
    for name, (module_name, attribute_name) in _LAZY_EXPORTS.items()
    if attribute_name is not None
}


def __getattr__(name: str):
    if name == "standard_plugins":
        cpu_default_factory = globals().get("cpu_default")
        if cpu_default_factory is None:
            cpu_default_factory = _resolve_lazy_attribute("cpu_default", _LAZY_EXPORTS, globals())
        value = cpu_default_factory()
        globals()[name] = value
        return value
    return _resolve_lazy_attribute(name, _LAZY_EXPORTS, globals())


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


def __dir__():
    return _lazy_dir(globals(), _LAZY_EXPORTS, __all__)
