"""
缓存统计模块 - 统计收集与报告。

提供缓存使用情况统计、磁盘使用分析和报告导出功能。
"""

from dataclasses import dataclass, field
import json
import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from ..foundation.utils import exporter
from .cache_analyzer import CacheAnalyzer, CacheEntry

if TYPE_CHECKING:
    pass

export, __all__ = exporter()


@export
@dataclass
class CacheStatistics:
    """缓存统计数据类

    Attributes:
        total_runs: 总运行数
        total_entries: 总缓存条目数
        total_size_bytes: 总大小（字节）
        compressed_entries: 压缩条目数
        avg_entry_size_bytes: 平均条目大小
        largest_entry: 最大的缓存条目
        oldest_entry: 最旧的缓存条目
        newest_entry: 最新的缓存条目
        by_run: 按运行分组的统计
        by_data_type: 按数据类型分组的统计
        scan_time: 扫描时间
    """

    total_runs: int
    total_entries: int
    total_size_bytes: int
    compressed_entries: int
    avg_entry_size_bytes: float
    largest_entry: Optional[CacheEntry]
    oldest_entry: Optional[CacheEntry]
    newest_entry: Optional[CacheEntry]
    by_run: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    by_data_type: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    scan_time: float = 0.0

    @property
    def total_size_human(self) -> str:
        """人类可读的总大小"""
        return CacheStatsCollector._format_size(self.total_size_bytes)

    @property
    def avg_entry_size_human(self) -> str:
        """人类可读的平均条目大小"""
        return CacheStatsCollector._format_size(int(self.avg_entry_size_bytes))

    @property
    def compression_ratio(self) -> float:
        """压缩率（压缩条目数/总条目数）"""
        if self.total_entries == 0:
            return 0.0
        return self.compressed_entries / self.total_entries

    def to_dict(self) -> Dict[str, Any]:
        """转换为可序列化的字典"""
        result = {
            "total_runs": self.total_runs,
            "total_entries": self.total_entries,
            "total_size_bytes": self.total_size_bytes,
            "total_size_human": self.total_size_human,
            "compressed_entries": self.compressed_entries,
            "compression_ratio": self.compression_ratio,
            "avg_entry_size_bytes": self.avg_entry_size_bytes,
            "avg_entry_size_human": self.avg_entry_size_human,
            "scan_time": self.scan_time,
            "by_run": self.by_run,
            "by_data_type": self.by_data_type,
        }

        # 序列化 CacheEntry 对象
        if self.largest_entry:
            result["largest_entry"] = self._entry_to_dict(self.largest_entry)
        else:
            result["largest_entry"] = None

        if self.oldest_entry:
            result["oldest_entry"] = self._entry_to_dict(self.oldest_entry)
        else:
            result["oldest_entry"] = None

        if self.newest_entry:
            result["newest_entry"] = self._entry_to_dict(self.newest_entry)
        else:
            result["newest_entry"] = None

        return result

    @staticmethod
    def _entry_to_dict(entry: CacheEntry) -> Dict[str, Any]:
        """将 CacheEntry 转换为字典（不包含 metadata）"""
        return {
            "run_id": entry.run_id,
            "data_name": entry.data_name,
            "key": entry.key,
            "size_bytes": entry.size_bytes,
            "size_human": entry.size_human,
            "created_at": entry.created_at,
            "created_at_str": entry.created_at_str,
            "plugin_version": entry.plugin_version,
            "compressed": entry.compressed,
        }


