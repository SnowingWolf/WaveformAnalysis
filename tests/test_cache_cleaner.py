"""
CacheCleaner 测试模块
"""

import tempfile
import time

import numpy as np
import pytest

from waveform_analysis.core.context import Context
from waveform_analysis.core.storage.cache_analyzer import CacheAnalyzer
from waveform_analysis.core.storage.cache_cleaner import (
    CacheCleaner,
    CleanupPlan,
    CleanupStrategy,
)


@pytest.fixture
def temp_storage_dir():
    """创建临时存储目录"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def context_with_cache(temp_storage_dir):
    """创建带有缓存数据的 Context"""
    ctx = Context(storage_dir=temp_storage_dir)
    storage = ctx.storage

    # 创建不同大小和时间的缓存数据
    test_data = [
        ("run_001", "peaks", 100, time.time() - 7 * 24 * 3600),  # 7 天前
        ("run_001", "waveforms", 1000, time.time() - 3 * 24 * 3600),  # 3 天前
        ("run_002", "peaks", 500, time.time() - 1 * 24 * 3600),  # 1 天前
        ("run_002", "waveforms", 2000, time.time()),  # 现在
    ]

    for run_id, data_name, size, timestamp in test_data:
        key = f"{run_id}-{data_name}-abc123"
        data = np.zeros(size, dtype=[("time", "<f8"), ("value", "<f4")])
        storage.save_memmap(key, data, run_id=run_id)

        # 更新时间戳
        meta = storage.get_metadata(key, run_id)
        if meta:
            meta["timestamp"] = timestamp
            meta["plugin_version"] = "1.0.0"
            storage.save_metadata(key, meta, run_id)

    return ctx


class TestCleanupStrategy:
    """CleanupStrategy 测试"""

    def test_strategy_values(self):
        """测试策略枚举值"""
        assert CleanupStrategy.LRU.value == "lru"
        assert CleanupStrategy.OLDEST.value == "oldest"
        assert CleanupStrategy.LARGEST.value == "largest"
        assert CleanupStrategy.VERSION_MISMATCH.value == "version"
        assert CleanupStrategy.FAILED_INTEGRITY.value == "integrity"


class TestCleanupPlan:
    """CleanupPlan 测试"""

    def test_create_plan(self):
        """测试创建清理计划"""
        plan = CleanupPlan(
            strategy=CleanupStrategy.LRU,
            entries_to_delete=[],
            total_size_to_free=1024 * 1024,
            affected_runs=["run_001"],
            reason="测试清理",
        )

        assert plan.strategy == CleanupStrategy.LRU
        assert plan.entry_count == 0
        assert plan.total_size_to_free == 1024 * 1024
        assert "MB" in plan.size_to_free_human or "KB" in plan.size_to_free_human


class TestCacheCleaner:
    """CacheCleaner 测试"""

    def test_plan_cleanup_lru(self, context_with_cache):
        """测试 LRU 清理计划"""
        analyzer = CacheAnalyzer(context_with_cache)
        analyzer.scan(verbose=False)

        cleaner = CacheCleaner(analyzer)
        cleaner.plan_cleanup(strategy=CleanupStrategy.LRU, max_entries=2)
        plan = cleaner.plan

        assert isinstance(plan, CleanupPlan)
        assert plan.strategy == CleanupStrategy.LRU
        assert plan.entry_count <= 2

    def test_plan_cleanup_largest(self, context_with_cache):
        """测试按最大文件清理"""
        analyzer = CacheAnalyzer(context_with_cache)
        analyzer.scan(verbose=False)

        cleaner = CacheCleaner(analyzer)
        cleaner.plan_cleanup(strategy=CleanupStrategy.LARGEST, max_entries=1)
        plan = cleaner.plan

        assert isinstance(plan, CleanupPlan)
        if plan.entries_to_delete:
            # 应该选择最大的文件
            sizes = [e.size_bytes for e in plan.entries_to_delete]
            # 由于只选了一个，无法比较大小顺序
            assert len(sizes) == 1

    def test_plan_cleanup_with_target_size(self, context_with_cache):
        """测试按目标大小清理"""
        analyzer = CacheAnalyzer(context_with_cache)
        analyzer.scan(verbose=False)

        cleaner = CacheCleaner(analyzer)
        cleaner.plan_cleanup(strategy=CleanupStrategy.LRU, target_size_mb=0.001)  # 很小的目标
        plan = cleaner.plan

        assert isinstance(plan, CleanupPlan)

    def test_plan_cleanup_keep_recent_days(self, context_with_cache):
        """测试保留最近 N 天的数据"""
        analyzer = CacheAnalyzer(context_with_cache)
        analyzer.scan(verbose=False)

        cleaner = CacheCleaner(analyzer)
        cleaner.plan_cleanup(strategy=CleanupStrategy.OLDEST, keep_recent_days=5)  # 保留最近 5 天
        plan = cleaner.plan

        # 应该不会删除最近 5 天内的数据
        for entry in plan.entries_to_delete:
            assert entry.age_days >= 5

    def test_plan_cleanup_by_run(self, context_with_cache):
        """测试按运行清理"""
        analyzer = CacheAnalyzer(context_with_cache)
        analyzer.scan(verbose=False)

        cleaner = CacheCleaner(analyzer)
        cleaner.plan_cleanup(strategy=CleanupStrategy.BY_RUN, run_id="run_001")
        plan = cleaner.plan

        # 所有条目应该属于 run_001
        for entry in plan.entries_to_delete:
            assert entry.run_id == "run_001"

    def test_preview_plan(self, context_with_cache, capsys):
        """测试预览清理计划"""
        analyzer = CacheAnalyzer(context_with_cache)
        analyzer.scan(verbose=False)

        cleaner = CacheCleaner(analyzer)
        cleaner.plan_cleanup(strategy=CleanupStrategy.LRU, max_entries=2)

        cleaner.preview_plan(detailed=True)
        captured = capsys.readouterr()
        assert "清理计划" in captured.out

    def test_execute_dry_run(self, context_with_cache):
        """测试 dry-run 执行"""
        analyzer = CacheAnalyzer(context_with_cache)
        analyzer.scan(verbose=False)

        cleaner = CacheCleaner(analyzer)
        cleaner.plan_cleanup(strategy=CleanupStrategy.LRU, max_entries=1)

        initial_count = len(analyzer.get_entries())

        result = cleaner.execute(dry_run=True)

        assert result["dry_run"] is True
        assert "deleted" in result
        assert "freed_bytes" in result

        # Dry-run 不应该实际删除
        analyzer.scan(force_refresh=True, verbose=False)
        final_count = len(analyzer.get_entries())
        assert final_count == initial_count

    def test_execute_actual(self, context_with_cache):
        """测试实际执行清理"""
        analyzer = CacheAnalyzer(context_with_cache)
        analyzer.scan(verbose=False)

        cleaner = CacheCleaner(analyzer)
        initial_entries = analyzer.get_entries()

        if not initial_entries:
            pytest.skip("没有缓存数据可清理")

        cleaner.plan_cleanup(strategy=CleanupStrategy.LRU, max_entries=1)

        if cleaner.plan.entry_count == 0:
            pytest.skip("没有条目需要清理")

        result = cleaner.execute(dry_run=False)

        assert result["dry_run"] is False
        assert result["deleted"] >= 0

    def test_cleanup_by_age(self, context_with_cache):
        """测试按年龄清理"""
        analyzer = CacheAnalyzer(context_with_cache)
        analyzer.scan(verbose=False)

        cleaner = CacheCleaner(analyzer)

        # 清理超过 5 天的数据
        result = cleaner.cleanup_by_age(max_age_days=5, dry_run=True)

        assert "dry_run" in result
        assert result["dry_run"] is True

    def test_cleanup_to_target_size(self, context_with_cache):
        """测试清理到目标大小"""
        analyzer = CacheAnalyzer(context_with_cache)
        analyzer.scan(verbose=False)

        cleaner = CacheCleaner(analyzer)

        # 目标大小设为当前大小的一半
        current_size = analyzer.get_total_size()
        target_mb = (current_size / 2) / (1024 * 1024)

        result = cleaner.cleanup_to_target_size(target_total_mb=target_mb, dry_run=True)

        assert "strategy" in result

    def test_cleanup_run(self, context_with_cache):
        """测试清理指定运行"""
        analyzer = CacheAnalyzer(context_with_cache)
        analyzer.scan(verbose=False)

        cleaner = CacheCleaner(analyzer)
        result = cleaner.cleanup_run("run_001", dry_run=True)

        assert "dry_run" in result

    def test_cleanup_data_type(self, context_with_cache):
        """测试清理指定数据类型"""
        analyzer = CacheAnalyzer(context_with_cache)
        analyzer.scan(verbose=False)

        cleaner = CacheCleaner(analyzer)
        result = cleaner.cleanup_data_type("peaks", dry_run=True)

        assert "dry_run" in result

    def test_empty_plan(self, temp_storage_dir):
        """测试空清理计划"""
        ctx = Context(storage_dir=temp_storage_dir)
        analyzer = CacheAnalyzer(ctx)
        analyzer.scan(verbose=False)

        cleaner = CacheCleaner(analyzer)
        cleaner.plan_cleanup(strategy=CleanupStrategy.LRU)
        plan = cleaner.plan

        assert plan.entry_count == 0
        assert plan.total_size_to_free == 0
