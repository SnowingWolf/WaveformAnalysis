"""
缓存清理模块 - 智能清理策略。

提供多种清理策略，支持按年龄、大小、版本等条件清理缓存。

"""

from dataclasses import dataclass
from enum import Enum
import time
from typing import Any, Dict, List, Optional

from ..foundation.utils import exporter
from .cache_analyzer import CacheAnalyzer, CacheEntry

export, __all__ = exporter()


@export
class CleanupStrategy(Enum):
    """清理策略枚举"""

    LRU = "lru"  # 最近最少使用（按创建时间）
    OLDEST = "oldest"  # 最旧的
    LARGEST = "largest"  # 最大的
    VERSION_MISMATCH = "version"  # 版本不匹配的
    FAILED_INTEGRITY = "integrity"  # 完整性检查失败的
    BY_RUN = "by_run"  # 按运行清理
    BY_DATA_TYPE = "by_data_type"  # 按数据类型清理


@export
@dataclass
class CleanupPlan:
    """清理计划数据类

    Attributes:
        strategy: 使用的清理策略
        entries_to_delete: 要删除的缓存条目列表
        total_size_to_free: 将释放的总空间（字节）
        affected_runs: 受影响的运行列表
        reason: 清理原因描述
    """

    strategy: CleanupStrategy
    entries_to_delete: List[CacheEntry]
    total_size_to_free: int
    affected_runs: List[str]
    reason: str = ""

    @property
    def entry_count(self) -> int:
        """要删除的条目数"""
        return len(self.entries_to_delete)

    @property
    def size_to_free_human(self) -> str:
        """人类可读的释放空间大小"""
        return CacheCleaner._format_size(self.total_size_to_free)


