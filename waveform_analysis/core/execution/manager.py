# -*- coding: utf-8 -*-
"""
全局执行器管理框架 - 统一管理线程池和进程池

提供统一的接口来管理并行执行资源，支持：
- 线程池和进程池的统一管理
- 自动资源清理和重用
- 配置管理和性能优化
- 上下文管理器支持
"""
import atexit
import multiprocessing
import threading
from contextlib import contextmanager
from typing import Any, Callable, Dict, Iterator, List, Optional, Tuple, Union

from concurrent.futures import (
    Executor,
    Future,
    ProcessPoolExecutor,
    ThreadPoolExecutor,
    as_completed,
)

from waveform_analysis.core.foundation.utils import exporter

# 初始化 exporter
export, __all__ = exporter()


class ExecutorManager:
    """
    全局执行器管理器 - 单例模式
    
    统一管理所有线程池和进程池，提供资源重用和自动清理。
    
    特性:
    - 单例模式，全局唯一实例
    - 自动资源清理（程序退出时）
    - 支持配置和重用
    - 线程安全
    """
    
    _instance: Optional["ExecutorManager"] = None
    _lock = threading.RLock()  # Use RLock for reentrant locking

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    instance = super().__new__(cls)
                    instance._initialized = False
                    cls._instance = instance
        return cls._instance

    def __init__(self):
        # Thread-safe initialization check
        with self._lock:
            if self._initialized:
                return

            self._executors: Dict[str, Executor] = {}
            self._executor_configs: Dict[str, Dict[str, Any]] = {}
            self._executor_refs: Dict[str, int] = {}  # 引用计数
            self._executor_lock = threading.Lock()  # Separate lock for executor operations
            self._default_max_workers = multiprocessing.cpu_count()

            # 注册退出时的清理函数
            atexit.register(self.shutdown_all)
            self._initialized = True
    
    def get_executor(
        self,
        name: str,
        executor_type: str = "thread",
        max_workers: Optional[int] = None,
        reuse: bool = True,
        **kwargs
    ) -> Executor:
        """
        获取或创建执行器。
        
        参数:
            name: 执行器名称（用于标识和重用）
            executor_type: "thread" 或 "process"
            max_workers: 最大工作线程/进程数（None=使用默认值）
            reuse: 是否重用已存在的执行器（默认True）
            **kwargs: 传递给执行器的其他参数
        
        返回:
            Executor 实例
        """
        if max_workers is None:
            max_workers = self._default_max_workers
        
        key = f"{name}_{executor_type}_{max_workers}"

        with self._executor_lock:
            if reuse and key in self._executors:
                # 重用现有执行器
                self._executor_refs[key] += 1
                return self._executors[key]

            # 创建新执行器
            if executor_type == "process":
                executor = ProcessPoolExecutor(max_workers=max_workers, **kwargs)
            else:
                executor = ThreadPoolExecutor(max_workers=max_workers, **kwargs)

            self._executors[key] = executor
            self._executor_configs[key] = {
                "name": name,
                "type": executor_type,
                "max_workers": max_workers,
                **kwargs
            }
            self._executor_refs[key] = 1

            return executor

    def release_executor(self, name: str, executor_type: str = "thread", max_workers: Optional[int] = None):
        """
        释放执行器引用（引用计数减1）。

        当引用计数为0时，执行器会被关闭。
        """
        if max_workers is None:
            max_workers = self._default_max_workers

        key = f"{name}_{executor_type}_{max_workers}"

        with self._executor_lock:
            if key in self._executor_refs:
                self._executor_refs[key] -= 1
                if self._executor_refs[key] <= 0:
                    self._shutdown_executor(key)

    def _shutdown_executor(self, key: str, wait: bool = True):
        """关闭指定执行器"""
        if key in self._executors:
            executor = self._executors[key]
            executor.shutdown(wait=wait)
            del self._executors[key]
            del self._executor_configs[key]
            del self._executor_refs[key]

    def shutdown_all(self, wait: bool = True):
        """关闭所有执行器"""
        with self._executor_lock:
            for key in list(self._executors.keys()):
                self._shutdown_executor(key, wait=wait)

    def shutdown_executor(self, name: str, executor_type: str = "thread", max_workers: Optional[int] = None, wait: bool = True):
        """关闭指定名称的执行器"""
        if max_workers is None:
            max_workers = self._default_max_workers

        key = f"{name}_{executor_type}_{max_workers}"

        with self._executor_lock:
            if key in self._executors:
                self._shutdown_executor(key, wait=wait)

    @contextmanager
    def executor(
        self,
        name: str,
        executor_type: str = "thread",
        max_workers: Optional[int] = None,
        reuse: bool = True,
        **kwargs
    ) -> Iterator[Executor]:
        """
        上下文管理器：自动获取和释放执行器。

        示例:
            with manager.executor("my_task", "process", max_workers=4) as ex:
                futures = [ex.submit(func, arg) for arg in args]
                results = [f.result() for f in futures]
        """
        executor = self.get_executor(name, executor_type, max_workers, reuse, **kwargs)
        try:
            yield executor
        finally:
            self.release_executor(name, executor_type, max_workers)

    def list_executors(self) -> Dict[str, Dict[str, Any]]:
        """列出所有活跃的执行器"""
        with self._executor_lock:
            return {
                key: {
                    **self._executor_configs[key],
                    "ref_count": self._executor_refs[key],
                }
                for key in self._executors.keys()
            }
    
    def get_stats(self) -> Dict[str, Any]:
        """获取执行器统计信息"""
        executors = self.list_executors()
        return {
            "total_executors": len(executors),
            "thread_executors": sum(1 for e in executors.values() if e.get("type") == "thread"),
            "process_executors": sum(1 for e in executors.values() if e.get("type") == "process"),
            "total_refs": sum(e.get("ref_count", 0) for e in executors.values()),
            "default_max_workers": self._default_max_workers,
            "cpu_count": multiprocessing.cpu_count(),
        }


