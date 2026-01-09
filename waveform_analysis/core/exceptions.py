"""
Exceptions 模块 - 异常处理基础类和工具。

提供错误分类、异常类和上下文信息收集功能，用于统一管理插件系统的异常处理。
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional


class ErrorSeverity(Enum):
    """错误严重程度枚举"""
    FATAL = "fatal"  # 致命错误，必须停止
    RECOVERABLE = "recoverable"  # 可恢复错误，可以重试或降级
    WARNING = "warning"  # 警告，仅记录


@dataclass
class ErrorContext:
    """错误上下文信息"""
    run_id: str
    plugin_name: str
    plugin_class: str
    config: Dict[str, Any]
    timestamp: str
    dependencies_info: Dict[str, Any]
    memory_mb: Optional[float] = None


class PluginError(Exception):
    """插件专用异常类

    包含错误严重程度、可恢复性、重试次数和上下文信息。
    """

    def __init__(
        self,
        message: str,
        severity: ErrorSeverity = ErrorSeverity.FATAL,
        recoverable: bool = False,
        retry_count: int = 0,
        context: Optional[ErrorContext] = None,
    ):
        """
        初始化插件异常

        Args:
            message: 错误消息
            severity: 错误严重程度
            recoverable: 是否可恢复
            retry_count: 重试次数
            context: 错误上下文信息
        """
        self.severity = severity
        self.recoverable = recoverable
        self.retry_count = retry_count
        self.context = context
        super().__init__(message)


class PluginTimeoutError(PluginError):
    """插件超时异常

    当插件执行超过指定timeout时抛出
    """

    def __init__(
        self,
        message: str,
        context: Optional[ErrorContext] = None,
    ):
        super().__init__(
            message,
            severity=ErrorSeverity.RECOVERABLE,
            recoverable=True,
            context=context
        )

