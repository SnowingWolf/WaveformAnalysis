"""
Plugins 子模块 - 插件系统统一入口

将核心基础设施 (core) 和内置插件 (builtin) 统一导出，提供向后兼容的导入路径。

使用方法：
    # 导入插件基类
    from waveform_analysis.core.plugins import Plugin, Option

    # 导入内置插件
    from waveform_analysis.core.plugins import RawFileNamesPlugin, WaveformsPlugin

    # 导入插件加载器
    from waveform_analysis.core.plugins import PluginLoader

    # 导入热重载功能
    from waveform_analysis.core.plugins import enable_hot_reload

新路径推荐：
    # 核心基础设施
    from waveform_analysis.core.plugins.core import Plugin, StreamingPlugin

    # 内置插件
    from waveform_analysis.core.plugins.builtin.cpu import RawFileNamesPlugin

向后兼容：
    from waveform_analysis.core import Plugin  # 仍然可用
"""

from importlib import import_module

from waveform_analysis._lazy_exports import LazyExport as _LazyExport
from waveform_analysis._lazy_exports import lazy_dir as _lazy_dir
from waveform_analysis._lazy_exports import (
    resolve_lazy_attribute as _resolve_lazy_attribute,
)

__all__ = [
    # 插件基类
    "Plugin",
    "Option",
    "option",
    "takes_config",
    # 流式插件
    "StreamingPlugin",
    "StreamingContext",
    # 插件加载器
    "PluginLoader",
    "load_plugins_from_entry_points",
    "load_plugins_from_directory",
    # 插件统计
    "PluginExecutionRecord",
    "PluginStatistics",
    "PluginStatsCollector",
    "get_stats_collector",
    # 插件热重载
    "PluginHotReloader",
    "enable_hot_reload",
    # Strax 适配器
    "StraxPluginAdapter",
    "StraxContextAdapter",
    "wrap_strax_plugin",
    "create_strax_context",
    "strax_dtype_to_numpy",
    "numpy_dtype_to_strax",
    # 标准插件
    "RawFileNamesPlugin",
    "WaveformsPlugin",
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
    "RecordsAsymmetryMaskPlugin",
    "RecordsDetectorMaskPlugin",
    "RecordsVetoMaskPlugin",
    # 信号处理插件
    "FilteredWaveformsPlugin",
    "WaveformWidthPlugin",
    "SignalPeaksStreamPlugin",
    # plugin sets / profiles
    "plugin_sets",
    "profiles",
]


