# -*- coding: utf-8 -*-
"""
插件性能统计和监控模块

提供插件级别的性能分析、统计收集和日志记录功能:
- 执行时间统计
- 内存使用监控
- 缓存命中率
- 调用计数
- 失败/超时统计
- 自动日志记录到文件
"""

import logging
import time
import tracemalloc
from typing import Dict, List, Optional, Any, Literal
from dataclasses import dataclass, field
from datetime import datetime
import os

from waveform_analysis.core.foundation.utils import exporter

logger = logging.getLogger(__name__)
export, __all__ = exporter()

# 监控模式
MonitoringMode = Literal['off', 'basic', 'detailed']


# ===========================
# Data Structures
# ===========================

@export
@dataclass
class PluginExecutionRecord:
    """单次插件执行记录"""
    plugin_name: str
    run_id: str
    start_time: float
    end_time: float
    duration: float
    success: bool
    cache_hit: bool
    memory_before_mb: Optional[float] = None
    memory_after_mb: Optional[float] = None
    memory_peak_mb: Optional[float] = None
    input_size_mb: Optional[float] = None
    output_size_mb: Optional[float] = None
    error: Optional[str] = None
    error_type: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@export
@dataclass
class PluginStatistics:
    """插件统计信息汇总"""
    plugin_name: str
    total_calls: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    timeout_calls: int = 0

    # 时间统计(秒)
    total_time: float = 0.0
    min_time: float = float('inf')
    max_time: float = 0.0
    mean_time: float = 0.0

    # 内存统计(MB)
    peak_memory_mb: float = 0.0
    avg_memory_mb: float = 0.0

    # 数据大小统计(MB)
    total_input_size_mb: float = 0.0
    total_output_size_mb: float = 0.0

    # 最近的错误
    recent_errors: List[str] = field(default_factory=list)

    def cache_hit_rate(self) -> float:
        """缓存命中率"""
        total = self.cache_hits + self.cache_misses
        return self.cache_hits / total if total > 0 else 0.0

    def success_rate(self) -> float:
        """成功率"""
        return self.successful_calls / self.total_calls if self.total_calls > 0 else 0.0


# ===========================
# Plugin Stats Collector
# ===========================

