"""
配置系统模块

提供统一的配置解析、兼容层管理和 adapter 推断功能。

核心组件:
- ConfigResolver: 配置解析器，统一处理配置值的解析
- CompatManager: 兼容层管理器，处理参数别名和弃用
- AdapterInfo: DAQ adapter 信息，用于配置推断
- ResolvedConfig: 解析后的配置集合

Examples:
    基础用法:
    >>> from waveform_analysis.core.config import ConfigResolver, get_adapter_info
    >>> resolver = ConfigResolver()
    >>> resolved = resolver.resolve(plugin, config, adapter_name="vx2730")
    >>> print(resolved.get("sampling_rate_hz"))
    500000000.0

    查看配置来源:
    >>> print(resolved.summary(verbose=True))

    兼容层管理:
    >>> from waveform_analysis.core.config import CompatManager
    >>> manager = CompatManager()
    >>> canonical, alias_used = manager.resolve_alias("peaks", "old_param")
"""

# 类型定义
# Adapter 信息
from .adapter_info import (
    AdapterInfo,
    clear_adapter_info_cache,
    get_adapter_info,
)

# 兼容层管理
from .compat import (
    CompatManager,
    DeprecationInfo,
    get_default_compat_manager,
)

# 配置解析器
from .resolver import (
    ConfigResolver,
)
from .types import (
    ConfigSource,
    ConfigValue,
    ResolvedConfig,
)

__all__ = [
    # 类型
    "ConfigSource",
    "ConfigValue",
    "ResolvedConfig",
    # Adapter
    "AdapterInfo",
    "get_adapter_info",
    "clear_adapter_info_cache",
    # 解析器
    "ConfigResolver",
    # 兼容层
    "CompatManager",
    "DeprecationInfo",
    "get_default_compat_manager",
]
