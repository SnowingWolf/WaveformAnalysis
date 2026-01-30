"""
进度追踪模块 (Phase 3 Enhancement)

提供统一的进度追踪系统:
- tqdm集成的进度条
- 嵌套进度显示
- ETA和吞吐量计算
- 线程安全
- 装饰器支持
"""

import functools
import inspect
import logging
import threading
import time
from typing import Any, Callable, Dict, Iterable, Iterator, Optional, TypeVar

from tqdm import tqdm

from waveform_analysis.core.foundation.utils import exporter

logger = logging.getLogger(__name__)
export, __all__ = exporter()

# 类型变量
T = TypeVar("T")
F = TypeVar("F", bound=Callable[..., Any])


# ===========================
# 进度追踪系统
# ===========================


@export
class ProgressTracker:
    """
    统一的进度追踪系统

    特性:
    - 支持嵌套进度条（使用tqdm的position参数）
    - 自动计算ETA和吞吐量
    - 支持多任务并行显示
    - 线程安全

    使用示例:
        tracker = ProgressTracker()

        # 创建主进度条
        tracker.create_bar(
            "batch_processing",
            total=100,
            desc="Processing runs",
            unit="run"
        )

        # 更新进度
        tracker.update("batch_processing", n=1)
        tracker.set_postfix("batch_processing", throughput="0.5 runs/s")

        # 关闭进度条
        tracker.close("batch_processing")
    """

    def __init__(self, disable: bool = False):
        """
        初始化进度追踪器

        Args:
            disable: 是否禁用进度显示（用于非交互环境）
        """
        self._bars: Dict[str, tqdm] = {}
        self._bar_info: Dict[str, Dict[str, Any]] = {}  # 存储进度条元信息
        self._lock = threading.RLock()
        self.disable = disable
        self._position_counter = 0  # 用于分配position

    def create_bar(
        self,
        name: str,
        total: int,
        desc: str = "",
        unit: str = "it",
        nested: bool = False,
        parent: Optional[str] = None,
        **kwargs,
    ) -> str:
        """
        创建进度条

        Args:
            name: 进度条唯一标识
            total: 总任务数
            desc: 描述文本
            unit: 单位（默认"it"）
            nested: 是否嵌套显示
            parent: 父进度条名称（用于嵌套层级关系）
            **kwargs: 传递给tqdm的其他参数

        Returns:
            进度条ID（即name）
        """
        with self._lock:
            if name in self._bars:
                logger.warning(f"Progress bar '{name}' already exists. Recreating...")
                self.close(name)

            # 计算position（用于嵌套显示）
            position = 0
            if nested and parent and parent in self._bar_info:
                parent_pos = self._bar_info[parent].get("position", 0)
                parent_nested_count = self._bar_info[parent].get("nested_count", 0)
                position = parent_pos + parent_nested_count + 1
                self._bar_info[parent]["nested_count"] = parent_nested_count + 1
            elif nested:
                position = self._position_counter
                self._position_counter += 1
            else:
                position = self._position_counter
                self._position_counter += 1

            # 创建tqdm进度条
            bar_disable = kwargs.pop("disable", self.disable)
            bar = tqdm(
                total=total,
                desc=desc,
                unit=unit,
                position=position,
                leave=True,
                disable=bar_disable,
                **kwargs,
            )

            self._bars[name] = bar
            self._bar_info[name] = {
                "parent": parent,
                "nested": nested,
                "position": position,
                "nested_count": 0,  # 子进度条数量
                "start_time": time.time(),
            }

            return name

    def update(self, name: str, n: int = 1, **kwargs):
        """
        更新进度

        Args:
            name: 进度条名称
            n: 增加的进度量
            **kwargs: 传递给tqdm.update的其他参数
        """
        with self._lock:
            if name not in self._bars:
                logger.warning(f"Progress bar '{name}' does not exist")
                return

            bar = self._bars[name]
            bar.update(n)

            # 如果进度条被禁用，tqdm.update 不会更新 n 值
            # 我们手动更新以便测试和跟踪
            if self.disable:
                bar.n += n

    def set_postfix(self, name: str, **kwargs):
        """
        设置后缀信息（如ETA、速度）

        Args:
            name: 进度条名称
            **kwargs: 后缀键值对（例如 throughput="0.5 runs/s"）
        """
        with self._lock:
            if name not in self._bars:
                logger.warning(f"Progress bar '{name}' does not exist")
                return

            bar = self._bars[name]
            bar.set_postfix(**kwargs)

    def set_description(self, name: str, desc: str):
        """
        更新描述文本

        Args:
            name: 进度条名称
            desc: 新的描述文本
        """
        with self._lock:
            if name not in self._bars:
                logger.warning(f"Progress bar '{name}' does not exist")
                return

            bar = self._bars[name]
            bar.set_description(desc)

    def close(self, name: str):
        """
        关闭进度条

        Args:
            name: 进度条名称
        """
        with self._lock:
            if name not in self._bars:
                return

            bar = self._bars[name]
            bar.close()

            del self._bars[name]
            del self._bar_info[name]

    def close_all(self):
        """关闭所有进度条"""
        with self._lock:
            for name in list(self._bars.keys()):
                self.close(name)

            # 重置position计数器
            self._position_counter = 0

    def get_elapsed_time(self, name: str) -> Optional[float]:
        """
        获取进度条已经运行的时间

        Args:
            name: 进度条名称

        Returns:
            已运行时间（秒），如果进度条不存在返回None
        """
        with self._lock:
            if name not in self._bar_info:
                return None

            start_time = self._bar_info[name]["start_time"]
            return time.time() - start_time

    def calculate_eta(self, name: str) -> Optional[float]:
        """
        计算预计剩余时间（ETA）

        Args:
            name: 进度条名称

        Returns:
            预计剩余时间（秒），如果无法计算返回None
        """
        with self._lock:
            if name not in self._bars:
                return None

            bar = self._bars[name]
            if bar.n == 0 or bar.total is None:
                return None

            elapsed = self.get_elapsed_time(name)
            if elapsed is None or elapsed == 0:
                return None

            # 简单的线性估计
            rate = bar.n / elapsed
            remaining = bar.total - bar.n

            if rate == 0:
                return None

            return remaining / rate

    def calculate_throughput(self, name: str) -> Optional[float]:
        """
        计算吞吐量

        Args:
            name: 进度条名称

        Returns:
            吞吐量（items/s），如果无法计算返回None
        """
        with self._lock:
            if name not in self._bars:
                return None

            bar = self._bars[name]
            elapsed = self.get_elapsed_time(name)

            if elapsed is None or elapsed == 0 or bar.n == 0:
                return None

            return bar.n / elapsed

    def __enter__(self):
        """上下文管理器入口"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器退出：自动关闭所有进度条"""
        self.close_all()
        return False