@export
class CacheStatsCollector:
    """缓存统计收集器

    提供缓存使用情况统计、磁盘使用分析和报告导出功能。

    Features:
        - 收集全局和分组统计
        - 磁盘使用分析
        - JSON/CSV 格式导出
        - 与 Context 统计收集器集成

    Examples:
        >>> analyzer = CacheAnalyzer(ctx)
        >>> analyzer.scan()
        >>>
        >>> collector = CacheStatsCollector(analyzer)
        >>> stats = collector.collect()
        >>> collector.print_summary(stats, detailed=True)
        >>>
        >>> # 导出统计
        >>> collector.export_stats(stats, 'cache_stats.json')
    """

    def __init__(self, analyzer: CacheAnalyzer):
        """初始化 CacheStatsCollector

        Args:
            analyzer: CacheAnalyzer 实例（需要已完成扫描）
        """
        self.analyzer = analyzer
        self.ctx = analyzer.ctx

    def collect(self, run_id: Optional[str] = None) -> CacheStatistics:
        """收集缓存统计信息

        Args:
            run_id: 仅统计指定 run，None 则统计所有

        Returns:
            CacheStatistics 统计数据
        """
        start_time = time.time()

        entries = self.analyzer.get_entries(run_id=run_id)

        if not entries:
            return CacheStatistics(
                total_runs=0,
                total_entries=0,
                total_size_bytes=0,
                compressed_entries=0,
                avg_entry_size_bytes=0.0,
                largest_entry=None,
                oldest_entry=None,
                newest_entry=None,
                by_run={},
                by_data_type={},
                scan_time=time.time() - start_time,
            )

        # 基础统计
        total_size = sum(e.size_bytes for e in entries)
        compressed_count = sum(1 for e in entries if e.compressed)
        runs = {e.run_id for e in entries}

        largest = max(entries, key=lambda e: e.size_bytes)
        oldest = min(entries, key=lambda e: e.created_at)
        newest = max(entries, key=lambda e: e.created_at)

        # 按运行分组统计
        by_run = self._collect_by_run(entries)

        # 按数据类型分组统计
        by_data_type = self._collect_by_data_type(entries)

        return CacheStatistics(
            total_runs=len(runs),
            total_entries=len(entries),
            total_size_bytes=total_size,
            compressed_entries=compressed_count,
            avg_entry_size_bytes=total_size / len(entries) if entries else 0.0,
            largest_entry=largest,
            oldest_entry=oldest,
            newest_entry=newest,
            by_run=by_run,
            by_data_type=by_data_type,
            scan_time=time.time() - start_time,
        )

    def _collect_by_run(self, entries: List[CacheEntry]) -> Dict[str, Dict[str, Any]]:
        """按运行分组统计"""
        by_run: Dict[str, Dict[str, Any]] = {}

        for entry in entries:
            if entry.run_id not in by_run:
                by_run[entry.run_id] = {
                    "entry_count": 0,
                    "total_size_bytes": 0,
                    "compressed_count": 0,
                    "data_types": set(),
                    "oldest_created_at": float("inf"),
                    "newest_created_at": 0,
                }

            stats = by_run[entry.run_id]
            stats["entry_count"] += 1
            stats["total_size_bytes"] += entry.size_bytes
            if entry.compressed:
                stats["compressed_count"] += 1
            stats["data_types"].add(entry.data_name)
            stats["oldest_created_at"] = min(stats["oldest_created_at"], entry.created_at)
            stats["newest_created_at"] = max(stats["newest_created_at"], entry.created_at)

        # 转换 set 为 list 并添加人类可读大小
        for _run_id, stats in by_run.items():
            stats["data_types"] = sorted(stats["data_types"])
            stats["total_size_human"] = self._format_size(stats["total_size_bytes"])
            # 处理无限值
            if stats["oldest_created_at"] == float("inf"):
                stats["oldest_created_at"] = 0

        return by_run

    def _collect_by_data_type(self, entries: List[CacheEntry]) -> Dict[str, Dict[str, Any]]:
        """按数据类型分组统计"""
        by_type: Dict[str, Dict[str, Any]] = {}

        for entry in entries:
            if entry.data_name not in by_type:
                by_type[entry.data_name] = {
                    "entry_count": 0,
                    "total_size_bytes": 0,
                    "compressed_count": 0,
                    "runs": set(),
                    "versions": set(),
                    "avg_entry_size": 0,
                }

            stats = by_type[entry.data_name]
            stats["entry_count"] += 1
            stats["total_size_bytes"] += entry.size_bytes
            if entry.compressed:
                stats["compressed_count"] += 1
            stats["runs"].add(entry.run_id)
            stats["versions"].add(entry.plugin_version)

        # 计算平均大小并转换 set 为 list
        for _data_name, stats in by_type.items():
            stats["runs"] = sorted(stats["runs"])
            stats["versions"] = sorted(stats["versions"])
            stats["run_count"] = len(stats["runs"])
            stats["total_size_human"] = self._format_size(stats["total_size_bytes"])
            if stats["entry_count"] > 0:
                stats["avg_entry_size"] = stats["total_size_bytes"] / stats["entry_count"]
                stats["avg_entry_size_human"] = self._format_size(int(stats["avg_entry_size"]))

        return by_type

    def print_summary(self, stats: CacheStatistics, detailed: bool = False):
        """打印统计摘要

        Args:
            stats: 统计数据
            detailed: 是否显示详细信息
        """
        print("\n" + "=" * 70)
        print("缓存统计报告")
        print("=" * 70)

        # 总体统计
        print("\n【总体概览】")
        print(f"  运行数量: {stats.total_runs}")
        print(f"  缓存条目: {stats.total_entries}")
        print(f"  总大小: {stats.total_size_human}")
        print(f"  平均条目大小: {stats.avg_entry_size_human}")
        print(f"  压缩条目: {stats.compressed_entries} ({stats.compression_ratio*100:.1f}%)")

        # 关键条目
        if stats.largest_entry:
            print("\n【最大缓存】")
            print(f"  {stats.largest_entry.key}")
            print(f"  大小: {stats.largest_entry.size_human}")
            print(f"  运行: {stats.largest_entry.run_id}")
            print(f"  类型: {stats.largest_entry.data_name}")

        if stats.oldest_entry:
            print("\n【最旧缓存】")
            print(f"  {stats.oldest_entry.key}")
            print(f"  创建于: {stats.oldest_entry.created_at_str}")
            print(f"  年龄: {stats.oldest_entry.age_days:.1f} 天")

        if stats.newest_entry:
            print("\n【最新缓存】")
            print(f"  {stats.newest_entry.key}")
            print(f"  创建于: {stats.newest_entry.created_at_str}")

        if detailed:
            # 按运行统计
            if stats.by_run:
                print("\n" + "-" * 70)
                print("【按运行统计】")
                for run_id in sorted(stats.by_run.keys()):
                    run_stats = stats.by_run[run_id]
                    print(f"\n  {run_id}:")
                    print(f"    条目数: {run_stats['entry_count']}")
                    print(f"    大小: {run_stats['total_size_human']}")
                    print(f"    压缩: {run_stats['compressed_count']}")
                    print(f"    数据类型: {', '.join(run_stats['data_types'])}")

            # 按数据类型统计
            if stats.by_data_type:
                print("\n" + "-" * 70)
                print("【按数据类型统计】")
                for data_name in sorted(stats.by_data_type.keys()):
                    type_stats = stats.by_data_type[data_name]
                    print(f"\n  {data_name}:")
                    print(f"    条目数: {type_stats['entry_count']}")
                    print(f"    总大小: {type_stats['total_size_human']}")
                    print(f"    平均大小: {type_stats.get('avg_entry_size_human', 'N/A')}")
                    print(f"    运行数: {type_stats['run_count']}")
                    print(f"    版本: {', '.join(type_stats['versions'])}")

        print("\n" + "=" * 70)
        print(f"统计耗时: {stats.scan_time*1000:.1f} ms")

    def get_hit_rate_stats(self) -> Dict[str, Any]:
        """获取缓存命中率统计

        集成 Context 的 stats_collector（如果可用）

        Returns:
            命中率统计字典
        """
        result = {
            "available": False,
            "total_hits": 0,
            "total_misses": 0,
            "hit_rate": 0.0,
            "by_plugin": {},
        }

        # 检查是否有统计收集器
        if not hasattr(self.ctx, "stats_collector") or self.ctx.stats_collector is None:
            return result

        stats_collector = self.ctx.stats_collector
        if not hasattr(stats_collector, "get_statistics"):
            return result

        result["available"] = True

        try:
            # 获取统计数据
            stats = stats_collector.get_statistics()

            # 提取命中率信息
            if "plugins" in stats:
                for plugin_name, plugin_stats in stats["plugins"].items():
                    cache_hits = plugin_stats.get("cache_hits", 0)
                    total_calls = plugin_stats.get("total_calls", 0)

                    result["total_hits"] += cache_hits
                    result["total_misses"] += total_calls - cache_hits

                    if total_calls > 0:
                        result["by_plugin"][plugin_name] = {
                            "hits": cache_hits,
                            "misses": total_calls - cache_hits,
                            "hit_rate": cache_hits / total_calls,
                        }

            total = result["total_hits"] + result["total_misses"]
            if total > 0:
                result["hit_rate"] = result["total_hits"] / total

        except Exception as e:
            result["error"] = str(e)

        return result

    def analyze_disk_usage(self) -> Dict[str, Any]:
        """分析磁盘使用情况

        Returns:
            磁盘使用分析结果
        """
        import os

        result = {
            "storage_dir": "",
            "total_disk_space": 0,
            "used_disk_space": 0,
            "free_disk_space": 0,
            "cache_size": 0,
            "cache_percentage": 0.0,
        }

        # 获取存储目录
        if hasattr(self.analyzer.storage, "work_dir"):
            storage_dir = self.analyzer.storage.work_dir
        elif hasattr(self.analyzer.storage, "base_dir"):
            storage_dir = self.analyzer.storage.base_dir
        else:
            return result

        result["storage_dir"] = storage_dir

        # 获取磁盘使用情况
        try:
            stat = os.statvfs(storage_dir)
            result["total_disk_space"] = stat.f_blocks * stat.f_frsize
            result["free_disk_space"] = stat.f_bavail * stat.f_frsize
            result["used_disk_space"] = result["total_disk_space"] - result["free_disk_space"]

            result["total_disk_space_human"] = self._format_size(result["total_disk_space"])
            result["free_disk_space_human"] = self._format_size(result["free_disk_space"])
            result["used_disk_space_human"] = self._format_size(result["used_disk_space"])

        except Exception as e:
            result["disk_error"] = str(e)

        # 获取缓存大小
        result["cache_size"] = self.analyzer.get_total_size()
        result["cache_size_human"] = self._format_size(result["cache_size"])

        if result["total_disk_space"] > 0:
            result["cache_percentage"] = (result["cache_size"] / result["total_disk_space"]) * 100

        return result

    def export_stats(self, stats: CacheStatistics, output_path: str, format: str = "json"):
        """导出统计数据

        Args:
            stats: 统计数据
            output_path: 输出文件路径
            format: 输出格式 ('json', 'csv')
        """
        if format == "json":
            self._export_json(stats, output_path)
        elif format == "csv":
            self._export_csv(stats, output_path)
        else:
            raise ValueError(f"不支持的格式: {format}")

        print(f"[CacheStatsCollector] 统计数据已导出到: {output_path}")

    def _export_json(self, stats: CacheStatistics, output_path: str):
        """导出为 JSON"""
        data = stats.to_dict()
        data["export_time"] = time.time()
        data["export_time_str"] = time.strftime("%Y-%m-%d %H:%M:%S")

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)

    def _export_csv(self, stats: CacheStatistics, output_path: str):
        """导出为 CSV"""
        import csv

        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)

            # 写入总体统计
            writer.writerow(["=== 总体统计 ==="])
            writer.writerow(["指标", "值"])
            writer.writerow(["运行数量", stats.total_runs])
            writer.writerow(["缓存条目", stats.total_entries])
            writer.writerow(["总大小", stats.total_size_human])
            writer.writerow(["压缩条目", stats.compressed_entries])
            writer.writerow(["压缩率", f"{stats.compression_ratio*100:.1f}%"])
            writer.writerow([])

            # 写入按运行统计
            if stats.by_run:
                writer.writerow(["=== 按运行统计 ==="])
                writer.writerow(["运行ID", "条目数", "大小", "压缩数", "数据类型"])
                for run_id, run_stats in sorted(stats.by_run.items()):
                    writer.writerow(
                        [
                            run_id,
                            run_stats["entry_count"],
                            run_stats["total_size_human"],
                            run_stats["compressed_count"],
                            "; ".join(run_stats["data_types"]),
                        ]
                    )
                writer.writerow([])

            # 写入按数据类型统计
            if stats.by_data_type:
                writer.writerow(["=== 按数据类型统计 ==="])
                writer.writerow(["数据类型", "条目数", "总大小", "平均大小", "运行数", "版本"])
                for data_name, type_stats in sorted(stats.by_data_type.items()):
                    writer.writerow(
                        [
                            data_name,
                            type_stats["entry_count"],
                            type_stats["total_size_human"],
                            type_stats.get("avg_entry_size_human", "N/A"),
                            type_stats["run_count"],
                            "; ".join(type_stats["versions"]),
                        ]
                    )

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        """格式化大小"""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"
