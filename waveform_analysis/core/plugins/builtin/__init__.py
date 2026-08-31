"""
Plugins Builtin 子模块 - 内置标准插件

本模块采用按加速器划分的插件架构（自 2026-01 版本起）：

**CPU 插件** (`builtin/cpu/`):
- 标准数据处理插件: RawFileNames, Waveforms (合并了 StWaveforms), Features, DataFrame, Events
- 滤波插件: FilteredWaveformsPlugin (scipy)
- 寻峰插件: HitFinderPlugin (scipy)

**JAX 插件** (`builtin/jax/`):
- 待实现：JAX 加速版本的滤波和寻峰插件

**流式插件** (`builtin/streaming/`):
- CPU 流式插件: SignalPeaksStreamPlugin
- JAX 流式插件待实现

向后兼容：
所有插件可以通过以下方式导入：
    from waveform_analysis.core.plugins.builtin.cpu import RawFileNamesPlugin
"""

from waveform_analysis._lazy_exports import LazyExport as _LazyExport
from waveform_analysis._lazy_exports import lazy_dir as _lazy_dir
from waveform_analysis._lazy_exports import (
    resolve_lazy_attribute as _resolve_lazy_attribute,
)

__all__ = [
    # 标准插件类
    "RawFileNamesPlugin",
    "RawFilesPlugin",
    "WaveformsPlugin",
    "StWaveformsPlugin",
    "WaveformStruct",
    "WaveformStructConfig",
    "HitFinderPlugin",
    "BasicFeaturesPlugin",
    "DataFramePlugin",
    "GroupedEventsPlugin",
    "PairedEventsPlugin",
    "RecordsPlugin",
    "WavePoolPlugin",
    "WavePoolFilteredPlugin",
    # 信号处理插件
    "FilteredWaveformsPlugin",
    "HIT_DTYPE",
    "WaveformWidthPlugin",
    "WAVEFORM_WIDTH_DTYPE",
    "WaveformWidthIntegralPlugin",
    "WAVEFORM_WIDTH_INTEGRAL_DTYPE",
    "CacheAnalysisPlugin",
    # 流式插件
    "SignalPeaksStreamPlugin",
    # 便捷列表
    "standard_plugins",
]


_LAZY_EXPORTS: dict[str, _LazyExport] = {
    # Canonical bundle exports.  Keep the builtin aggregate independent from
    # ``cpu`` so importing it cannot fan out through every CPU shim.
    "RawFileNamesPlugin": (".raw_files", "RawFileNamesPlugin"),
    "RawFilesPlugin": (".raw_files", "RawFileNamesPlugin"),
    "WaveformsPlugin": (".st_waveforms", "WaveformsPlugin"),
    "StWaveformsPlugin": (".st_waveforms", "WaveformsPlugin"),
    "WaveformStruct": (".st_waveforms", "WaveformStruct"),
    "WaveformStructConfig": (".st_waveforms", "WaveformStructConfig"),
    "HitFinderPlugin": (".hit", "HitFinderPlugin"),
    "BasicFeaturesPlugin": (".basic_features", "BasicFeaturesPlugin"),
    "DataFramePlugin": (".df", "DataFramePlugin"),
    "GroupedEventsPlugin": (".df_events", "GroupedEventsPlugin"),
    "PairedEventsPlugin": (".df_paired", "PairedEventsPlugin"),
    "RecordsPlugin": (".records", "RecordsPlugin"),
    "WavePoolPlugin": (".wave_pool", "WavePoolPlugin"),
    "WavePoolFilteredPlugin": (".wave_pool_filtered", "WavePoolFilteredPlugin"),
    "FilteredWaveformsPlugin": (".filtered_waveforms", "FilteredWaveformsPlugin"),
    "HIT_DTYPE": (".hit", "HIT_DTYPE"),
    "WaveformWidthPlugin": (".waveform_width", "WaveformWidthPlugin"),
    "WAVEFORM_WIDTH_DTYPE": (".waveform_width", "WAVEFORM_WIDTH_DTYPE"),
    "WaveformWidthIntegralPlugin": (
        ".waveform_width_integral",
        "WaveformWidthIntegralPlugin",
    ),
    "WAVEFORM_WIDTH_INTEGRAL_DTYPE": (
        ".waveform_width_integral",
        "WAVEFORM_WIDTH_INTEGRAL_DTYPE",
    ),
    "CacheAnalysisPlugin": (".cache_analysis", "CacheAnalysisPlugin"),
    "SignalPeaksStreamPlugin": (
        ".signal_peaks_stream",
        "SignalPeaksStreamPlugin",
    ),
    # ``standard_plugins`` historically aliases the cached CPU profile list.
    # It is the one aggregate export intentionally resolved through ``cpu``.
    "standard_plugins": (".cpu", "standard_plugins"),
    # Preserve the historical public child-module names in dir()/getattr().
    "basic_features": (".basic_features", None),
    "cache_analysis": (".cache_analysis", None),
    "cpu": (".cpu", None),
    "df": (".df", None),
    "df_events": (".df_events", None),
    "df_paired": (".df_paired", None),
    "energy_reconstruction": (".energy_reconstruction", None),
    "events": (".events", None),
    "filtered_waveforms": (".filtered_waveforms", None),
    "hit": (".hit", None),
    "hit_grouped": (".hit_grouped", None),
    "hit_merge_clusters": (".hit_merge_clusters", None),
    "hit_merged": (".hit_merged", None),
    "hit_merged_components": (".hit_merged_components", None),
    "hit_merged_features": (".hit_merged_features", None),
    "hit_threshold": (".hit_threshold", None),
    "peak_classification": (".peak_classification", None),
    "peaklet_channels": (".peaklet_channels", None),
    "peaklet_components": (".peaklet_components", None),
    "peaklet_features": (".peaklet_features", None),
    "peaklet_waveform_pool": (".peaklet_waveform_pool", None),
    "peaklet_waveforms": (".peaklet_waveforms", None),
    "peaklets": (".peaklets", None),
    "peaks": (".peaks", None),
    "position_reconstruction": (".position_reconstruction", None),
    "raw_files": (".raw_files", None),
    "records": (".records", None),
    "records_asymmetry_mask": (".records_asymmetry_mask", None),
    "records_detector_mask": (".records_detector_mask", None),
    "records_veto_mask": (".records_veto_mask", None),
    "s1_s2_pair_candidates": (".s1_s2_pair_candidates", None),
    "s1_s2_pairs": (".s1_s2_pairs", None),
    "shared": (".shared", None),
    "signal_peaks_stream": (".signal_peaks_stream", None),
    "st_waveforms": (".st_waveforms", None),
    "streaming": (".streaming", None),
    "wave_pool": (".wave_pool", None),
    "wave_pool_filtered": (".wave_pool_filtered", None),
    "waveform_width": (".waveform_width", None),
    "waveform_width_integral": (".waveform_width_integral", None),
}

_LAZY_ATTRS = _LAZY_EXPORTS


def __getattr__(name: str):
    return _resolve_lazy_attribute(name, _LAZY_EXPORTS, globals())


def __dir__():
    return _lazy_dir(globals(), _LAZY_EXPORTS, __all__)