@export
def format_time(seconds: float) -> str:
    """
    格式化时间显示

    Args:
        seconds: 秒数

    Returns:
        格式化的时间字符串

    Examples:
        >>> format_time(65.5)
        '01:05'
        >>> format_time(3665.2)
        '01:01:05'
    """
    if seconds < 60:
        return f"{int(seconds):02d}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes:02d}:{secs:02d}"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"


@export
def format_throughput(throughput: float, unit: str = "it") -> str:
    """
    格式化吞吐量显示

    Args:
        throughput: 吞吐量（items/s）
        unit: 单位

    Returns:
        格式化的吞吐量字符串

    Examples:
        >>> format_throughput(0.5, "runs")
        '0.50 runs/s'
        >>> format_throughput(123.456, "items")
        '123.5 items/s'
    """
    if throughput < 1:
        return f"{throughput:.2f} {unit}/s"
    elif throughput < 10:
        return f"{throughput:.1f} {unit}/s"
    else:
        return f"{int(throughput)} {unit}/s"


# ===========================
# 全局进度追踪器
# ===========================

# 全局单例进度追踪器（线程本地）
_local = threading.local()


def _get_global_tracker() -> ProgressTracker:
    """获取全局进度追踪器（线程安全）"""
    if not hasattr(_local, "tracker"):
        _local.tracker = ProgressTracker()
    return _local.tracker


