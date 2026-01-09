# -*- coding: utf-8 -*-
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

# 执行器管理
from .manager import (
    ExecutorManager,
    get_executor_manager,
    get_executor,
    parallel_map,
    parallel_apply,
    ParallelProgressConfig,
    parallel_progress,
    configure_default_workers,
    get_default_workers,
    get_stats,
)

# 执行器配置
from .config import (
    EXECUTOR_CONFIGS,
    get_config,
    register_config,
)

# 超时管理
from .timeout import (
    TimeoutManager,
    get_timeout_manager,
    with_timeout,
)

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
    # 执行器配置
    "EXECUTOR_CONFIGS",
    "get_config",
    "register_config",
    # 超时管理
    "TimeoutManager",
    "get_timeout_manager",
    "with_timeout",
]
