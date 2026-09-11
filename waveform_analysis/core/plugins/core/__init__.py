"""
Plugins Core 子模块 - 插件系统核心基础设施

提供插件系统的基础类、加载器、统计收集器、热重载和适配器。

主要组件：
- Plugin/Option: 插件基类和配置选项
- StreamingPlugin: 流式插件基类
- BatchProcessingPlugin: 批量流处理插件基类
- PluginLoader: 插件动态加载器
- PluginStatsCollector: 插件性能统计
- PluginHotReloader: 插件热重载
- StraxPluginAdapter: Strax 插件适配器

向后兼容：
所有导出的类和函数可以通过以下方式导入：
    from waveform_analysis.core.plugins.core import Plugin
    from waveform_analysis.core import Plugin  # 通过 core.__init__.py 兼容
"""

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
    # 插件契约规范
    "PluginSpec",
    "OutputSchema",
    "FieldSpec",
    "InputRequirement",
    "Capabilities",
    "ConfigField",
    # 流式插件
    "StreamingPlugin",
    "StreamingContext",
    # 批量流处理插件
    "BatchProcessingPlugin",
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
]


_LAZY_EXPORTS: dict[str, _LazyExport] = {
    # Plugin base classes and options.
    "Plugin": (".base", "Plugin"),
    "Option": (".base", "Option"),
    "option": (".base", "option"),
    "takes_config": (".base", "takes_config"),
    # Plugin contract specifications.
    "PluginSpec": (".spec", "PluginSpec"),
    "OutputSchema": (".spec", "OutputSchema"),
    "FieldSpec": (".spec", "FieldSpec"),
    "InputRequirement": (".spec", "InputRequirement"),
    "Capabilities": (".spec", "Capabilities"),
    "ConfigField": (".spec", "ConfigField"),
    # Streaming and batch processing.
    "StreamingPlugin": (".streaming", "StreamingPlugin"),
    "StreamingContext": (".streaming", "StreamingContext"),
    "BatchProcessingPlugin": (".batch_processing", "BatchProcessingPlugin"),
    # Plugin loading and statistics.
    "PluginLoader": (".loader", "PluginLoader"),
    "load_plugins_from_entry_points": (".loader", "load_plugins_from_entry_points"),
    "load_plugins_from_directory": (".loader", "load_plugins_from_directory"),
    "PluginExecutionRecord": (".stats", "PluginExecutionRecord"),
    "PluginStatistics": (".stats", "PluginStatistics"),
    "PluginStatsCollector": (".stats", "PluginStatsCollector"),
    "get_stats_collector": (".stats", "get_stats_collector"),
    # Hot reload support.
    "PluginHotReloader": (".hot_reload", "PluginHotReloader"),
    "enable_hot_reload": (".hot_reload", "enable_hot_reload"),
    # Strax adapters.
    "StraxPluginAdapter": (".adapters", "StraxPluginAdapter"),
    "StraxContextAdapter": (".adapters", "StraxContextAdapter"),
    "wrap_strax_plugin": (".adapters", "wrap_strax_plugin"),
    "create_strax_context": (".adapters", "create_strax_context"),
    "strax_dtype_to_numpy": (".adapters", "strax_dtype_to_numpy"),
    "numpy_dtype_to_strax": (".adapters", "numpy_dtype_to_strax"),
    # Preserve direct access to the historical child modules in dir()/getattr().
    "adapters": (".adapters", None),
    "base": (".base", None),
    "batch_processing": (".batch_processing", None),
    "hot_reload": (".hot_reload", None),
    "loader": (".loader", None),
    "spec": (".spec", None),
    "stats": (".stats", None),
    "streaming": (".streaming", None),
}

_LAZY_ATTRS = _LAZY_EXPORTS


def __getattr__(name: str):
    return _resolve_lazy_attribute(name, _LAZY_EXPORTS, globals())


def __dir__():
    return _lazy_dir(globals(), _LAZY_EXPORTS, __all__)