@export
def get_global_tracker() -> ProgressTracker:
    """
    获取全局进度追踪器实例

    每个线程有独立的追踪器实例，避免多线程冲突。

    Returns:
        ProgressTracker 实例

    Example:
        >>> tracker = get_global_tracker()
        >>> tracker.create_bar("task1", total=100, desc="Processing")
    """
    return _get_global_tracker()


@export
def reset_global_tracker():
    """
    重置全局进度追踪器

    关闭所有进度条并创建新的追踪器实例。
    通常用于测试或需要清理状态的场景。
    """
    if hasattr(_local, "tracker"):
        _local.tracker.close_all()
        del _local.tracker


# ===========================
# 进度追踪装饰器
# ===========================


@export
def with_progress(
    total: Optional[int] = None,
    desc: Optional[str] = None,
    unit: str = "it",
    disable: bool = False,
    tracker: Optional[ProgressTracker] = None,
    bar_name: Optional[str] = None,
    show_result: bool = False,
    **tqdm_kwargs,
) -> Callable[[F], F]:
    """
    统一的进度追踪装饰器

    自动为函数添加进度追踪功能。支持：
    - 普通函数：显示执行状态
    - 返回可迭代对象的函数：自动包装为进度迭代器
    - 生成器函数：逐步显示生成进度

    Args:
        total: 总任务数（如果函数返回可迭代对象，可自动推断）
        desc: 进度条描述（默认使用函数名）
        unit: 进度单位（默认"it"）
        disable: 是否禁用进度条
        tracker: 使用的进度追踪器（默认使用全局追踪器）
        bar_name: 进度条名称（默认使用函数名）
        show_result: 是否在完成后显示结果统计
        **tqdm_kwargs: 传递给 tqdm 的其他参数

    Returns:
        装饰后的函数

    Examples:
        >>> @with_progress(total=100, desc="Processing items")
        ... def process_items():
        ...     for i in range(100):
        ...         yield i
        ...
        >>> list(process_items())  # 自动显示进度

        >>> @with_progress(desc="Loading data")
        ... def load_data(files):
        ...     return [load_file(f) for f in files]
        ...
        >>> load_data(['a.csv', 'b.csv', 'c.csv'])  # 显示加载进度
    """

    def decorator(func: F) -> F:
        # 获取函数签名信息
        func_name = func.__name__
        is_generator = inspect.isgeneratorfunction(func)

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # 确定使用的追踪器
            _tracker = tracker if tracker is not None else get_global_tracker()

            # 确定进度条名称和描述
            _bar_name = bar_name or f"{func_name}_{id(wrapper)}"
            _desc = desc or f"Executing {func_name}"

            # 如果是生成器函数，包装生成器
            if is_generator:
                return _wrap_generator(
                    func(*args, **kwargs),
                    _tracker,
                    _bar_name,
                    _desc,
                    unit,
                    total,
                    disable,
                    show_result,
                    **tqdm_kwargs,
                )

            # 普通函数：执行并可能包装返回值
            start_time = time.time()
            result = func(*args, **kwargs)
            elapsed = time.time() - start_time

            # 如果返回可迭代对象（非字符串），包装为进度迭代器
            if hasattr(result, "__iter__") and not isinstance(result, (str, bytes)):
                _total = total
                if _total is None and hasattr(result, "__len__"):
                    try:
                        _total = len(result)
                    except (TypeError, AttributeError):
                        pass

                return progress_iter(
                    result,
                    total=_total,
                    desc=_desc,
                    unit=unit,
                    disable=disable,
                    tracker=_tracker,
                    bar_name=_bar_name,
                    **tqdm_kwargs,
                )

            # 普通返回值：可选显示执行时间
            if show_result and not disable:
                logger.info(f"{func_name} completed in {format_time(elapsed)}")

            return result

        return wrapper

    return decorator


