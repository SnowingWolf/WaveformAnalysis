"""
超时管理模块 - 为plugin执行提供超时控制

防止plugin长时间挂起,支持:
- 跨平台超时控制(Unix signal + threading Timer)
- Graceful cleanup
- 自定义超时回调
- 超时事件日志记录
"""

import logging
import time
import platform
import warnings
from typing import Any, Callable, Optional, Dict
from contextlib import contextmanager

from waveform_analysis.core.utils import exporter
from waveform_analysis.core.exceptions import PluginTimeoutError

logger = logging.getLogger(__name__)
export, __all__ = exporter()


# ===========================
# Timeout Implementation
# ===========================

@export
class TimeoutManager:
    """
    超时管理器,提供跨平台的超时控制

    使用示例:
        manager = TimeoutManager()
        try:
            result = manager.run_with_timeout(func, timeout=10.0, arg1, arg2)
        except PluginTimeoutError:
            print("Function timed out!")
    """

    def __init__(self):
        self.is_unix = platform.system() in ['Linux', 'Darwin']
        self._timeout_stats: Dict[str, int] = {}

    def run_with_timeout(
        self,
        func: Callable,
        timeout: Optional[float],
        *args,
        **kwargs
    ) -> Any:
        """
        执行函数with超时控制

        Args:
            func: 要执行的函数
            timeout: 超时时间(秒),None表示无超时
            *args: 函数参数
            **kwargs: 函数关键字参数

        Returns:
            函数执行结果

        Raises:
            PluginTimeoutError: 函数执行超时
        """
        if timeout is None or timeout <= 0:
            # No timeout
            return func(*args, **kwargs)

        if self.is_unix:
            return self._run_with_signal(func, timeout, *args, **kwargs)
        else:
            return self._run_with_threading(func, timeout, *args, **kwargs)

    def _run_with_signal(
        self,
        func: Callable,
        timeout: float,
        *args,
        **kwargs
    ) -> Any:
        """Unix平台:使用signal.alarm实现超时(效率更高)"""
        import signal

        def timeout_handler(signum, frame):
            raise PluginTimeoutError(f"Function timed out after {timeout} seconds")

        # Setup signal handler
        old_handler = signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(int(timeout) + 1)  # 向上取整

        try:
            result = func(*args, **kwargs)
            signal.alarm(0)  # Cancel alarm
            return result
        except PluginTimeoutError:
            # Record timeout
            func_name = getattr(func, '__name__', 'unknown')
            self._timeout_stats[func_name] = self._timeout_stats.get(func_name, 0) + 1
            logger.warning(f"Function '{func_name}' timed out after {timeout}s")
            raise
        finally:
            signal.alarm(0)  # Ensure alarm is canceled
            signal.signal(signal.SIGALRM, old_handler)  # Restore handler

    def _run_with_threading(
        self,
        func: Callable,
        timeout: float,
        *args,
        **kwargs
    ) -> Any:
        """跨平台:使用threading实现超时(兼容Windows)"""
        import threading

        result = [None]
        exception = [None]

        def target():
            try:
                result[0] = func(*args, **kwargs)
            except Exception as e:
                exception[0] = e

        thread = threading.Thread(target=target)
        thread.daemon = True
        thread.start()
        thread.join(timeout)

        if thread.is_alive():
            # Timeout occurred
            func_name = getattr(func, '__name__', 'unknown')
            self._timeout_stats[func_name] = self._timeout_stats.get(func_name, 0) + 1
            logger.warning(f"Function '{func_name}' timed out after {timeout}s")

            # Note: We cannot forcibly stop the thread in Python
            # It will continue running in background (daemon)
            warnings.warn(
                f"Function '{func_name}' timed out but thread cannot be forcibly stopped. "
                f"It will continue running as daemon thread.",
                RuntimeWarning
            )
            raise PluginTimeoutError(f"Function timed out after {timeout} seconds")

        if exception[0] is not None:
            raise exception[0]

        return result[0]

    @contextmanager
    def timeout_context(self, timeout: Optional[float], name: str = "operation"):
        """
        Context manager for timeout control

        使用示例:
            with manager.timeout_context(10.0, "plugin_compute"):
                # ... long operation ...
        """
        if timeout is None or timeout <= 0:
            yield
            return

        start_time = time.time()

        try:
            if self.is_unix:
                import signal

                def timeout_handler(signum, frame):
                    raise PluginTimeoutError(f"{name} timed out after {timeout} seconds")

                old_handler = signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(int(timeout) + 1)

            yield

            if self.is_unix:
                import signal
                signal.alarm(0)

        except PluginTimeoutError:
            elapsed = time.time() - start_time
            self._timeout_stats[name] = self._timeout_stats.get(name, 0) + 1
            logger.warning(f"Operation '{name}' timed out after {elapsed:.2f}s (limit: {timeout}s)")
            raise
        finally:
            if self.is_unix:
                import signal
                signal.alarm(0)
                signal.signal(signal.SIGALRM, old_handler)

    def get_timeout_stats(self) -> Dict[str, int]:
        """获取超时统计信息"""
        return self._timeout_stats.copy()

    def reset_stats(self):
        """重置统计信息"""
        self._timeout_stats.clear()


# ===========================
# Global Timeout Manager
# ===========================

_timeout_manager = None

@export
def get_timeout_manager() -> TimeoutManager:
    """获取全局TimeoutManager单例"""
    global _timeout_manager
    if _timeout_manager is None:
        _timeout_manager = TimeoutManager()
    return _timeout_manager


# ===========================
# Decorator for Easy Use
# ===========================

@export
def with_timeout(timeout: Optional[float] = None):
    """
    装饰器:为函数添加超时控制

    使用示例:
        @with_timeout(timeout=10.0)
        def my_slow_function():
            time.sleep(15)  # Will timeout

        try:
            my_slow_function()
        except PluginTimeoutError:
            print("Function timed out!")
    """
    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            manager = get_timeout_manager()
            return manager.run_with_timeout(func, timeout, *args, **kwargs)
        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        return wrapper
    return decorator
