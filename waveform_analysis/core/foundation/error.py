# -*- coding: utf-8 -*-
"""
错误管理模块 - 提供统一的错误上下文收集和日志记录功能。

从 Context 中提取，提高内聚性和可测试性。
"""

# 1. Standard library imports
from datetime import datetime
import logging
from typing import Any, Callable, Dict

# 2. Third-party imports
import numpy as np
import pandas as pd

# 3. Local imports
from .utils import exporter

export, __all__ = exporter()


@export
class ErrorManager:
    """错误上下文收集和日志管理

    负责在插件执行失败时收集详细的错误上下文信息，
    并根据不同的日志级别输出相应的错误日志。

    Examples:
        >>> logger = logging.getLogger(__name__)
        >>> error_manager = ErrorManager(logger)
        >>>
        >>> # 收集错误上下文
        >>> context = error_manager.collect_context(
        ...     plugin, run_id,
        ...     get_config_fn=ctx.get_config,
        ...     get_data_fn=ctx._get_data_from_memory
        ... )
        >>>
        >>> # 记录错误
        >>> error_manager.log_error(
        ...     plugin_name, exception, run_id, plugin, context,
        ...     get_config_fn=ctx.get_config
        ... )
    """

    def __init__(self, logger: logging.Logger):
        """初始化 ErrorManager

        Args:
            logger: 日志记录器实例
        """
        self.logger = logger

    def collect_context(
        self,
        plugin: Any,
        run_id: str,
        get_config_fn: Callable[[Any, str], Any],
        get_data_fn: Callable[[str, str], Any]
    ) -> Dict[str, Any]:
        """收集错误发生时的上下文信息

        Args:
            plugin: 插件实例
            run_id: 运行 ID
            get_config_fn: 获取配置的回调函数 (plugin, key) -> value
            get_data_fn: 获取数据的回调函数 (run_id, name) -> data

        Returns:
            包含错误上下文的字典，包括：
            - run_id: 运行标识符
            - plugin: 插件提供的数据名
            - plugin_class: 插件类名
            - config: 插件配置
            - dependencies_info: 依赖数据的元信息
            - memory_mb: 内存使用（如果 psutil 可用）
            - timestamp: 错误发生时间
        """
        context = {
            "run_id": run_id,
            "plugin": plugin.provides,
            "plugin_class": plugin.__class__.__name__,
            "config": {k: get_config_fn(plugin, k) for k in plugin.config_keys},
            "timestamp": datetime.now().isoformat()
        }

        # 收集依赖数据信息
        dependencies_info = {}
        for dep in plugin.depends_on:
            dep_name = dep if isinstance(dep, str) else dep[0]
            try:
                dep_data = get_data_fn(run_id, dep_name)
                if dep_data is not None:
                    if isinstance(dep_data, np.ndarray):
                        dependencies_info[dep_name] = {
                            "shape": dep_data.shape,
                            "dtype": str(dep_data.dtype),
                            "size_mb": dep_data.nbytes / (1024 * 1024)
                        }
                    elif isinstance(dep_data, list):
                        dependencies_info[dep_name] = {
                            "length": len(dep_data),
                            "type": type(dep_data[0]).__name__ if dep_data else "empty"
                        }
                    elif isinstance(dep_data, pd.DataFrame):
                        dependencies_info[dep_name] = {
                            "shape": dep_data.shape,
                            "columns": list(dep_data.columns),
                            "size_mb": dep_data.memory_usage(deep=True).sum() / (1024 * 1024)
                        }
            except (AttributeError, TypeError, KeyError) as e:
                # 某些数据类型可能缺少所需的属性
                self.logger.debug(
                    f"Could not collect dependency info for {dep_name}: {e}"
                )
            except Exception as e:
                # 其他未预期的错误（不应该阻止错误报告）
                self.logger.warning(
                    f"Unexpected error collecting dependency info for {dep_name}: {e}"
                )

        context["dependencies_info"] = dependencies_info

        # 内存使用情况（可选，需要 psutil）
        try:
            import psutil
            process = psutil.Process()
            context["memory_mb"] = process.memory_info().rss / (1024 * 1024)
        except ImportError:
            context["memory_mb"] = None

        return context

    def log_error(
        self,
        plugin_name: str,
        exception: Exception,
        run_id: str,
        plugin: Any,
        error_context: Dict[str, Any],
        get_config_fn: Callable[[Any, str], Any]
    ) -> None:
        """统一的错误日志记录

        根据当前日志级别输出不同详细程度的错误信息：
        - DEBUG: 完整的异常栈和错误上下文
        - INFO: 异常类型和消息
        - 其他: 简短的错误消息

        Args:
            plugin_name: 插件名称
            exception: 异常对象
            run_id: 运行 ID
            plugin: 插件实例
            error_context: 错误上下文字典
            get_config_fn: 获取配置的回调函数
        """
        log_level = self.logger.level

        if log_level <= logging.DEBUG:
            # DEBUG 级别：输出完整信息
            self.logger.error(
                f"Plugin '{plugin_name}' ({plugin.__class__.__name__}) failed",
                exc_info=True,
                extra={
                    "run_id": run_id,
                    "plugin_name": plugin_name,
                    "plugin_class": plugin.__class__.__name__,
                    "config": {k: get_config_fn(plugin, k) for k in plugin.config_keys},
                    "error_context": error_context
                }
            )
        elif log_level <= logging.INFO:
            # INFO 级别：输出异常类型和消息
            self.logger.error(
                f"Plugin '{plugin_name}' ({plugin.__class__.__name__}) failed: "
                f"{type(exception).__name__}: {exception}",
                extra={"run_id": run_id, "plugin_name": plugin_name}
            )
        else:
            # 其他级别：简短消息
            self.logger.error(f"Plugin '{plugin_name}' failed: {exception}")
