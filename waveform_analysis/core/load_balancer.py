"""
动态负载均衡模块 (Phase 3 Enhancement)

提供动态负载均衡功能:
- 监控系统CPU和内存使用率
- 根据负载动态调整worker数量
- 根据任务大小智能分配
- 任务历史记录和统计
"""

import logging
import multiprocessing
import time
from typing import Dict, List, Optional

try:
    import psutil
except ImportError:
    psutil = None

from waveform_analysis.core.utils import exporter

logger = logging.getLogger(__name__)
export, __all__ = exporter()


# ===========================
# 动态负载均衡器
# ===========================

@export
class DynamicLoadBalancer:
    """
    动态负载均衡器

    特性:
    - 监控系统CPU和内存使用率
    - 根据负载动态调整worker数量
    - 根据任务大小智能分配
    - 避免资源浪费

    使用示例:
        balancer = DynamicLoadBalancer(
            min_workers=1,
            max_workers=8,
            cpu_threshold=0.8,
            memory_threshold=0.85
        )

        # 获取当前最优worker数量
        optimal_workers = balancer.get_optimal_workers(n_tasks=100)

        # 记录任务完成
        balancer.record_task_completion(duration=2.5, success=True)

        # 获取统计信息
        stats = balancer.get_statistics()
    """

    def __init__(
        self,
        min_workers: int = 1,
        max_workers: Optional[int] = None,
        cpu_threshold: float = 0.8,      # CPU使用率阈值
        memory_threshold: float = 0.85,  # 内存使用率阈值
        check_interval: float = 5.0      # 检查间隔（秒）
    ):
        """
        初始化负载均衡器

        Args:
            min_workers: 最小worker数量
            max_workers: 最大worker数量（None=CPU核心数）
            cpu_threshold: CPU使用率阈值（0-1）
            memory_threshold: 内存使用率阈值（0-1）
            check_interval: 检查间隔（秒）
        """
        self.min_workers = min_workers
        self.max_workers = max_workers or multiprocessing.cpu_count()
        self.cpu_threshold = cpu_threshold
        self.memory_threshold = memory_threshold
        self.check_interval = check_interval

        self._current_workers = self.min_workers
        self._last_check_time = 0
        self._task_history: List[Dict] = []  # 任务执行历史
        self.logger = logging.getLogger(self.__class__.__name__)

        # 检查psutil是否可用
        if psutil is None:
            self.logger.warning(
                "psutil not available. Load balancing will use basic heuristics. "
                "Install with: pip install psutil"
            )

    def get_optimal_workers(
        self,
        n_tasks: int,
        estimated_task_size: Optional[int] = None
    ) -> int:
        """
        获取当前最优worker数量

        Args:
            n_tasks: 任务总数
            estimated_task_size: 估计的任务大小（字节）

        Returns:
            建议的worker数量
        """
        # 1. 检查是否需要更新
        current_time = time.time()
        if current_time - self._last_check_time < self.check_interval:
            # 未到检查间隔，返回当前值
            return min(self._current_workers, n_tasks)

        self._last_check_time = current_time

        if psutil is None:
            # 没有psutil，使用简单策略
            suggested_workers = min(self.max_workers, n_tasks, multiprocessing.cpu_count())
        else:
            # 2. 获取系统资源状态
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory_info = psutil.virtual_memory()
            memory_percent = memory_info.percent / 100.0

            # 3. 根据负载调整worker数量
            if cpu_percent > self.cpu_threshold * 100:
                # CPU过载，减少worker
                suggested_workers = max(self.min_workers, self._current_workers - 1)
                self.logger.debug(f"High CPU ({cpu_percent:.1f}%), reducing workers")
            elif memory_percent > self.memory_threshold:
                # 内存不足，减少worker
                suggested_workers = max(self.min_workers, self._current_workers - 1)
                self.logger.debug(f"High memory ({memory_percent*100:.1f}%), reducing workers")
            elif cpu_percent < 0.5 * self.cpu_threshold * 100 and memory_percent < 0.7 * self.memory_threshold:
                # 资源充足，增加worker
                suggested_workers = min(self.max_workers, self._current_workers + 1)
                self.logger.debug(f"Resources available, increasing workers")
            else:
                # 保持当前worker数量
                suggested_workers = self._current_workers

            # 4. 考虑任务数量限制
            suggested_workers = min(suggested_workers, n_tasks)

            # 5. 根据任务大小调整
            if estimated_task_size is not None and estimated_task_size > 0:
                # 大任务：减少worker以避免内存溢出
                available_memory = memory_info.available
                max_workers_by_memory = max(1, available_memory // (estimated_task_size * 2))
                suggested_workers = min(suggested_workers, max_workers_by_memory)
                self.logger.debug(
                    f"Task size: {estimated_task_size / 1024 / 1024:.1f}MB, "
                    f"limiting workers to {max_workers_by_memory}"
                )

            self.logger.debug(
                f"Load balancer: CPU={cpu_percent:.1f}%, Memory={memory_percent*100:.1f}%, "
                f"Workers={suggested_workers}/{self.max_workers}"
            )

        self._current_workers = suggested_workers
        return suggested_workers

    def record_task_completion(
        self,
        duration: float,
        memory_used: Optional[int] = None,
        success: bool = True
    ):
        """
        记录任务完成情况（用于未来优化）

        Args:
            duration: 任务执行时间（秒）
            memory_used: 内存使用（字节）
            success: 是否成功
        """
        self._task_history.append({
            'duration': duration,
            'memory_used': memory_used,
            'success': success,
            'workers': self._current_workers,
            'timestamp': time.time()
        })

        # 保留最近1000条记录
        if len(self._task_history) > 1000:
            self._task_history = self._task_history[-1000:]

    def get_statistics(self) -> Dict:
        """
        获取负载均衡统计信息

        Returns:
            统计信息字典
        """
        if not self._task_history:
            return {
                'total_tasks': 0,
                'current_workers': self._current_workers
            }

        durations = [t['duration'] for t in self._task_history]
        successful_tasks = [t for t in self._task_history if t['success']]

        stats = {
            'total_tasks': len(self._task_history),
            'successful_tasks': len(successful_tasks),
            'failed_tasks': len(self._task_history) - len(successful_tasks),
            'avg_duration': sum(durations) / len(durations),
            'min_duration': min(durations),
            'max_duration': max(durations),
            'current_workers': self._current_workers,
            'min_workers': self.min_workers,
            'max_workers': self.max_workers
        }

        # 如果有内存记录
        memory_used_list = [t['memory_used'] for t in self._task_history if t.get('memory_used')]
        if memory_used_list:
            stats['avg_memory_mb'] = sum(memory_used_list) / len(memory_used_list) / 1024 / 1024
            stats['max_memory_mb'] = max(memory_used_list) / 1024 / 1024

        return stats

    def reset(self):
        """
        重置负载均衡器状态

        清除任务历史，重置worker数量
        """
        self._current_workers = self.min_workers
        self._last_check_time = 0
        self._task_history.clear()
        self.logger.info("Load balancer reset")


@export
def get_system_info() -> Dict:
    """
    获取系统资源信息

    Returns:
        系统信息字典
    """
    info = {
        'cpu_count': multiprocessing.cpu_count(),
        'psutil_available': psutil is not None
    }

    if psutil is not None:
        info['cpu_percent'] = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        info['memory_total_gb'] = memory.total / 1024 / 1024 / 1024
        info['memory_available_gb'] = memory.available / 1024 / 1024 / 1024
        info['memory_percent'] = memory.percent

    return info