_LAZY_EXPORTS: dict[str, _LazyExport] = {
    # Aggregate modules.
    "plugin_sets": (".plugin_sets", None),
    "profiles": (".profiles", None),
    # Builtin plugin bundles.
    "BasicFeaturesPlugin": (".builtin.basic_features", "BasicFeaturesPlugin"),
    "DataFramePlugin": (".builtin.df", "DataFramePlugin"),
    "FilteredWaveformsPlugin": (".builtin.filtered_waveforms", "FilteredWaveformsPlugin"),
    "GroupedEventsPlugin": (".builtin.df_events", "GroupedEventsPlugin"),
    "HitFinderPlugin": (".builtin.hit", "HitFinderPlugin"),
    "PairedEventsPlugin": (".builtin.df_paired", "PairedEventsPlugin"),
    "RawFileNamesPlugin": (".builtin.raw_files", "RawFileNamesPlugin"),
    "RecordsPlugin": (".builtin.records", "RecordsPlugin"),
    "WavePoolPlugin": (".builtin.wave_pool", "WavePoolPlugin"),
    "WavePoolFilteredPlugin": (".builtin.wave_pool_filtered", "WavePoolFilteredPlugin"),
    "RecordsAsymmetryMaskPlugin": (
        ".builtin.records_asymmetry_mask",
        "RecordsAsymmetryMaskPlugin",
    ),
    "RecordsDetectorMaskPlugin": (
        ".builtin.records_detector_mask",
        "RecordsDetectorMaskPlugin",
    ),
    "RecordsVetoMaskPlugin": (".builtin.records_veto_mask", "RecordsVetoMaskPlugin"),
    "WaveformsPlugin": (".builtin.st_waveforms", "WaveformsPlugin"),
    "WaveformStruct": (".builtin.st_waveforms", "WaveformStruct"),
    "WaveformStructConfig": (".builtin.st_waveforms", "WaveformStructConfig"),
    "WaveformWidthPlugin": (".builtin.waveform_width", "WaveformWidthPlugin"),
    "SignalPeaksStreamPlugin": (".builtin.signal_peaks_stream", "SignalPeaksStreamPlugin"),
    # Peaklet plugins - compatibility exports for the new bundle locations.
    "PeakletPlugin": (".builtin.peaklets", "PeakletPlugin"),
    "PeakletComponentsPlugin": (".builtin.peaklet_components", "PeakletComponentsPlugin"),
    "PeakletWaveformPlugin": (".builtin.peaklet_waveforms", "PeakletWaveformPlugin"),
    "PeakletWaveformPoolPlugin": (
        ".builtin.peaklet_waveform_pool",
        "PeakletWaveformPoolPlugin",
    ),
    "PeakletFeaturesPlugin": (".builtin.peaklet_features", "PeakletFeaturesPlugin"),
    "PeaksPlugin": (".builtin.peaks", "PeaksPlugin"),
    "PeakletChannelsPlugin": (".builtin.peaklet_channels", "PeakletChannelsPlugin"),
    # Hit plugins - compatibility exports for the per-provides bundles.
    "HitGroupedPlugin": (".builtin.hit_grouped", "HitGroupedPlugin"),
    "ThresholdHitPlugin": (".builtin.hit_threshold", "ThresholdHitPlugin"),
    "HitMergePlugin": (".builtin.hit_merged", "HitMergePlugin"),
    "HitMergeClustersPlugin": (".builtin.hit_merge_clusters", "HitMergeClustersPlugin"),
    "HitMergedComponentsPlugin": (
        ".builtin.hit_merged_components",
        "HitMergedComponentsPlugin",
    ),
    "HitMergedFeaturesPlugin": (
        ".builtin.hit_merged_features",
        "HitMergedFeaturesPlugin",
    ),
    # Core infrastructure.
    "Option": (".core.base", "Option"),
    "Plugin": (".core.base", "Plugin"),
    "PluginExecutionRecord": (".core.stats", "PluginExecutionRecord"),
    "PluginHotReloader": (".core.hot_reload", "PluginHotReloader"),
    "PluginLoader": (".core.loader", "PluginLoader"),
    "PluginStatistics": (".core.stats", "PluginStatistics"),
    "PluginStatsCollector": (".core.stats", "PluginStatsCollector"),
    "StraxContextAdapter": (".core.adapters", "StraxContextAdapter"),
    "StraxPluginAdapter": (".core.adapters", "StraxPluginAdapter"),
    "StreamingContext": (".core.streaming", "StreamingContext"),
    "StreamingPlugin": (".core.streaming", "StreamingPlugin"),
    "create_strax_context": (".core.adapters", "create_strax_context"),
    "enable_hot_reload": (".core.hot_reload", "enable_hot_reload"),
    "get_stats_collector": (".core.stats", "get_stats_collector"),
    "load_plugins_from_directory": (".core.loader", "load_plugins_from_directory"),
    "load_plugins_from_entry_points": (".core.loader", "load_plugins_from_entry_points"),
    "numpy_dtype_to_strax": (".core.adapters", "numpy_dtype_to_strax"),
    "option": (".core.base", "option"),
    "strax_dtype_to_numpy": (".core.adapters", "strax_dtype_to_numpy"),
    "takes_config": (".core.base", "takes_config"),
    "wrap_strax_plugin": (".core.adapters", "wrap_strax_plugin"),
}

# Keep the historical private map name available to callers that inspected it.
_LAZY_ATTRS = _LAZY_EXPORTS

_PUBLIC_SUBMODULES = ("builtin", "core", "plugin_sets", "profiles")


def __getattr__(name: str):
    return _resolve_lazy_attribute(name, _LAZY_EXPORTS, globals())


def __dir__():
    return _lazy_dir(globals(), _LAZY_EXPORTS, (*__all__, *_PUBLIC_SUBMODULES))
