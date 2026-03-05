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
from typing import Dict, Optional, Tuple

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
    "EventsPlugin",
    "EventFramePlugin",
    "EventsGroupedPlugin",
    # 信号处理插件
    "FilteredWaveformsPlugin",
    "SignalPeaksPlugin",
    "WaveformWidthPlugin",
    "SignalPeaksStreamPlugin",
    # plugin sets / profiles
    "plugin_sets",
    "profiles",
]


_LAZY_ATTRS: Dict[str, Tuple[str, Optional[str]]] = {
    "plugin_sets": (".plugin_sets", None),
    "profiles": (".profiles", None),
    "BasicFeaturesPlugin": (".builtin.cpu", "BasicFeaturesPlugin"),
    "DataFramePlugin": (".builtin.cpu", "DataFramePlugin"),
    "EventFramePlugin": (".builtin.cpu", "EventFramePlugin"),
    "EventsGroupedPlugin": (".builtin.cpu", "EventsGroupedPlugin"),
    "EventsPlugin": (".builtin.cpu", "EventsPlugin"),
    "FilteredWaveformsPlugin": (".builtin.cpu", "FilteredWaveformsPlugin"),
    "GroupedEventsPlugin": (".builtin.cpu", "GroupedEventsPlugin"),
    "HitFinderPlugin": (".builtin.cpu", "HitFinderPlugin"),
    "PairedEventsPlugin": (".builtin.cpu", "PairedEventsPlugin"),
    "RawFileNamesPlugin": (".builtin.cpu", "RawFileNamesPlugin"),
    "RecordsPlugin": (".builtin.cpu", "RecordsPlugin"),
    "SignalPeaksPlugin": (".builtin.cpu", "SignalPeaksPlugin"),
    "WaveformsPlugin": (".builtin.cpu", "WaveformsPlugin"),
    "WaveformStruct": (".builtin.cpu", "WaveformStruct"),
    "WaveformStructConfig": (".builtin.cpu", "WaveformStructConfig"),
    "WaveformWidthPlugin": (".builtin.cpu", "WaveformWidthPlugin"),
    "SignalPeaksStreamPlugin": (".builtin.streaming", "SignalPeaksStreamPlugin"),
    "Option": (".core", "Option"),
    "Plugin": (".core", "Plugin"),
    "PluginExecutionRecord": (".core", "PluginExecutionRecord"),
    "PluginHotReloader": (".core", "PluginHotReloader"),
    "PluginLoader": (".core", "PluginLoader"),
    "PluginStatistics": (".core", "PluginStatistics"),
    "PluginStatsCollector": (".core", "PluginStatsCollector"),
    "StraxContextAdapter": (".core", "StraxContextAdapter"),
    "StraxPluginAdapter": (".core", "StraxPluginAdapter"),
    "StreamingContext": (".core", "StreamingContext"),
    "StreamingPlugin": (".core", "StreamingPlugin"),
    "create_strax_context": (".core", "create_strax_context"),
    "enable_hot_reload": (".core", "enable_hot_reload"),
    "get_stats_collector": (".core", "get_stats_collector"),
    "load_plugins_from_directory": (".core", "load_plugins_from_directory"),
    "load_plugins_from_entry_points": (".core", "load_plugins_from_entry_points"),
    "numpy_dtype_to_strax": (".core", "numpy_dtype_to_strax"),
    "option": (".core", "option"),
    "strax_dtype_to_numpy": (".core", "strax_dtype_to_numpy"),
    "takes_config": (".core", "takes_config"),
    "wrap_strax_plugin": (".core", "wrap_strax_plugin"),
}


def __getattr__(name: str):
    if name in _LAZY_ATTRS:
        module_name, attr_name = _LAZY_ATTRS[name]
        module = import_module(module_name, __name__)
        value = getattr(module, attr_name) if attr_name else module
        globals()[name] = value
        return value
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


def __dir__():
    return sorted(set(globals()) | set(__all__) | set(_LAZY_ATTRS))