# 全局单例实例
_manager = ExecutorManager()


@export
def get_executor_manager() -> ExecutorManager:
    """获取全局执行器管理器实例"""
    return _manager


@export
@contextmanager
def get_executor(
    name: str,
    executor_type: str = "thread",
    max_workers: Optional[int] = None,
    reuse: bool = True,
    **kwargs
) -> Iterator[Executor]:
    """
    便捷函数：获取执行器（上下文管理器）。
    
    参数:
        name: 执行器名称
        executor_type: "thread" 或 "process"
        max_workers: 最大工作线程/进程数
        reuse: 是否重用已存在的执行器
        **kwargs: 传递给执行器的其他参数
    
    示例:
        from waveform_analysis.core.execution.manager import get_executor
        
        with get_executor("data_processing", "process", max_workers=4) as ex:
            futures = [ex.submit(process_chunk, chunk) for chunk in chunks]
            results = [f.result() for f in as_completed(futures)]
    """
    with _manager.executor(name, executor_type, max_workers, reuse, **kwargs) as executor:
        yield executor


@export
def parallel_map(
    func: Callable,
    iterable: List[Any],
    executor_type: str = "thread",
    max_workers: Optional[int] = None,
    executor_name: Optional[str] = None,
    reuse_executor: bool = False,
    **kwargs
) -> List[Any]:
    """
    并行执行函数（类似map，但并行）。
    
    参数:
        func: 要执行的函数
        iterable: 输入数据列表
        executor_type: "thread" 或 "process"
        max_workers: 最大工作线程/进程数
        executor_name: 执行器名称（用于重用）
        reuse_executor: 是否重用执行器
        **kwargs: 传递给执行器的其他参数
    
    返回:
        结果列表（保持输入顺序）
    
    示例:
        results = parallel_map(process_file, file_list, executor_type="process", max_workers=4)
    """
    if executor_name is None:
        executor_name = f"parallel_map_{id(func)}"
    
    if max_workers is None:
        max_workers = min(len(iterable), multiprocessing.cpu_count())
    
    with get_executor(executor_name, executor_type, max_workers, reuse_executor, **kwargs) as executor:
        # 提交所有任务
        futures = {executor.submit(func, item): idx for idx, item in enumerate(iterable)}
        
        # 收集结果（保持顺序）
        results = [None] * len(iterable)
        for future in as_completed(futures):
            idx = futures[future]
            try:
                results[idx] = future.result()
            except Exception as e:
                # 可以选择记录错误或重新抛出
                raise RuntimeError(f"任务 {idx} 执行失败: {e}") from e
        
        return results


@export
def parallel_apply(
    func: Callable,
    args_list: List[Tuple],
    executor_type: str = "thread",
    max_workers: Optional[int] = None,
    executor_name: Optional[str] = None,
    reuse_executor: bool = False,
    **kwargs
) -> List[Any]:
    """
    并行执行函数（支持多参数）。
    
    参数:
        func: 要执行的函数
        args_list: 参数元组列表，每个元组对应一次函数调用
        executor_type: "thread" 或 "process"
        max_workers: 最大工作线程/进程数
        executor_name: 执行器名称（用于重用）
        reuse_executor: 是否重用执行器
        **kwargs: 传递给执行器的其他参数
    
    返回:
        结果列表（保持输入顺序）
    
    示例:
        args_list = [(x, y) for x, y in zip(xs, ys)]
        results = parallel_apply(process_pair, args_list, executor_type="process", max_workers=4)
    """
    if executor_name is None:
        executor_name = f"parallel_apply_{id(func)}"
    
    if max_workers is None:
        max_workers = min(len(args_list), multiprocessing.cpu_count())
    
    with get_executor(executor_name, executor_type, max_workers, reuse_executor, **kwargs) as executor:
        # 提交所有任务
        futures = {executor.submit(func, *args): idx for idx, args in enumerate(args_list)}
        
        # 收集结果（保持顺序）
        results = [None] * len(args_list)
        for future in as_completed(futures):
            idx = futures[future]
            try:
                results[idx] = future.result()
            except Exception as e:
                raise RuntimeError(f"任务 {idx} 执行失败: {e}") from e
        
        return results


@export
def configure_default_workers(max_workers: Optional[int] = None):
    """
    配置默认的最大工作线程/进程数。
    
    参数:
        max_workers: 默认值（None=使用CPU核心数）
    """
    if max_workers is None:
        max_workers = multiprocessing.cpu_count()
    _manager._default_max_workers = max_workers


@export
def get_default_workers() -> int:
    """获取默认的最大工作线程/进程数"""
    return _manager._default_max_workers


@export
def get_stats() -> Dict[str, Any]:
    """获取执行器统计信息（便捷函数）"""
    return _manager.get_stats()

