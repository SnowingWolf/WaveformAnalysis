# -*- coding: utf-8 -*-
"""
全局执行器管理框架 - 统一管理线程池和进程池

提供统一的接口来管理并行执行资源，支持：
- 线程池和进程池的统一管理
- 自动资源清理和重用
- 配置管理和性能优化
- 上下文管理器支持
- 动态负载均衡（可选）
"""

import atexit
from concurrent.futures import (
    Executor,
    ProcessPoolExecutor,
    ThreadPoolExecutor,
    as_completed,
)
from contextlib import contextmanager
from dataclasses import dataclass
import multiprocessing
import threading
import time
from typing import Any, Callable, Dict, Iterator, List, Optional, Tuple

from waveform_analysis.core.foundation.utils import exporter

# 初始化 exporter
export, __all__ = exporter()

# 线程本地存储，用于进度配置
_thread_local = threading.local()


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
        """
        初始化全局执行器管理器（单例模式）

        仅在首次创建实例时初始化内部状态。后续调用会被忽略。

        初始化内容:
        - 执行器字典和配置
        - 引用计数器
        - 线程锁（用于线程安全操作）
        - 默认 worker 数量（CPU 核心数）
        - 负载均衡器支持（可选）
        - 注册退出清理钩子

        Note:
            由于单例模式，请使用 get_instance() 获取实例，而非直接调用构造函数。
        """
        # Thread-safe initialization check
        with self._lock:
            if self._initialized:
                return

            self._executors: Dict[str, Executor] = {}
            self._executor_configs: Dict[str, Dict[str, Any]] = {}
            self._executor_refs: Dict[str, int] = {}  # 引用计数
            self._executor_lock = threading.Lock()  # Separate lock for executor operations
            self._default_max_workers = multiprocessing.cpu_count()

            # 负载均衡器支持
            self._load_balancer: Optional[Any] = None  # DynamicLoadBalancer实例
            self._load_balancing_enabled = False

            # 注册退出时的清理函数
            atexit.register(self.shutdown_all)
            self._initialized = True

    def get_executor(
        self, name: str, executor_type: str = "thread", max_workers: Optional[int] = None, reuse: bool = True, **kwargs
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
            self._executor_configs[key] = {"name": name, "type": executor_type, "max_workers": max_workers, **kwargs}
            self._executor_refs[key] = 1

            return executor

    def release_executor(
        self,
        name: str,
        executor_type: str = "thread",
        max_workers: Optional[int] = None,
        wait: bool = True,
    ):
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
                    self._shutdown_executor(key, wait=wait)

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

    def shutdown_executor(
        self, name: str, executor_type: str = "thread", max_workers: Optional[int] = None, wait: bool = True
    ):
        """关闭指定名称的执行器"""
        if max_workers is None:
            max_workers = self._default_max_workers

        key = f"{name}_{executor_type}_{max_workers}"

        with self._executor_lock:
            if key in self._executors:
                self._shutdown_executor(key, wait=wait)

    @contextmanager
    def executor(
        self, name: str, executor_type: str = "thread", max_workers: Optional[int] = None, reuse: bool = True, **kwargs
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

    def enable_load_balancing(
        self,
        min_workers: int = 1,
        max_workers: Optional[int] = None,
        cpu_threshold: float = 0.8,
        memory_threshold: float = 0.85,
        check_interval: float = 5.0,
    ):
        """
        启用动态负载均衡

        Args:
            min_workers: 最小worker数量
            max_workers: 最大worker数量（None=使用默认值）
            cpu_threshold: CPU使用率阈值（0-1）
            memory_threshold: 内存使用率阈值（0-1）
            check_interval: 检查间隔（秒）
        """
        from waveform_analysis.core.load_balancer import DynamicLoadBalancer

        self._load_balancer = DynamicLoadBalancer(
            min_workers=min_workers,
            max_workers=max_workers or self._default_max_workers,
            cpu_threshold=cpu_threshold,
            memory_threshold=memory_threshold,
            check_interval=check_interval,
        )
        self._load_balancing_enabled = True

    def disable_load_balancing(self):
        """禁用动态负载均衡"""
        self._load_balancing_enabled = False
        self._load_balancer = None

    def get_load_balancer_stats(self) -> Optional[Dict]:
        """
        获取负载均衡统计信息

        Returns:
            统计信息字典，如果未启用则返回None
        """
        if self._load_balancer:
            return self._load_balancer.get_statistics()
        return None


# ===========================
# 进度配置系统
# ===========================


@export
@dataclass
class ParallelProgressConfig:
    """
    并行执行进度条配置

    可以通过装饰器或上下文管理器设置，让 parallel_map/parallel_apply 自动显示进度条。

    使用方式:
        # 方式1：装饰函数
        @parallel_progress(desc="Processing files", unit="file")
        def process_file(file_path):
            return load_file(file_path)

        results = parallel_map(process_file, file_list)  # 自动显示进度条

        # 方式2：使用上下文管理器
        with ParallelProgressConfig(desc="Batch processing", unit="batch"):
            results = parallel_map(process_file, file_list)  # 使用上下文配置
    """

    enabled: bool = True
    desc: Optional[str] = None
    unit: str = "it"

    @classmethod
    def get_current(cls) -> Optional["ParallelProgressConfig"]:
        """获取当前线程的配置"""
        return getattr(_thread_local, "parallel_progress_config", None)

    def __enter__(self):
        """上下文管理器入口"""
        _thread_local.parallel_progress_config = self
        return self

    def __exit__(self, *args):
        """上下文管理器退出"""
        if hasattr(_thread_local, "parallel_progress_config"):
            delattr(_thread_local, "parallel_progress_config")


@export
def parallel_progress(desc: Optional[str] = None, unit: str = "it", enabled: bool = True):
    """
    装饰器：为函数配置并行执行的进度条

    使用方式:
        @parallel_progress(desc="Processing files", unit="file")
        def process_file(file_path):
            return load_file(file_path)

        # 调用时自动使用进度条
        results = parallel_map(process_file, file_list)

    参数:
        desc: 进度条描述（默认使用函数名）
        unit: 进度单位（默认"it"）
        enabled: 是否启用进度条（默认True）

    返回:
        装饰后的函数
    """

    def decorator(func: Callable) -> Callable:
        # 将配置存储在函数属性中
        func._parallel_progress = ParallelProgressConfig(
            enabled=enabled, desc=desc or f"Processing {func.__name__}", unit=unit
        )
        return func

    return decorator


# 全局单例实例
_manager = ExecutorManager()


@export
def get_executor_manager() -> ExecutorManager:
    """获取全局执行器管理器实例"""
    return _manager


@export
@contextmanager
def get_executor(
    name: str, executor_type: str = "thread", max_workers: Optional[int] = None, reuse: bool = True, **kwargs
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
            futures = [ex.submit(handle_chunk, chunk) for chunk in chunks]
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
    progress_callback: Optional[Callable[[int], None]] = None,
    use_load_balancer: bool = True,
    estimated_task_size: Optional[int] = None,
    **kwargs,
) -> List[Any]:
    """
    并行执行函数（类似map，但并行）。

    自动检测进度配置（如果函数被 @parallel_progress 装饰或使用 ParallelProgressConfig 上下文）。

    参数:
        func: 要执行的函数
        iterable: 输入数据列表
        executor_type: "thread" 或 "process"
        max_workers: 最大工作线程/进程数
        executor_name: 执行器名称（用于重用）
        reuse_executor: 是否重用执行器
        progress_callback: 进度回调函数，每完成一个任务时调用
                          接收参数：当前完成的任务索引
                          优先级：progress_callback > 函数配置 > 线程配置
        use_load_balancer: 是否使用负载均衡器（如果已启用）
        estimated_task_size: 估计的任务大小（字节），用于负载均衡
        **kwargs: 传递给执行器的其他参数

    返回:
        结果列表（保持输入顺序）

    示例:
        # 基本用法
        results = parallel_map(process_file, file_list, executor_type="process", max_workers=4)

        # 使用装饰器配置进度条
        @parallel_progress(desc="Processing files", unit="file")
        def process_file(file_path):
            return load_file(file_path)

        results = parallel_map(process_file, file_list)  # 自动显示进度条

        # 使用上下文管理器配置进度条
        with ParallelProgressConfig(desc="Batch processing", unit="batch"):
            results = parallel_map(process_file, file_list)

        # 使用自定义进度回调（优先级最高）
        def update_progress(idx):
            print(f"Completed {idx}")
        results = parallel_map(process_file, file_list, progress_callback=update_progress)

        # 使用负载均衡
        results = parallel_map(
            process_file, file_list,
            use_load_balancer=True,
            estimated_task_size=10*1024*1024  # 10MB per task
        )
    """
    # 自动检测进度配置（优先级：progress_callback > 函数配置 > 线程配置）
    progress_config = None
    tracker = None
    bar_name = None

    if progress_callback is None:
        # 检查函数配置
        progress_config = getattr(func, "_parallel_progress", None)

        # 如果没有，检查线程配置
        if progress_config is None:
            progress_config = ParallelProgressConfig.get_current()

        # 如果配置存在且启用，创建进度条
        if progress_config and progress_config.enabled:
            from waveform_analysis.core.foundation.progress import (
                format_throughput,
                get_global_tracker,
            )

            tracker = get_global_tracker()
            bar_name = f"parallel_map_{id(iterable)}"

            tracker.create_bar(bar_name, total=len(iterable), desc=progress_config.desc, unit=progress_config.unit)

            def update_progress(idx):
                tracker.update(bar_name, n=1)
                if (idx + 1) % 10 == 0:
                    throughput = tracker.calculate_throughput(bar_name)
                    if throughput:
                        tracker.set_postfix(bar_name, speed=format_throughput(throughput, progress_config.unit))

            progress_callback = update_progress

    if executor_name is None:
        executor_name = f"parallel_map_{id(func)}"

    # 动态调整 max_workers (如果启用负载均衡)
    if max_workers is None or (use_load_balancer and _manager._load_balancing_enabled):
        if _manager._load_balancing_enabled and _manager._load_balancer and use_load_balancer:
            optimal_workers = _manager._load_balancer.get_optimal_workers(
                n_tasks=len(iterable), estimated_task_size=estimated_task_size
            )
            # 如果用户指定了 max_workers,取两者较小值
            if max_workers is not None:
                max_workers = min(max_workers, optimal_workers)
            else:
                max_workers = optimal_workers
        elif max_workers is None:
            max_workers = min(len(iterable), multiprocessing.cpu_count())

    # 记录开始时间(用于统计)
    start_time = time.time() if (_manager._load_balancing_enabled and use_load_balancer) else None
    successful_tasks = 0

    try:
        with get_executor(executor_name, executor_type, max_workers, reuse_executor, **kwargs) as executor:
            # 提交所有任务
            futures = {executor.submit(func, item): idx for idx, item in enumerate(iterable)}

            # 收集结果（保持顺序）
            results = [None] * len(iterable)
            for future in as_completed(futures):
                idx = futures[future]
                try:
                    results[idx] = future.result()
                    successful_tasks += 1

                    # 调用进度回调
                    if progress_callback:
                        progress_callback(idx)

                except Exception as e:
                    raise RuntimeError(f"任务 {idx} 执行失败: {e}") from e

            # 记录任务完成统计
            if _manager._load_balancing_enabled and _manager._load_balancer and start_time:
                duration = time.time() - start_time
                _manager._load_balancer.record_task_completion(
                    duration=duration, success=(successful_tasks == len(iterable))
                )

            return results
    finally:
        # 清理进度条
        if tracker and bar_name:
            tracker.close(bar_name)


@export
def parallel_apply(
    func: Callable,
    args_list: List[Tuple],
    executor_type: str = "thread",
    max_workers: Optional[int] = None,
    executor_name: Optional[str] = None,
    reuse_executor: bool = False,
    progress_callback: Optional[Callable[[int], None]] = None,
    use_load_balancer: bool = True,
    estimated_task_size: Optional[int] = None,
    **kwargs,
) -> List[Any]:
    """
    并行执行函数（支持多参数）。

    自动检测进度配置（如果函数被 @parallel_progress 装饰或使用 ParallelProgressConfig 上下文）。

    参数:
        func: 要执行的函数
        args_list: 参数元组列表，每个元组对应一次函数调用
        executor_type: "thread" 或 "process"
        max_workers: 最大工作线程/进程数
        executor_name: 执行器名称（用于重用）
        reuse_executor: 是否重用执行器
        progress_callback: 进度回调函数，每完成一个任务时调用
                          接收参数：当前完成的任务索引
                          优先级：progress_callback > 函数配置 > 线程配置
        use_load_balancer: 是否使用负载均衡器（如果已启用）
        estimated_task_size: 估计的任务大小（字节），用于负载均衡
        **kwargs: 传递给执行器的其他参数

    返回:
        结果列表（保持输入顺序）

    示例:
        # 基本用法
        args_list = [(x, y) for x, y in zip(xs, ys)]
        results = parallel_apply(process_pair, args_list, executor_type="process", max_workers=4)

        # 使用装饰器配置进度条
        @parallel_progress(desc="Processing pairs", unit="pair")
        def process_pair(x, y):
            return x + y

        results = parallel_apply(process_pair, args_list)  # 自动显示进度条

        # 使用上下文管理器配置进度条
        with ParallelProgressConfig(desc="Batch processing", unit="batch"):
            results = parallel_apply(process_pair, args_list)

        # 使用负载均衡
        results = parallel_apply(
            process_pair, args_list,
            use_load_balancer=True,
            estimated_task_size=5*1024*1024  # 5MB per task
        )
    """
    # 自动检测进度配置（优先级：progress_callback > 函数配置 > 线程配置）
    progress_config = None
    tracker = None
    bar_name = None

    if progress_callback is None:
        # 检查函数配置
        progress_config = getattr(func, "_parallel_progress", None)

        # 如果没有，检查线程配置
        if progress_config is None:
            progress_config = ParallelProgressConfig.get_current()

        # 如果配置存在且启用，创建进度条
        if progress_config and progress_config.enabled:
            from waveform_analysis.core.foundation.progress import (
                format_throughput,
                get_global_tracker,
            )

            tracker = get_global_tracker()
            bar_name = f"parallel_apply_{id(args_list)}"

            tracker.create_bar(bar_name, total=len(args_list), desc=progress_config.desc, unit=progress_config.unit)

            def update_progress(idx):
                tracker.update(bar_name, n=1)
                if (idx + 1) % 10 == 0:
                    throughput = tracker.calculate_throughput(bar_name)
                    if throughput:
                        tracker.set_postfix(bar_name, speed=format_throughput(throughput, progress_config.unit))

            progress_callback = update_progress

    if executor_name is None:
        executor_name = f"parallel_apply_{id(func)}"

    # 动态调整 max_workers (如果启用负载均衡)
    if max_workers is None or (use_load_balancer and _manager._load_balancing_enabled):
        if _manager._load_balancing_enabled and _manager._load_balancer and use_load_balancer:
            optimal_workers = _manager._load_balancer.get_optimal_workers(
                n_tasks=len(args_list), estimated_task_size=estimated_task_size
            )
            # 如果用户指定了 max_workers,取两者较小值
            if max_workers is not None:
                max_workers = min(max_workers, optimal_workers)
            else:
                max_workers = optimal_workers
        elif max_workers is None:
            max_workers = min(len(args_list), multiprocessing.cpu_count())

    # 记录开始时间(用于统计)
    start_time = time.time() if (_manager._load_balancing_enabled and use_load_balancer) else None
    successful_tasks = 0

    try:
        with get_executor(executor_name, executor_type, max_workers, reuse_executor, **kwargs) as executor:
            # 提交所有任务
            futures = {executor.submit(func, *args): idx for idx, args in enumerate(args_list)}

            # 收集结果（保持顺序）
            results = [None] * len(args_list)
            for future in as_completed(futures):
                idx = futures[future]
                try:
                    results[idx] = future.result()
                    successful_tasks += 1

                    # 调用进度回调
                    if progress_callback:
                        progress_callback(idx)

                except Exception as e:
                    raise RuntimeError(f"任务 {idx} 执行失败: {e}") from e

            # 记录任务完成统计
            if _manager._load_balancing_enabled and _manager._load_balancer and start_time:
                duration = time.time() - start_time
                _manager._load_balancer.record_task_completion(
                    duration=duration, success=(successful_tasks == len(args_list))
                )

            return results
    finally:
        # 清理进度条
        if tracker and bar_name:
            tracker.close(bar_name)


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


@export
def enable_global_load_balancing(
    min_workers: int = 1,
    max_workers: Optional[int] = None,
    cpu_threshold: float = 0.8,
    memory_threshold: float = 0.85,
    check_interval: float = 5.0,
):
    """
    启用全局负载均衡（便捷函数）

    Args:
        min_workers: 最小worker数量
        max_workers: 最大worker数量（None=使用默认值）
        cpu_threshold: CPU使用率阈值（0-1）
        memory_threshold: 内存使用率阈值（0-1）
        check_interval: 检查间隔（秒）
    """
    _manager.enable_load_balancing(
        min_workers=min_workers,
        max_workers=max_workers,
        cpu_threshold=cpu_threshold,
        memory_threshold=memory_threshold,
        check_interval=check_interval,
    )


@export
def disable_global_load_balancing():
    """禁用全局负载均衡（便捷函数）"""
    _manager.disable_load_balancing()


@export
def get_load_balancer_stats() -> Optional[Dict]:
    """
    获取负载均衡统计信息（便捷函数）

    Returns:
        统计信息字典，如果未启用则返回None
    """
    return _manager.get_load_balancer_stats()
