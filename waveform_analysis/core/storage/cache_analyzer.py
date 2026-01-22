# -*- coding: utf-8 -*-
"""
缓存分析器模块 - 统一的缓存扫描与索引接口。

提供 CacheEntry 数据类和 CacheAnalyzer 分析器，用于：
- 扫描和索引缓存条目
- 查询和过滤缓存数据
- 统计缓存大小和分布


"""

import os
import threading
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from ..foundation.utils import exporter

if TYPE_CHECKING:
    from ..context import Context

export, __all__ = exporter()


@export
@dataclass
class CacheEntry:
    """缓存条目元数据

    存储单个缓存文件的完整元数据信息，用于缓存分析和管理。

    Attributes:
        run_id: 运行标识符
        data_name: 数据类型名称（插件提供的数据名）
        key: 完整的缓存键（格式: run_id-data_name-lineage_hash）
        size_bytes: 缓存文件大小（字节）
        created_at: 创建时间戳
        plugin_version: 插件版本号
        dtype_str: 数据类型字符串
        count: 数据记录数
        compressed: 是否压缩
        has_checksum: 是否有校验和
        file_path: 数据文件完整路径
        metadata: 原始元数据字典
    """

    run_id: str
    data_name: str
    key: str
    size_bytes: int
    created_at: float
    plugin_version: str
    dtype_str: str
    count: int
    compressed: bool
    has_checksum: bool
    file_path: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def size_mb(self) -> float:
        """返回大小（MB）"""
        return self.size_bytes / (1024 * 1024)

    @property
    def size_human(self) -> str:
        """返回人类可读的大小字符串"""
        if self.size_bytes < 1024:
            return f"{self.size_bytes} B"
        elif self.size_bytes < 1024 * 1024:
            return f"{self.size_bytes / 1024:.1f} KB"
        elif self.size_bytes < 1024 * 1024 * 1024:
            return f"{self.size_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{self.size_bytes / (1024 * 1024 * 1024):.2f} GB"

    @property
    def age_days(self) -> float:
        """返回缓存年龄（天）"""
        return (time.time() - self.created_at) / (24 * 3600)

    @property
    def created_at_str(self) -> str:
        """返回人类可读的创建时间"""
        import datetime

        return datetime.datetime.fromtimestamp(self.created_at).strftime("%Y-%m-%d %H:%M:%S")


