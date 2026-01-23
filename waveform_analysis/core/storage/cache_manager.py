# -*- coding: utf-8 -*-
"""
运行时缓存管理模块 - 提供统一的缓存检查和加载接口。

从 Context 中提取，统一管理内存缓存和磁盘缓存的检查逻辑。

注意：本模块的 RuntimeCacheManager 与 cache.py 中的 CacheManager 职责不同：
- RuntimeCacheManager: Context 运行时缓存管理（内存 + 磁盘缓存检查）
- CacheManager (cache.py): 步骤级缓存管理（签名计算、数据序列化）
"""

# 1. Standard library imports
from typing import TYPE_CHECKING, Any, Optional, Tuple

# 2. Third-party imports
# None
# 3. Local imports
from ..foundation.utils import exporter

if TYPE_CHECKING:
    from ..context import Context

export, __all__ = exporter()


@export
class RuntimeCacheManager:
    """运行时缓存管理器

    统一管理 Context 执行过程中的内存缓存和磁盘缓存的检查、加载和统计记录。

    职责：
    - 检查内存缓存
    - 检查磁盘缓存
    - 统一的缓存命中接口
    - 集成统计收集

    Examples:
        >>> cache_manager = RuntimeCacheManager(ctx)
        >>>
        >>> # 检查缓存
        >>> data, cache_hit = cache_manager.check_cache(
        ...     'run_001', 'st_waveforms', 'key_hash'
        ... )
        >>>
        >>> if cache_hit:
        ...     print(f"缓存命中，数据大小: {len(data)}")
        ... else:
        ...     print("缓存未命中，需要计算")
    """

    def __init__(self, context: 'Context'):
        """初始化 RuntimeCacheManager

        Args:
            context: Context 实例，用于访问缓存数据和统计收集器
        """
        self.ctx = context

    def check_memory_cache(self, run_id: str, name: str) -> Optional[Any]:
        """检查内存缓存

        Args:
            run_id: 运行标识符
            name: 数据名称

        Returns:
            缓存的数据，如果未命中返回 None
        """
        return self.ctx._get_data_from_memory(run_id, name)

    def check_disk_cache(self, run_id: str, name: str, key: str) -> Optional[Any]:
        """检查磁盘缓存

        Args:
            run_id: 运行标识符
            name: 数据名称
            key: 缓存键

        Returns:
            缓存的数据，如果未命中返回 None
        """
        with self.ctx.profiler.timeit("context.load_cache"):
            return self.ctx._load_from_disk_with_check(run_id, name, key)

    def check_cache(
        self,
        run_id: str,
        name: str,
        key: str
    ) -> Tuple[Optional[Any], bool]:
        """统一的缓存检查接口

        按顺序检查内存缓存和磁盘缓存，并记录统计信息。

        Args:
            run_id: 运行标识符
            name: 数据名称
            key: 缓存键

        Returns:
            元组 (data, cache_hit):
            - data: 缓存的数据，未命中时为 None
            - cache_hit: 是否命中缓存
        """
        # 1. 检查内存缓存
        mem_cached = self.check_memory_cache(run_id, name)
        if mem_cached is not None:
            # 内存缓存命中 - 记录统计
            self._record_cache_hit_stats(name, run_id)
            return mem_cached, True

        # 2. 检查磁盘缓存
        disk_cached = self.check_disk_cache(run_id, name, key)
        if disk_cached is not None:
            # 磁盘缓存命中 - 记录统计
            self._record_cache_hit_stats(name, run_id)
            return disk_cached, True

        # 3. 缓存未命中
        return None, False

    def _record_cache_hit_stats(self, name: str, run_id: str) -> None:
        """记录缓存命中的统计信息

        Args:
            name: 插件名称
            run_id: 运行标识符
        """
        if self.ctx.stats_collector and self.ctx.stats_collector.is_enabled():
            self.ctx.stats_collector.start_execution(name, run_id)
            self.ctx.stats_collector.end_execution(name, success=True, cache_hit=True)
