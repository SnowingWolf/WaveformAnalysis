"""
任务取消模块 (Phase 3 Enhancement)

提供任务取消和信号处理功能:
- CancellationToken 取消令牌
- CancellationManager 全局取消管理
- 信号处理（Ctrl+C）
- 资源清理回调
"""

from collections.abc import Callable
import logging
import signal
import threading
from typing import Optional

from waveform_analysis.core.foundation.utils import exporter

logger = logging.getLogger(__name__)
export, __all__ = exporter()


# ===========================
# 任务取消异常
# ===========================


@export
class TaskCancelledException(Exception):
    """
    任务取消异常

    当任务被取消时抛出此异常
    """

    pass


# ===========================
# 取消令牌
# ===========================


@export
class CancellationToken:
    """
    任务取消令牌

    特性:
    - 线程安全的取消状态检查
    - 支持取消回调
    - 与signal.SIGINT集成

    使用示例:
        token = CancellationToken()

        # 在任务循环中检查
        for item in items:
            if token.is_cancelled():
                break
            process(item)

        # 或抛出异常
        token.throw_if_cancelled()

        # 注册清理回调
        token.register_callback(lambda: cleanup_resources())
    """

    def __init__(self):
        """初始化取消令牌"""
        self._cancelled = threading.Event()
        self._callbacks: list[Callable] = []
        self._lock = threading.Lock()

    def cancel(self):
        """
        标记为已取消，触发所有回调

        线程安全，可以从任何线程调用
        """
        if not self._cancelled.is_set():
            self._cancelled.set()

            # 触发所有回调
            with self._lock:
                for callback in self._callbacks:
                    try:
                        callback()
                    except Exception as e:
                        logger.error(f"Error in cancellation callback: {e}")

    def is_cancelled(self) -> bool:
        """
        检查是否已取消

        Returns:
            True if cancelled, False otherwise
        """
        return self._cancelled.is_set()

    def throw_if_cancelled(self):
        """
        如果已取消，抛出TaskCancelledException异常

        Raises:
            TaskCancelledException: 如果任务已被取消
        """
        if self.is_cancelled():
            raise TaskCancelledException("Task was cancelled")

    def register_callback(self, callback: Callable):
        """
        注册取消回调（用于资源清理）

        回调将在调用cancel()时执行

        Args:
            callback: 无参数的可调用对象
        """
        with self._lock:
            self._callbacks.append(callback)

    def unregister_callback(self, callback: Callable):
        """
        注销取消回调

        Args:
            callback: 要移除的回调对象
        """
        with self._lock:
            if callback in self._callbacks:
                self._callbacks.remove(callback)

    def reset(self):
        """
        重置取消状态（谨慎使用）

        清除取消标志，允许令牌重新使用
        """
        self._cancelled.clear()


# ===========================
# 全局取消管理器
# ===========================


@export
class CancellationManager:
    """
    全局取消管理器

    处理Ctrl+C信号，管理所有活跃的CancellationToken

    使用示例:
        manager = get_cancellation_manager()
        manager.enable()

        token = CancellationToken()
        manager.register_token(token)

        # 按Ctrl+C会自动取消所有token

        manager.unregister_token(token)
        manager.disable()
    """

    _instance: Optional["CancellationManager"] = None
    _lock = threading.Lock()

    def __init__(self):
        """初始化取消管理器（不要直接调用，使用get_cancellation_manager）"""
        self._tokens: set[CancellationToken] = set()
        self._tokens_lock = threading.Lock()
        self._original_sigint = None
        self._enabled = False
        self.logger = logging.getLogger(self.__class__.__name__)

    def enable(self):
        """
        启用信号处理

        安装SIGINT处理器以捕获Ctrl+C
        """
        if not self._enabled:
            try:
                self._original_sigint = signal.signal(signal.SIGINT, self._handle_sigint)
                self._enabled = True
                self.logger.debug("Cancellation signal handler enabled")
            except ValueError as e:
                # 在某些环境中（如线程中）无法设置信号处理器
                self.logger.warning(f"Cannot enable signal handler: {e}")

    def disable(self):
        """
        禁用信号处理，恢复原始处理器
        """
        if self._enabled and self._original_sigint is not None:
            try:
                signal.signal(signal.SIGINT, self._original_sigint)
                self._enabled = False
                self.logger.debug("Cancellation signal handler disabled")
            except ValueError as e:
                self.logger.warning(f"Cannot disable signal handler: {e}")

    def _handle_sigint(self, signum, frame):
        """
        SIGINT处理函数

        Args:
            signum: 信号编号
            frame: 当前堆栈帧
        """
        print("\n🛑 Received cancellation signal (Ctrl+C). Cleaning up...")
        self.cancel_all()

        # 如果有原始处理器，也调用它
        if self._original_sigint and callable(self._original_sigint):
            self._original_sigint(signum, frame)

    def register_token(self, token: CancellationToken):
        """
        注册token

        Args:
            token: 要注册的CancellationToken
        """
        with self._tokens_lock:
            self._tokens.add(token)
            self.logger.debug(f"Registered cancellation token (total: {len(self._tokens)})")

    def unregister_token(self, token: CancellationToken):
        """
        注销token

        Args:
            token: 要注销的CancellationToken
        """
        with self._tokens_lock:
            self._tokens.discard(token)
            self.logger.debug(f"Unregistered cancellation token (remaining: {len(self._tokens)})")

    def cancel_all(self):
        """
        取消所有注册的token
        """
        with self._tokens_lock:
            token_count = len(self._tokens)
            for token in list(self._tokens):
                token.cancel()

            self.logger.info(f"Cancelled {token_count} active tasks")

    def clear_all_tokens(self):
        """
        清除所有token（不触发取消）

        用于清理
        """
        with self._tokens_lock:
            self._tokens.clear()

    def __enter__(self):
        """上下文管理器入口：启用信号处理"""
        self.enable()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器退出：禁用信号处理"""
        self.disable()
        return False


@export
def get_cancellation_manager() -> CancellationManager:
    """
    获取全局取消管理器（单例）

    Returns:
        CancellationManager实例

    Examples:
        >>> manager = get_cancellation_manager()
        >>> manager.enable()
        >>> token = CancellationToken()
        >>> manager.register_token(token)
        >>> # ... do work ...
        >>> manager.unregister_token(token)
        >>> manager.disable()
    """
    if CancellationManager._instance is None:
        with CancellationManager._lock:
            if CancellationManager._instance is None:
                CancellationManager._instance = CancellationManager()

    return CancellationManager._instance