@export
class CacheAnalyzer:
    """缓存分析器 - 统一的缓存扫描与索引接口

    提供缓存扫描、索引和查询功能，是缓存管理工具集的核心组件。

    Features:
        - 扫描所有 run 的缓存数据
        - 支持增量扫描（避免重复遍历）
        - 线程安全的缓存索引
        - 灵活的过滤和查询接口

    Examples:e
        >>> from waveform_analysis.core.context import Context
        >>> ctx = Context(storage_dir='./cache')
        >>>
        >>> # 创建分析器并扫描
        >>> analyzer = CacheAnalyzer(ctx)
        >>> analyzer.scan()
        >>>
        >>> # 获取所有条目
        >>> entries = analyzer.get_entries()
        >>>
        >>> # 按 run_id 过滤
        >>> run_entries = analyzer.get_entries(run_id='run_001')
        >>>
        >>> # 按大小过滤
        >>> large_entries = analyzer.get_entries(min_size=1024*1024)
    """

    def __init__(self, context: "Context"):
        """初始化 CacheAnalyzer

        Args:
            context: Context 实例，用于访问存储层
        """
        self.ctx = context
        self._cache_index: Dict[str, List[CacheEntry]] = {}  # run_id -> entries
        self._lock = threading.Lock()
        self._last_scan_time: Optional[float] = None
        self._scanned_runs: set = set()

    @property
    def storage(self):
        """获取存储实例"""
        return self.ctx.storage

    def scan(
        self, force_refresh: bool = False, run_ids: Optional[List[str]] = None, verbose: bool = True
    ) -> Dict[str, List[CacheEntry]]:
        """扫描缓存目录，构建索引

        Args:
            force_refresh: 强制刷新，忽略已有索引
            run_ids: 仅扫描指定的 run_id 列表，None 则扫描所有
            verbose: 是否显示扫描进度

        Returns:
            Dict[str, List[CacheEntry]]: run_id 到 CacheEntry 列表的映射
        """
        with self._lock:
            if force_refresh:
                self._cache_index.clear()
                self._scanned_runs.clear()

            # 获取所有 run_id
            all_runs = self.storage.list_runs()

            # 如果存储不支持 run_subdirs 模式，尝试从 key 中提取 run_id
            if not all_runs and hasattr(self.storage, "use_run_subdirs"):
                if not self.storage.use_run_subdirs:
                    all_runs = self._extract_runs_from_flat_storage()

            # 过滤要扫描的 run
            if run_ids is not None:
                runs_to_scan = [r for r in run_ids if r in all_runs or r not in self._scanned_runs]
            else:
                runs_to_scan = [r for r in all_runs if r not in self._scanned_runs or force_refresh]

            if verbose and runs_to_scan:
                print(f"[CacheAnalyzer] 扫描 {len(runs_to_scan)} 个运行的缓存...")

            total_entries = 0
            for run_id in runs_to_scan:
                entries = self._scan_run(run_id)
                self._cache_index[run_id] = entries
                self._scanned_runs.add(run_id)
                total_entries += len(entries)

            self._last_scan_time = time.time()

            if verbose and runs_to_scan:
                total_size = sum(e.size_bytes for entries in self._cache_index.values() for e in entries)
                print(
                    f"[CacheAnalyzer] 扫描完成: {len(self._cache_index)} 个运行, "
                    f"{total_entries} 个缓存条目, 总大小 {self._format_size(total_size)}"
                )

            return self._cache_index.copy()

    def _extract_runs_from_flat_storage(self) -> List[str]:
        """从扁平存储结构中提取 run_id 列表"""
        runs = set()
        keys = self.storage.list_keys()
        for key in keys:
            # key 格式: "run_id-data_name-lineage_hash"
            parts = key.split("-")
            if len(parts) >= 2:
                runs.add(parts[0])
        return sorted(runs)

    def _scan_run(self, run_id: str) -> List[CacheEntry]:
        """扫描单个 run 的缓存

        Args:
            run_id: 运行标识符

        Returns:
            该 run 的所有 CacheEntry 列表
        """
        entries = []

        # 获取该 run 的所有 key
        keys = self.storage.list_keys(run_id)

        # 如果是扁平模式，过滤出属于该 run 的 key
        if not keys and hasattr(self.storage, "use_run_subdirs"):
            if not self.storage.use_run_subdirs:
                all_keys = self.storage.list_keys()
                keys = [k for k in all_keys if k.startswith(f"{run_id}-")]

        for key in keys:
            entry = self._create_entry(run_id, key)
            if entry is not None:
                entries.append(entry)

        return entries

    def _create_entry(self, run_id: str, key: str) -> Optional[CacheEntry]:
        """从 key 创建 CacheEntry

        Args:
            run_id: 运行标识符
            key: 缓存键

        Returns:
            CacheEntry 或 None（如果元数据不存在）
        """
        metadata = self.storage.get_metadata(key, run_id)
        if metadata is None:
            return None

        # 解析 key 获取 data_name
        # key 格式: "run_id-data_name-lineage_hash"
        parts = key.split("-")
        if len(parts) >= 2:
            data_name = parts[1]
        else:
            data_name = key

        # 获取文件路径和大小
        file_path, size_bytes = self._get_file_info(key, run_id, metadata)

        # 提取插件版本（可能在 lineage 或直接在 metadata 中）
        plugin_version = self._extract_plugin_version(data_name, metadata)

        return CacheEntry(
            run_id=run_id,
            data_name=data_name,
            key=key,
            size_bytes=size_bytes,
            created_at=metadata.get("timestamp", 0),
            plugin_version=plugin_version,
            dtype_str=metadata.get("dtype", "unknown"),
            count=metadata.get("count", 0),
            compressed=metadata.get("compressed", False),
            has_checksum="checksum" in metadata,
            file_path=file_path,
            metadata=metadata,
        )

    def _get_file_info(self, key: str, run_id: str, metadata: Dict[str, Any]) -> tuple:
        """获取文件路径和大小

        Returns:
            (file_path, size_bytes)
        """
        # 获取路径
        if hasattr(self.storage, "_get_paths"):
            bin_path, _, _ = self.storage._get_paths(key, run_id)
        else:
            bin_path = os.path.join(self.storage.base_dir, f"{key}.bin")

        # 检查是否压缩
        is_compressed = metadata.get("compressed", False)
        if is_compressed:
            compression = metadata.get("compression", "")
            # 常见压缩扩展名映射
            ext_map = {
                "blosc2": ".blosc2",
                "lz4": ".lz4",
                "zstd": ".zst",
                "gzip": ".gz",
            }
            ext = ext_map.get(compression, f".{compression}")
            file_path = bin_path + ext
            size_bytes = metadata.get("compressed_size", 0)
        else:
            file_path = bin_path
            # 计算大小
            count = metadata.get("count", 0)
            itemsize = metadata.get("itemsize", 0)
            shape = metadata.get("shape", (count,))
            if count and itemsize:
                import numpy as np

                size_bytes = int(np.prod(shape)) * itemsize
            else:
                size_bytes = 0

        # 如果元数据中有大小信息，优先使用
        if "original_size" in metadata and not is_compressed:
            size_bytes = metadata["original_size"]

        # 尝试从实际文件获取大小
        if os.path.exists(file_path):
            try:
                size_bytes = os.path.getsize(file_path)
            except OSError:
                pass

        return file_path, size_bytes

    def _extract_plugin_version(self, data_name: str, metadata: Dict[str, Any]) -> str:
        """提取插件版本号"""
        # 首先尝试从 metadata 中获取
        if "plugin_version" in metadata:
            return str(metadata["plugin_version"])

        # 尝试从 lineage 中获取
        lineage = metadata.get("lineage", {})
        if isinstance(lineage, dict):
            version = lineage.get("version")
            if version is not None:
                return str(version)

        # 尝试从已注册的插件获取
        if hasattr(self.ctx, "_plugins") and data_name in self.ctx._plugins:
            plugin = self.ctx._plugins[data_name]
            if hasattr(plugin, "version"):
                return str(plugin.version)

        return "unknown"

    def get_entries(
        self,
        run_id: Optional[str] = None,
        data_name: Optional[str] = None,
        min_size: Optional[int] = None,
        max_size: Optional[int] = None,
        min_age_days: Optional[float] = None,
        max_age_days: Optional[float] = None,
        compressed_only: Optional[bool] = None,
    ) -> List[CacheEntry]:
        """获取缓存条目，支持多种过滤条件

        Args:
            run_id: 按 run_id 过滤
            data_name: 按数据类型过滤
            min_size: 最小大小（字节）
            max_size: 最大大小（字节）
            min_age_days: 最小年龄（天）
            max_age_days: 最大年龄（天）
            compressed_only: 仅返回压缩/未压缩的条目

        Returns:
            符合条件的 CacheEntry 列表
        """
        with self._lock:
            # 确定要搜索的 run
            if run_id is not None:
                if run_id in self._cache_index:
                    all_entries = self._cache_index[run_id]
                else:
                    return []
            else:
                all_entries = [e for entries in self._cache_index.values() for e in entries]

            # 应用过滤条件
            result = []
            current_time = time.time()

            for entry in all_entries:
                # data_name 过滤
                if data_name is not None and entry.data_name != data_name:
                    continue

                # 大小过滤
                if min_size is not None and entry.size_bytes < min_size:
                    continue
                if max_size is not None and entry.size_bytes > max_size:
                    continue

                # 年龄过滤
                age_days = (current_time - entry.created_at) / (24 * 3600)
                if min_age_days is not None and age_days < min_age_days:
                    continue
                if max_age_days is not None and age_days > max_age_days:
                    continue

                # 压缩过滤
                if compressed_only is not None and entry.compressed != compressed_only:
                    continue

                result.append(entry)

            return result

    def get_total_size(self, run_id: Optional[str] = None) -> int:
        """获取总缓存大小

        Args:
            run_id: 如果指定，只计算该 run 的大小

        Returns:
            总大小（字节）
        """
        entries = self.get_entries(run_id=run_id)
        return sum(e.size_bytes for e in entries)

    def get_run_summary(self, run_id: str) -> Dict[str, Any]:
        """获取单个 run 的缓存摘要

        Args:
            run_id: 运行标识符

        Returns:
            包含统计信息的字典
        """
        entries = self.get_entries(run_id=run_id)

        if not entries:
            return {
                "run_id": run_id,
                "total_entries": 0,
                "total_size_bytes": 0,
                "total_size_human": "0 B",
                "data_types": [],
                "compressed_count": 0,
                "oldest_entry": None,
                "newest_entry": None,
            }

        total_size = sum(e.size_bytes for e in entries)
        compressed_count = sum(1 for e in entries if e.compressed)
        data_types = list(set(e.data_name for e in entries))

        oldest = min(entries, key=lambda e: e.created_at)
        newest = max(entries, key=lambda e: e.created_at)

        return {
            "run_id": run_id,
            "total_entries": len(entries),
            "total_size_bytes": total_size,
            "total_size_human": self._format_size(total_size),
            "data_types": sorted(data_types),
            "compressed_count": compressed_count,
            "oldest_entry": oldest,
            "newest_entry": newest,
        }

    def get_all_runs(self) -> List[str]:
        """获取所有已扫描的 run_id"""
        with self._lock:
            return sorted(self._cache_index.keys())

    def get_data_type_summary(self) -> Dict[str, Dict[str, Any]]:
        """按数据类型汇总缓存信息

        Returns:
            data_name -> {count, total_size, runs} 的映射
        """
        summary = {}
        entries = self.get_entries()

        for entry in entries:
            if entry.data_name not in summary:
                summary[entry.data_name] = {
                    "count": 0,
                    "total_size_bytes": 0,
                    "runs": set(),
                    "versions": set(),
                }

            summary[entry.data_name]["count"] += 1
            summary[entry.data_name]["total_size_bytes"] += entry.size_bytes
            summary[entry.data_name]["runs"].add(entry.run_id)
            summary[entry.data_name]["versions"].add(entry.plugin_version)

        # 转换 set 为 list 以便序列化
        for data_name in summary:
            summary[data_name]["runs"] = sorted(summary[data_name]["runs"])
            summary[data_name]["versions"] = sorted(summary[data_name]["versions"])
            summary[data_name]["total_size_human"] = self._format_size(summary[data_name]["total_size_bytes"])

        return summary

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        """格式化大小为人类可读字符串"""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"

    def print_summary(self, detailed: bool = False):
        """打印缓存摘要信息

        Args:
            detailed: 是否显示详细信息
        """
        entries = self.get_entries()

        if not entries:
            print("[CacheAnalyzer] 没有找到缓存数据")
            return

        total_size = sum(e.size_bytes for e in entries)
        compressed_count = sum(1 for e in entries if e.compressed)
        runs = self.get_all_runs()

        print("\n" + "=" * 60)
        print("缓存摘要")
        print("=" * 60)
        print(f"  运行数量: {len(runs)}")
        print(f"  缓存条目: {len(entries)}")
        print(f"  总大小: {self._format_size(total_size)}")
        print(f"  压缩条目: {compressed_count} ({100 * compressed_count / len(entries):.1f}%)")

        if detailed:
            print("\n按数据类型统计:")
            print("-" * 60)
            type_summary = self.get_data_type_summary()
            for data_name, info in sorted(type_summary.items()):
                print(f"  {data_name}:")
                print(f"    条目数: {info['count']}")
                print(f"    大小: {info['total_size_human']}")
                print(f"    运行数: {len(info['runs'])}")
                print(f"    版本: {', '.join(info['versions'])}")

            print("\n按运行统计:")
            print("-" * 60)
            for run_id in runs:
                summary = self.get_run_summary(run_id)
                print(f"  {run_id}: {summary['total_entries']} 条目, {summary['total_size_human']}")

        print("=" * 60)
