"""
Plugins Core 子模块 - 插件系统核心基础设施

提供插件系统的基础类、加载器、统计收集器、热重载和适配器。

主要组件：
- Plugin/Option: 插件基类和配置选项
- StreamingPlugin: 流式插件基类
- PluginLoader: 插件动态加载器
- PluginStatsCollector: 插件性能统计
- PluginHotReloader: 插件热重载
- StraxPluginAdapter: Strax 插件适配器

向后兼容：
所有导出的类和函数可以通过以下方式导入：
    from waveform_analysis.core.plugins.core import Plugin
    from waveform_analysis.core import Plugin  # 通过 core.__init__.py 兼容
"""

# 插件基类和配置
# Strax 适配器
from .adapters import (
    StraxContextAdapter,
    StraxPluginAdapter,
    create_strax_context,
    numpy_dtype_to_strax,
    strax_dtype_to_numpy,
    wrap_strax_plugin,
)
from .base import (
    Option,
    Plugin,
    option,
    takes_config,
)

# 插件热重载
from .hot_reload import (
    PluginHotReloader,
    enable_hot_reload,
)

# 插件加载器
from .loader import (
    PluginLoader,
    load_plugins_from_directory,
    load_plugins_from_entry_points,
)

# 插件契约规范
from .spec import (
    Capabilities,
    ConfigField,
    FieldSpec,
    InputRequirement,
    OutputSchema,
    PluginSpec,
)

# 插件统计
from .stats import (
    PluginExecutionRecord,
    PluginStatistics,
    PluginStatsCollector,
    get_stats_collector,
)

# 流式插件
from .streaming import (
    StreamingContext,
    StreamingPlugin,
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
