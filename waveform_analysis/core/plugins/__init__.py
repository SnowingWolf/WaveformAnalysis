# -*- coding: utf-8 -*-
"""
Plugins 子模块 - 插件系统统一入口

将核心基础设施 (core) 和内置插件 (builtin) 统一导出，提供向后兼容的导入路径。

使用方法：
    # 导入插件基类
    from waveform_analysis.core.plugins import Plugin, Option

    # 导入内置插件
    from waveform_analysis.core.plugins import RawFilesPlugin, WaveformsPlugin

    # 导入插件加载器
    from waveform_analysis.core.plugins import PluginLoader

    # 导入热重载功能
    from waveform_analysis.core.plugins import enable_hot_reload

新路径推荐：
    # 核心基础设施
    from waveform_analysis.core.plugins.core import Plugin, StreamingPlugin

    # 内置插件
    from waveform_analysis.core.plugins.builtin.cpu import RawFilesPlugin

向后兼容：
    from waveform_analysis.core import Plugin  # 仍然可用
"""

# 从 core 子模块导出核心基础设施
# 从 builtin 子模块导出内置插件
from .builtin.cpu import (
    ChargesPlugin,
    DataFramePlugin,
    # 信号处理插件
    FilteredWaveformsPlugin,
    GroupedEventsPlugin,
    HitFinderPlugin,
    PairedEventsPlugin,
    PeaksPlugin,
    RecordsPlugin,
    # 标准插件
    RawFilesPlugin,
    SignalPeaksPlugin,
    StWaveformsPlugin,
    WaveformsPlugin,
    WavePoolPlugin,
    WaveformWidthPlugin,
)
from .builtin.streaming import SignalPeaksStreamPlugin
from .core import (
    Option,
    # 插件基类
    Plugin,
    # 插件统计
    PluginExecutionRecord,
    # 插件热重载
    PluginHotReloader,
    # 插件加载器
    PluginLoader,
    PluginStatistics,
    PluginStatsCollector,
    StraxContextAdapter,
    # Strax 适配器
    StraxPluginAdapter,
    StreamingContext,
    # 流式插件
    StreamingPlugin,
    create_strax_context,
    enable_hot_reload,
    get_stats_collector,
    load_plugins_from_directory,
    load_plugins_from_entry_points,
    numpy_dtype_to_strax,
    option,
    strax_dtype_to_numpy,
    takes_config,
    wrap_strax_plugin,
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
    "RawFilesPlugin",
    "WaveformsPlugin",
    "StWaveformsPlugin",
    "HitFinderPlugin",
    "PeaksPlugin",
    "ChargesPlugin",
    "DataFramePlugin",
    "GroupedEventsPlugin",
    "PairedEventsPlugin",
    "RecordsPlugin",
    # 信号处理插件
    "FilteredWaveformsPlugin",
    "SignalPeaksPlugin",
    "WaveformWidthPlugin",
    "SignalPeaksStreamPlugin",
    "WavePoolPlugin",
]
