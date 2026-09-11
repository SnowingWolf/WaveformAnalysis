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

from waveform_analysis._lazy_exports import LazyExport as _LazyExport
from waveform_analysis._lazy_exports import lazy_dir as _lazy_dir
from waveform_analysis._lazy_exports import (
    resolve_lazy_attribute as _resolve_lazy_attribute,
)

_LAZY_EXPORTS: dict[str, _LazyExport] = {
    # 类型
    "ConfigSource": (".types", "ConfigSource"),
    "ConfigValue": (".types", "ConfigValue"),
    "ResolvedConfig": (".types", "ResolvedConfig"),
    # Adapter
    "AdapterInfo": (".adapter_info", "AdapterInfo"),
    "get_adapter_info": (".adapter_info", "get_adapter_info"),
    "clear_adapter_info_cache": (".adapter_info", "clear_adapter_info_cache"),
    # 解析器
    "ConfigResolver": (".resolver", "ConfigResolver"),
    "RUN_NUMBER_PATTERN": (".run_config", "RUN_NUMBER_PATTERN"),
    "VALID_DAQ_STATUSES": (".run_config", "VALID_DAQ_STATUSES"),
    "VALID_POLARITIES": (".run_config", "VALID_POLARITIES"),
    "RunConfigValidationError": (".run_config", "RunConfigValidationError"),
    "resolve_run_hardware_channels": (
        ".run_config",
        "resolve_run_hardware_channels",
    ),
    "validate_run_config": (".run_config", "validate_run_config"),
    # 兼容层
    "CompatManager": (".compat", "CompatManager"),
    "DeprecationInfo": (".compat", "DeprecationInfo"),
    "get_default_compat_manager": (".compat", "get_default_compat_manager"),
}

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
    "RUN_NUMBER_PATTERN",
    "VALID_DAQ_STATUSES",
    "VALID_POLARITIES",
    "RunConfigValidationError",
    "resolve_run_hardware_channels",
    "validate_run_config",
    # 兼容层
    "CompatManager",
    "DeprecationInfo",
    "get_default_compat_manager",
]


def __getattr__(name: str) -> object:
    return _resolve_lazy_attribute(name, _LAZY_EXPORTS, globals())


def __dir__() -> list[str]:
    return _lazy_dir(globals(), _LAZY_EXPORTS, __all__)