@export
class CacheCleaner:
    """缓存清理器

    提供多种清理策略，支持按年龄、大小、版本等条件清理缓存。

    Features:
        - 多种清理策略（LRU、最大、最旧等）
        - 清理计划预览
        - dry-run 模式
        - 按 run 或数据类型清理

    Examples:
        >>> analyzer = CacheAnalyzer(ctx)
        >>> analyzer.scan()
        >>>
        >>> cleaner = CacheCleaner(analyzer)
        >>>
        >>> # 创建清理计划
        >>> cleaner.plan_cleanup(
        ...     strategy=CleanupStrategy.LRU,
        ...     target_size_mb=1024
        ... ).preview_plan()
        >>>
        >>> # 执行清理
        >>> result = cleaner.execute(dry_run=False)
    """

    def __init__(self, analyzer: CacheAnalyzer):
        """初始化 CacheCleaner

        Args:
            analyzer: CacheAnalyzer 实例（需要已完成扫描）
        """
        self.analyzer = analyzer
        self.ctx = analyzer.ctx
        self._plan: Optional[CleanupPlan] = None

    @property
    def storage(self):
        """获取存储实例"""
        return self.ctx.storage

    @property
    def plan(self) -> CleanupPlan:
        """获取当前清理计划"""
        if self._plan is None:
            raise ValueError("未设置清理计划，请先调用 plan_cleanup()。")
        return self._plan

    def plan_cleanup(
        self,
        strategy: CleanupStrategy = CleanupStrategy.LRU,
        target_size_mb: Optional[float] = None,
        keep_recent_days: Optional[float] = None,
        run_id: Optional[str] = None,
        data_name: Optional[str] = None,
        max_entries: Optional[int] = None,
    ) -> "CacheCleaner":
        """创建清理计划

        Args:
            strategy: 清理策略
            target_size_mb: 目标释放空间（MB），与 max_entries 二选一
            keep_recent_days: 保留最近 N 天的数据
            run_id: 仅清理指定 run
            data_name: 仅清理指定数据类型
            max_entries: 最多删除的条目数

        Returns:
            CacheCleaner（便于链式调用）
        """
        # 获取候选条目
        entries = self.analyzer.get_entries(run_id=run_id, data_name=data_name)

        if not entries:
            self._plan = CleanupPlan(
                strategy=strategy,
                entries_to_delete=[],
                total_size_to_free=0,
                affected_runs=[],
                reason="没有找到匹配的缓存条目",
            )
            return self

        # 按保留天数过滤
        if keep_recent_days is not None:
            cutoff_time = time.time() - (keep_recent_days * 24 * 3600)
            entries = [e for e in entries if e.created_at < cutoff_time]

        # 根据策略排序
        if strategy == CleanupStrategy.LRU:
            entries.sort(key=lambda e: e.created_at)
            reason = "按最早创建时间排序"
        elif strategy == CleanupStrategy.OLDEST:
            entries.sort(key=lambda e: e.created_at)
            reason = "按最旧的优先"
        elif strategy == CleanupStrategy.LARGEST:
            entries.sort(key=lambda e: e.size_bytes, reverse=True)
            reason = "按最大文件优先"
        elif strategy == CleanupStrategy.VERSION_MISMATCH:
            entries = self._filter_version_mismatch(entries)
            reason = "清理版本不匹配的缓存"
        elif strategy == CleanupStrategy.FAILED_INTEGRITY:
            entries = self._filter_failed_integrity(entries)
            reason = "清理完整性检查失败的缓存"
        elif strategy == CleanupStrategy.BY_RUN:
            reason = f"按运行清理: {run_id}" if run_id else "清理所有运行"
        elif strategy == CleanupStrategy.BY_DATA_TYPE:
            reason = f"按数据类型清理: {data_name}" if data_name else "清理所有数据类型"
        else:
            reason = "未指定策略"

        # 选择要删除的条目
        to_delete = []
        total_size = 0
        target_bytes = (target_size_mb * 1024 * 1024) if target_size_mb else float("inf")

        for entry in entries:
            if max_entries is not None and len(to_delete) >= max_entries:
                break
            if target_size_mb is not None and total_size >= target_bytes:
                break

            to_delete.append(entry)
            total_size += entry.size_bytes

        affected_runs = sorted({e.run_id for e in to_delete})

        self._plan = CleanupPlan(
            strategy=strategy,
            entries_to_delete=to_delete,
            total_size_to_free=total_size,
            affected_runs=affected_runs,
            reason=reason,
        )
        return self

    def _filter_version_mismatch(self, entries: List[CacheEntry]) -> List[CacheEntry]:
        """过滤版本不匹配的条目"""
        result = []
        for entry in entries:
            if not hasattr(self.ctx, "_plugins") or entry.data_name not in self.ctx._plugins:
                continue

            plugin = self.ctx._plugins[entry.data_name]
            current_version = str(getattr(plugin, "version", "unknown"))

            if entry.plugin_version != current_version and entry.plugin_version != "unknown":
                result.append(entry)

        return result

    def _filter_failed_integrity(self, entries: List[CacheEntry]) -> List[CacheEntry]:
        """过滤完整性检查失败的条目"""
        import os

        result = []

        for entry in entries:
            # 检查文件是否存在
            if not os.path.exists(entry.file_path):
                result.append(entry)
                continue

            # 检查文件大小
            if not entry.compressed:
                try:
                    actual_size = os.path.getsize(entry.file_path)
                    if entry.size_bytes > 0 and actual_size != entry.size_bytes:
                        result.append(entry)
                except OSError:
                    result.append(entry)

        return result

    def _resolve_plan(self, plan: Optional[CleanupPlan]) -> CleanupPlan:
        if plan is not None:
            self._plan = plan
        if self._plan is None:
            raise ValueError("未设置清理计划，请先调用 plan_cleanup() 或传入 plan。")
        return self._plan

    def preview_plan(self, plan: Optional[CleanupPlan] = None, detailed: bool = False):
        """预览清理计划

        Args:
            plan: 清理计划（None 则使用最近一次 plan_cleanup 的结果）
            detailed: 是否显示详细信息
        """
        plan = self._resolve_plan(plan)
        print("\n" + "=" * 60)
        print("清理计划预览")
        print("=" * 60)

        print(f"\n策略: {plan.strategy.value}")
        print(f"原因: {plan.reason}")
        print(f"将删除: {plan.entry_count} 个缓存条目")
        print(f"释放空间: {plan.size_to_free_human}")
        print(f"受影响的运行: {len(plan.affected_runs)}")

        if detailed and plan.entries_to_delete:
            print("\n" + "-" * 60)
            print("详细列表:")

            # 按 run_id 分组
            by_run: Dict[str, List[CacheEntry]] = {}
            for entry in plan.entries_to_delete:
                if entry.run_id not in by_run:
                    by_run[entry.run_id] = []
                by_run[entry.run_id].append(entry)

            for run_id in sorted(by_run.keys()):
                run_entries = by_run[run_id]
                run_size = sum(e.size_bytes for e in run_entries)
                print(f"\n  {run_id} ({len(run_entries)} 条目, {self._format_size(run_size)})")

                for entry in sorted(run_entries, key=lambda e: e.data_name):
                    print(
                        f"    • {entry.data_name}: {entry.size_human}, 创建于 {entry.created_at_str}"
                    )

        print("\n" + "=" * 60)

    def execute(self, plan: Optional[CleanupPlan] = None, dry_run: bool = True) -> Dict[str, Any]:
        """执行清理计划

        Args:
            plan: 清理计划（None 则使用最近一次 plan_cleanup 的结果）
            dry_run: 如果为 True，只报告将要执行的操作

        Returns:
            执行结果统计
        """
        plan = self._resolve_plan(plan)
        result = {
            "dry_run": dry_run,
            "strategy": plan.strategy.value,
            "total_entries": plan.entry_count,
            "deleted": 0,
            "failed": 0,
            "freed_bytes": 0,
            "errors": [],
        }

        if not plan.entries_to_delete:
            print("[CacheCleaner] 没有需要清理的条目")
            return result

        if dry_run:
            print(f"\n[Dry-Run] 将删除 {plan.entry_count} 个条目, 释放 {plan.size_to_free_human}")
        else:
            print(f"\n[CacheCleaner] 开始清理 {plan.entry_count} 个条目...")

        for entry in plan.entries_to_delete:
            try:
                if dry_run:
                    print(f"  [would delete] {entry.key} ({entry.size_human})")
                else:
                    self.storage.delete(entry.key, entry.run_id)
                    print(f"  [deleted] {entry.key} ({entry.size_human})")

                result["deleted"] += 1
                result["freed_bytes"] += entry.size_bytes

            except Exception as e:
                result["failed"] += 1
                result["errors"].append({"key": entry.key, "error": str(e)})
                print(f"  [error] {entry.key}: {e}")

        result["freed_human"] = self._format_size(result["freed_bytes"])

        if dry_run:
            print("\n[Dry-Run] 完成。实际执行请设置 dry_run=False")
        else:
            print(
                f"\n[CacheCleaner] 清理完成: "
                f"删除 {result['deleted']}, 失败 {result['failed']}, "
                f"释放 {result['freed_human']}"
            )

        return result

    def cleanup_by_age(
        self, max_age_days: float, run_id: Optional[str] = None, dry_run: bool = True
    ) -> Dict[str, Any]:
        """按年龄清理缓存

        删除超过指定天数的缓存。

        Args:
            max_age_days: 最大保留天数
            run_id: 仅清理指定 run
            dry_run: 是否为演练模式

        Returns:
            执行结果统计
        """
        self.plan_cleanup(
            strategy=CleanupStrategy.OLDEST, keep_recent_days=max_age_days, run_id=run_id
        )

        # 实际上我们需要反转逻辑：删除早于 cutoff 的
        # plan_cleanup 已经在 keep_recent_days 中做了过滤
        return self.execute(dry_run=dry_run)

    def cleanup_to_target_size(
        self,
        target_total_mb: float,
        strategy: CleanupStrategy = CleanupStrategy.LRU,
        run_id: Optional[str] = None,
        dry_run: bool = True,
    ) -> Dict[str, Any]:
        """清理到目标总大小

        删除缓存直到总大小低于目标值。

        Args:
            target_total_mb: 目标总大小（MB）
            strategy: 清理策略
            run_id: 仅清理指定 run
            dry_run: 是否为演练模式

        Returns:
            执行结果统计
        """
        current_size = self.analyzer.get_total_size(run_id=run_id)
        target_bytes = target_total_mb * 1024 * 1024

        if current_size <= target_bytes:
            print(
                f"[CacheCleaner] 当前大小 {self._format_size(current_size)} 已低于目标 {target_total_mb:.1f} MB"
            )
            return {
                "dry_run": dry_run,
                "strategy": strategy.value,
                "total_entries": 0,
                "deleted": 0,
                "failed": 0,
                "freed_bytes": 0,
            }

        size_to_free_mb = (current_size - target_bytes) / (1024 * 1024)

        self.plan_cleanup(strategy=strategy, target_size_mb=size_to_free_mb, run_id=run_id)

        return self.execute(dry_run=dry_run)

    def cleanup_run(
        self, run_id: str, data_names: Optional[List[str]] = None, dry_run: bool = True
    ) -> Dict[str, Any]:
        """清理指定运行的缓存

        Args:
            run_id: 运行标识符
            data_names: 要清理的数据类型列表，None 则清理所有
            dry_run: 是否为演练模式

        Returns:
            执行结果统计
        """
        if data_names:
            entries = []
            for data_name in data_names:
                entries.extend(self.analyzer.get_entries(run_id=run_id, data_name=data_name))
        else:
            entries = self.analyzer.get_entries(run_id=run_id)

        plan = CleanupPlan(
            strategy=CleanupStrategy.BY_RUN,
            entries_to_delete=entries,
            total_size_to_free=sum(e.size_bytes for e in entries),
            affected_runs=[run_id],
            reason=f"清理运行 {run_id} 的缓存",
        )

        return self.execute(plan, dry_run=dry_run)

    def cleanup_data_type(
        self, data_name: str, run_ids: Optional[List[str]] = None, dry_run: bool = True
    ) -> Dict[str, Any]:
        """清理指定数据类型的缓存

        Args:
            data_name: 数据类型名称
            run_ids: 要清理的运行列表，None 则清理所有
            dry_run: 是否为演练模式

        Returns:
            执行结果统计
        """
        if run_ids:
            entries = []
            for run_id in run_ids:
                entries.extend(self.analyzer.get_entries(run_id=run_id, data_name=data_name))
        else:
            entries = self.analyzer.get_entries(data_name=data_name)

        affected_runs = sorted({e.run_id for e in entries})

        plan = CleanupPlan(
            strategy=CleanupStrategy.BY_DATA_TYPE,
            entries_to_delete=entries,
            total_size_to_free=sum(e.size_bytes for e in entries),
            affected_runs=affected_runs,
            reason=f"清理数据类型 {data_name} 的缓存",
        )

        return self.execute(plan, dry_run=dry_run)

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