@export
class PluginStatsCollector:
    """
    插件统计收集器

    负责收集、聚合和报告插件性能数据

    使用示例:
        collector = PluginStatsCollector(mode='detailed')
        collector.start_execution('my_plugin', 'run_001')
        # ... plugin执行 ...
        collector.end_execution('my_plugin', success=True, cache_hit=False)

        # 获取统计
        stats = collector.get_statistics('my_plugin')
        report = collector.generate_report(format='text')
    """

    def __init__(
        self,
        mode: MonitoringMode = 'basic',
        enable_memory_tracking: bool = True,
        log_file: Optional[str] = None,
        max_recent_errors: int = 10,
    ):
        """
        初始化统计收集器

        Args:
            mode: 监控模式
                - 'off': 禁用
                - 'basic': 仅时间和调用计数
                - 'detailed': 包括内存、数据大小等
            enable_memory_tracking: 是否启用内存追踪(仅在detailed模式有效)
            log_file: 日志文件路径,None表示不写文件
            max_recent_errors: 保留的最近错误数量
        """
        self.mode = mode
        self.enable_memory_tracking = enable_memory_tracking and mode == 'detailed'
        self.log_file = log_file
        self.max_recent_errors = max_recent_errors

        # 统计数据
        self._statistics: Dict[str, PluginStatistics] = {}
        self._execution_history: List[PluginExecutionRecord] = []
        self._current_executions: Dict[str, Dict[str, Any]] = {}  # {plugin_name: execution_context}

        # 日志设置
        self._setup_logging()

        # 内存追踪
        self._memory_tracking_started = False
        if self.enable_memory_tracking:
            try:
                tracemalloc.start()
                self._memory_tracking_started = True
            except Exception as e:
                logger.warning(f"Failed to start memory tracking: {e}")
                self.enable_memory_tracking = False

    def _setup_logging(self):
        """设置日志记录"""
        if self.log_file:
            # 创建日志目录
            log_dir = os.path.dirname(self.log_file)
            if log_dir and not os.path.exists(log_dir):
                os.makedirs(log_dir, exist_ok=True)

            # 配置文件handler
            handler = logging.FileHandler(self.log_file, mode='a')
            handler.setLevel(logging.INFO)
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)

            # 确保logger级别允许INFO消息
            logger.setLevel(logging.INFO)

    def is_enabled(self) -> bool:
        """检查是否启用统计"""
        return self.mode != 'off'

    def start_execution(
        self,
        plugin_name: str,
        run_id: str,
        input_size_mb: Optional[float] = None
    ):
        """
        开始记录插件执行

        Args:
            plugin_name: 插件名称
            run_id: 运行ID
            input_size_mb: 输入数据大小(MB),可选
        """
        if not self.is_enabled():
            return

        context = {
            'plugin_name': plugin_name,
            'run_id': run_id,
            'start_time': time.time(),
            'input_size_mb': input_size_mb,
        }

        # 记录初始内存
        if self.enable_memory_tracking and self._memory_tracking_started:
            try:
                current, peak = tracemalloc.get_traced_memory()
                context['memory_before_mb'] = current / (1024 * 1024)
            except Exception:
                pass

        self._current_executions[plugin_name] = context

        # 记录日志
        if self.mode in ['basic', 'detailed']:
            logger.info(f"Plugin '{plugin_name}' started for run '{run_id}'")

    def end_execution(
        self,
        plugin_name: str,
        success: bool = True,
        cache_hit: bool = False,
        output_size_mb: Optional[float] = None,
        error: Optional[Exception] = None
    ):
        """
        结束记录插件执行

        Args:
            plugin_name: 插件名称
            success: 执行是否成功
            cache_hit: 是否命中缓存
            output_size_mb: 输出数据大小(MB),可选
            error: 错误对象,如果失败
        """
        if not self.is_enabled():
            return

        if plugin_name not in self._current_executions:
            logger.warning(f"No start record found for plugin '{plugin_name}'")
            return

        context = self._current_executions.pop(plugin_name)
        end_time = time.time()
        duration = end_time - context['start_time']

        # 记录内存
        memory_after_mb = None
        memory_peak_mb = None
        if self.enable_memory_tracking and self._memory_tracking_started:
            try:
                current, peak = tracemalloc.get_traced_memory()
                memory_after_mb = current / (1024 * 1024)
                memory_peak_mb = peak / (1024 * 1024)
            except Exception:
                pass

        # 创建执行记录
        record = PluginExecutionRecord(
            plugin_name=plugin_name,
            run_id=context['run_id'],
            start_time=context['start_time'],
            end_time=end_time,
            duration=duration,
            success=success,
            cache_hit=cache_hit,
            memory_before_mb=context.get('memory_before_mb'),
            memory_after_mb=memory_after_mb,
            memory_peak_mb=memory_peak_mb,
            input_size_mb=context.get('input_size_mb'),
            output_size_mb=output_size_mb,
            error=str(error) if error else None,
            error_type=type(error).__name__ if error else None,
        )

        self._execution_history.append(record)

        # 更新统计
        self._update_statistics(record)

        # 记录日志
        self._log_execution(record)

    def _update_statistics(self, record: PluginExecutionRecord):
        """更新统计信息"""
        plugin_name = record.plugin_name

        if plugin_name not in self._statistics:
            self._statistics[plugin_name] = PluginStatistics(plugin_name=plugin_name)

        stats = self._statistics[plugin_name]

        # 更新计数
        stats.total_calls += 1
        if record.cache_hit:
            stats.cache_hits += 1
        else:
            stats.cache_misses += 1

        if record.success:
            stats.successful_calls += 1
        else:
            stats.failed_calls += 1

        # 更新时间统计
        stats.total_time += record.duration
        stats.min_time = min(stats.min_time, record.duration)
        stats.max_time = max(stats.max_time, record.duration)
        stats.mean_time = stats.total_time / stats.total_calls

        # 更新内存统计(仅detailed模式)
        if self.mode == 'detailed' and record.memory_peak_mb is not None:
            stats.peak_memory_mb = max(stats.peak_memory_mb, record.memory_peak_mb)
            # 计算平均内存
            if stats.avg_memory_mb == 0:
                stats.avg_memory_mb = record.memory_peak_mb
            else:
                stats.avg_memory_mb = (
                    (stats.avg_memory_mb * (stats.total_calls - 1) + record.memory_peak_mb)
                    / stats.total_calls
                )

        # 更新数据大小统计
        if record.input_size_mb:
            stats.total_input_size_mb += record.input_size_mb
        if record.output_size_mb:
            stats.total_output_size_mb += record.output_size_mb

        # 记录最近的错误
        if not record.success and record.error:
            stats.recent_errors.append(f"{record.timestamp}: {record.error}")
            if len(stats.recent_errors) > self.max_recent_errors:
                stats.recent_errors = stats.recent_errors[-self.max_recent_errors:]

    def _log_execution(self, record: PluginExecutionRecord):
        """记录执行日志"""
        if self.mode == 'basic':
            if record.success:
                logger.info(
                    f"Plugin '{record.plugin_name}' completed in {record.duration:.3f}s "
                    f"(cache_hit={record.cache_hit})"
                )
            else:
                logger.error(
                    f"Plugin '{record.plugin_name}' failed after {record.duration:.3f}s: "
                    f"{record.error_type}"
                )

        elif self.mode == 'detailed':
            msg_parts = [
                f"Plugin '{record.plugin_name}' ",
                f"run='{record.run_id}' ",
                f"duration={record.duration:.3f}s ",
                f"cache_hit={record.cache_hit} ",
                f"success={record.success}",
            ]

            if record.memory_peak_mb is not None:
                msg_parts.append(f" memory_peak={record.memory_peak_mb:.2f}MB")

            if record.output_size_mb is not None:
                msg_parts.append(f" output_size={record.output_size_mb:.2f}MB")

            if not record.success:
                msg_parts.append(f" error={record.error_type}")

            logger.info(''.join(msg_parts))

    def get_statistics(self, plugin_name: Optional[str] = None) -> Dict[str, PluginStatistics]:
        """
        获取统计信息

        Args:
            plugin_name: 插件名称,None返回所有

        Returns:
            统计信息字典
        """
        if plugin_name:
            return {plugin_name: self._statistics.get(plugin_name, PluginStatistics(plugin_name))}
        return self._statistics.copy()

    def get_execution_history(
        self,
        plugin_name: Optional[str] = None,
        limit: int = 100
    ) -> List[PluginExecutionRecord]:
        """
        获取执行历史

        Args:
            plugin_name: 插件名称过滤,None返回所有
            limit: 返回最近N条记录

        Returns:
            执行记录列表
        """
        history = self._execution_history

        if plugin_name:
            history = [r for r in history if r.plugin_name == plugin_name]

        return history[-limit:]

    def generate_report(self, format: Literal['text', 'dict'] = 'text') -> Any:
        """
        生成统计报告

        Args:
            format: 报告格式
                - 'text': 文本格式
                - 'dict': 字典格式(可序列化为JSON)

        Returns:
            报告内容
        """
        if format == 'dict':
            return self._generate_dict_report()
        elif format == 'text':
            return self._generate_text_report()
        else:
            raise ValueError(f"Unknown report format: {format}")

    def _generate_dict_report(self) -> Dict[str, Any]:
        """生成字典格式报告"""
        report = {
            'summary': {
                'total_plugins': len(self._statistics),
                'total_executions': len(self._execution_history),
                'monitoring_mode': self.mode,
                'generated_at': datetime.now().isoformat(),
            },
            'plugins': {}
        }

        for plugin_name, stats in self._statistics.items():
            report['plugins'][plugin_name] = {
                'total_calls': stats.total_calls,
                'cache_hit_rate': f"{stats.cache_hit_rate():.1%}",
                'success_rate': f"{stats.success_rate():.1%}",
                'time_stats': {
                    'total': f"{stats.total_time:.2f}s",
                    'mean': f"{stats.mean_time:.3f}s",
                    'min': f"{stats.min_time:.3f}s",
                    'max': f"{stats.max_time:.3f}s",
                },
            }

            if self.mode == 'detailed':
                report['plugins'][plugin_name]['memory_stats'] = {
                    'peak_mb': f"{stats.peak_memory_mb:.2f}",
                    'avg_mb': f"{stats.avg_memory_mb:.2f}",
                }

            if stats.recent_errors:
                report['plugins'][plugin_name]['recent_errors'] = stats.recent_errors[-3:]

        return report

    def _generate_text_report(self) -> str:
        """生成文本格式报告"""
        lines = []
        lines.append("=" * 80)
        lines.append("Plugin Performance Report")
        lines.append("=" * 80)
        lines.append(f"Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"Monitoring mode: {self.mode}")
        lines.append(f"Total plugins: {len(self._statistics)}")
        lines.append(f"Total executions: {len(self._execution_history)}")
        lines.append("")

        for plugin_name, stats in sorted(self._statistics.items()):
            lines.append("-" * 80)
            lines.append(f"Plugin: {plugin_name}")
            lines.append("-" * 80)
            lines.append(f"  Total calls: {stats.total_calls}")
            lines.append(f"  Cache hit rate: {stats.cache_hit_rate():.1%} ({stats.cache_hits}/{stats.total_calls})")
            lines.append(f"  Success rate: {stats.success_rate():.1%}")
            lines.append(f"  Failed calls: {stats.failed_calls}")
            lines.append("")
            lines.append("  Time statistics:")
            lines.append(f"    Total: {stats.total_time:.2f}s")
            lines.append(f"    Mean:  {stats.mean_time:.3f}s")
            lines.append(f"    Min:   {stats.min_time:.3f}s")
            lines.append(f"    Max:   {stats.max_time:.3f}s")

            if self.mode == 'detailed':
                lines.append("")
                lines.append("  Memory statistics:")
                lines.append(f"    Peak: {stats.peak_memory_mb:.2f} MB")
                lines.append(f"    Avg:  {stats.avg_memory_mb:.2f} MB")

            if stats.recent_errors:
                lines.append("")
                lines.append(f"  Recent errors (last {min(3, len(stats.recent_errors))}):")
                for error in stats.recent_errors[-3:]:
                    lines.append(f"    - {error}")

            lines.append("")

        lines.append("=" * 80)
        return "\n".join(lines)

    def reset(self):
        """重置所有统计数据"""
        self._statistics.clear()
        self._execution_history.clear()
        self._current_executions.clear()

    def __del__(self):
        """析构函数:停止内存追踪"""
        if self._memory_tracking_started:
            try:
                tracemalloc.stop()
            except Exception:
                pass


# ===========================
# Global Instance
# ===========================

_stats_collector = None

@export
def get_stats_collector(
    mode: MonitoringMode = 'basic',
    log_file: Optional[str] = None,
    reset: bool = False
) -> PluginStatsCollector:
    """
    获取全局统计收集器

    Args:
        mode: 监控模式
        log_file: 日志文件路径
        reset: 是否重置现有收集器

    Returns:
        PluginStatsCollector实例
    """
    global _stats_collector

    if _stats_collector is None or reset:
        _stats_collector = PluginStatsCollector(mode=mode, log_file=log_file)

    return _stats_collector
