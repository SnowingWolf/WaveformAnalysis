"""
进度追踪模块 (Phase 3 Enhancement)

提供统一的进度追踪系统:
- tqdm集成的进度条
- 嵌套进度显示
- ETA和吞吐量计算
- 线程安全
"""

import logging
import threading
import time
from typing import Any, Dict, Optional

from tqdm import tqdm

from waveform_analysis.core.utils import exporter

logger = logging.getLogger(__name__)
export, __all__ = exporter()


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
        self._lock = threading.Lock()
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
        **kwargs
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
                parent_pos = self._bar_info[parent].get('position', 0)
                parent_nested_count = self._bar_info[parent].get('nested_count', 0)
                position = parent_pos + parent_nested_count + 1
                self._bar_info[parent]['nested_count'] = parent_nested_count + 1
            elif nested:
                position = self._position_counter
                self._position_counter += 1
            else:
                position = self._position_counter
                self._position_counter += 1

            # 创建tqdm进度条
            bar = tqdm(
                total=total,
                desc=desc,
                unit=unit,
                position=position,
                leave=True,
                disable=self.disable,
                **kwargs
            )

            self._bars[name] = bar
            self._bar_info[name] = {
                'parent': parent,
                'nested': nested,
                'position': position,
                'nested_count': 0,  # 子进度条数量
                'start_time': time.time()
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

            start_time = self._bar_info[name]['start_time']
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
