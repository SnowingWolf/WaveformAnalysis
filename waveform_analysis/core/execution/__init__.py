"""
Execution 子模块 - 并行执行和超时管理

提供统一的执行器管理、并行计算和超时控制功能。

主要组件：
- ExecutorManager: 执行器池管理
- TimeoutManager: 超时控制管理
- Executor Configs: 预定义的执行器配置

向后兼容：
所有导出的类和函数可以通过以下方式导入：
    from waveform_analysis.core.execution import get_executor
    from waveform_analysis.core import get_executor  # 通过 core.__init__.py 兼容
"""

from waveform_analysis._lazy_exports import LazyExport as _LazyExport
from waveform_analysis._lazy_exports import lazy_dir as _lazy_dir
from waveform_analysis._lazy_exports import (
    resolve_lazy_attribute as _resolve_lazy_attribute,
)

_LAZY_EXPORTS: dict[str, _LazyExport] = {
    # 执行器管理
    "ExecutorManager": (".manager", "ExecutorManager"),
    "get_executor_manager": (".manager", "get_executor_manager"),
    "get_executor": (".manager", "get_executor"),
    "parallel_map": (".manager", "parallel_map"),
    "parallel_apply": (".manager", "parallel_apply"),
    # 进度配置
    "ParallelProgressConfig": (".manager", "ParallelProgressConfig"),
    "parallel_progress": (".manager", "parallel_progress"),
    "configure_default_workers": (".manager", "configure_default_workers"),
    "get_default_workers": (".manager", "get_default_workers"),
    "get_stats": (".manager", "get_stats"),
    # 负载均衡
    "enable_global_load_balancing": (".manager", "enable_global_load_balancing"),
    "disable_global_load_balancing": (".manager", "disable_global_load_balancing"),
    "get_load_balancer_stats": (".manager", "get_load_balancer_stats"),
    # 执行器配置
    "EXECUTOR_CONFIGS": (".config", "EXECUTOR_CONFIGS"),
    "get_config": (".config", "get_config"),
    "register_config": (".config", "register_config"),
    # 超时管理
    "TimeoutManager": (".timeout", "TimeoutManager"),
    "get_timeout_manager": (".timeout", "get_timeout_manager"),
    "with_timeout": (".timeout", "with_timeout"),
    # 验证管理
    "ValidationManager": (".validation", "ValidationManager"),
}

__all__ = [
    # 执行器管理
    "ExecutorManager",
    "get_executor_manager",
    "get_executor",
    "parallel_map",
    "parallel_apply",
    # 进度配置
    "ParallelProgressConfig",
    "parallel_progress",
    "configure_default_workers",
    "get_default_workers",
    "get_stats",
    # 负载均衡
    "enable_global_load_balancing",
    "disable_global_load_balancing",
    "get_load_balancer_stats",
    # 执行器配置
    "EXECUTOR_CONFIGS",
    "get_config",
    "register_config",
    # 超时管理
    "TimeoutManager",
    "get_timeout_manager",
    "with_timeout",
    # 验证管理
    "ValidationManager",
]


def __getattr__(name: str) -> object:
    return _resolve_lazy_attribute(name, _LAZY_EXPORTS, globals())


def __dir__() -> list[str]:
    return _lazy_dir(globals(), _LAZY_EXPORTS, __all__)