def _wrap_generator(
    gen: Iterator[T],
    tracker: ProgressTracker,
    bar_name: str,
    desc: str,
    unit: str,
    total: Optional[int],
    disable: bool,
    show_result: bool,
    **tqdm_kwargs,
) -> Iterator[T]:
    """
    包装生成器，添加进度追踪

    Args:
        gen: 原始生成器
        tracker: 进度追踪器
        bar_name: 进度条名称
        desc: 描述
        unit: 单位
        total: 总数
        disable: 是否禁用
        show_result: 是否显示结果
        **tqdm_kwargs: tqdm 参数

    Yields:
        生成器的元素
    """
    # 创建进度条
    if not disable:
        tracker.create_bar(bar_name, total=total or 0, desc=desc, unit=unit, **tqdm_kwargs)

    count = 0
    start_time = time.time()

    try:
        for item in gen:
            yield item
            count += 1

            if not disable:
                tracker.update(bar_name, n=1)

                # 更新吞吐量
                if count % 10 == 0:  # 每10个更新一次，减少开销
                    throughput = tracker.calculate_throughput(bar_name)
                    if throughput is not None:
                        tracker.set_postfix(bar_name, speed=format_throughput(throughput, unit))

    finally:
        # 关闭进度条
        if not disable:
            tracker.close(bar_name)

            # 可选：显示统计信息
            if show_result:
                elapsed = time.time() - start_time
                avg_speed = count / elapsed if elapsed > 0 else 0
                logger.info(
                    f"Generator completed: {count} {unit}s in {format_time(elapsed)} "
                    f"({format_throughput(avg_speed, unit)})"
                )


@export
def progress_iter(
    iterable: Iterable[T],
    total: Optional[int] = None,
    desc: str = "Processing",
    unit: str = "it",
    disable: bool = False,
    tracker: Optional[ProgressTracker] = None,
    bar_name: Optional[str] = None,
    **tqdm_kwargs,
) -> Iterator[T]:
    """
    为可迭代对象添加进度条

    独立函数版本，不需要装饰器。

    Args:
        iterable: 可迭代对象
        total: 总数（默认自动推断）
        desc: 描述
        unit: 单位
        disable: 是否禁用
        tracker: 进度追踪器
        bar_name: 进度条名称
        **tqdm_kwargs: tqdm 参数

    Yields:
        可迭代对象的元素

    Example:
        >>> for item in progress_iter(data_list, desc="Processing data"):
        ...     process(item)
    """
    _tracker = tracker if tracker is not None else get_global_tracker()
    _bar_name = bar_name or f"progress_iter_{id(iterable)}"

    # 尝试获取长度
    _total = total
    if _total is None and hasattr(iterable, "__len__"):
        try:
            _total = len(iterable)
        except (TypeError, AttributeError):
            pass

    # 使用生成器包装函数
    def _gen():
        yield from iterable

    return _wrap_generator(
        _gen(),
        _tracker,
        _bar_name,
        desc,
        unit,
        _total,
        disable,
        False,  # 不显示结果统计
        **tqdm_kwargs,
    )


@export
def progress_map(
    func: Callable[[T], Any],
    iterable: Iterable[T],
    total: Optional[int] = None,
    desc: str = "Mapping",
    unit: str = "it",
    disable: bool = False,
    **tqdm_kwargs,
) -> list:
    """
    带进度条的 map 函数

    类似内置 map，但显示进度。

    Args:
        func: 要应用的函数
        iterable: 可迭代对象
        total: 总数
        desc: 描述
        unit: 单位
        disable: 是否禁用
        **tqdm_kwargs: tqdm 参数

    Returns:
        结果列表

    Example:
        >>> results = progress_map(lambda x: x**2, range(100), desc="Squaring")
    """
    results = []
    for item in progress_iter(
        iterable, total=total, desc=desc, unit=unit, disable=disable, **tqdm_kwargs
    ):
        results.append(func(item))
    return results
