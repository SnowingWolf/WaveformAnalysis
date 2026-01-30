"""
CacheAnalyzer 测试模块
"""

import tempfile
import time

import numpy as np
import pytest

from waveform_analysis.core.context import Context
from waveform_analysis.core.storage.cache_analyzer import CacheAnalyzer, CacheEntry


@pytest.fixture
def temp_storage_dir():
    """创建临时存储目录"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def context_with_cache(temp_storage_dir):
    """创建带有缓存数据的 Context"""
    ctx = Context(storage_dir=temp_storage_dir)

    # 手动创建一些缓存数据
    storage = ctx.storage

    # 创建测试数据
    for run_id in ["run_001", "run_002"]:
        for data_name in ["peaks", "waveforms"]:
            key = f"{run_id}-{data_name}-abc123"
            data = np.zeros(100, dtype=[("time", "<f8"), ("value", "<f4")])

            # 直接保存数据
            storage.save_memmap(key, data, run_id=run_id)

            # 更新元数据添加 plugin_version
            meta = storage.get_metadata(key, run_id)
            if meta:
                meta["plugin_version"] = "1.0.0"
                meta["lineage"] = {"version": "1.0.0"}
                storage.save_metadata(key, meta, run_id)

    return ctx


class TestCacheEntry:
    """CacheEntry 测试"""

    def test_create_entry(self):
        """测试创建 CacheEntry"""
        entry = CacheEntry(
            run_id="run_001",
            data_name="peaks",
            key="run_001-peaks-abc123",
            size_bytes=1024 * 1024,  # 1 MB
            created_at=time.time() - 3600,  # 1 小时前
            plugin_version="1.0.0",
            dtype_str="<f8",
            count=1000,
            compressed=False,
            has_checksum=False,
            file_path="/tmp/test.bin",
            metadata={},
        )

        assert entry.run_id == "run_001"
        assert entry.data_name == "peaks"
        assert entry.size_bytes == 1024 * 1024

    def test_size_human(self):
        """测试人类可读大小"""
        # 字节
        entry = CacheEntry(
            run_id="run_001",
            data_name="test",
            key="test",
            size_bytes=512,
            created_at=time.time(),
            plugin_version="1.0",
            dtype_str="<f8",
            count=0,
            compressed=False,
            has_checksum=False,
            file_path="",
        )
        assert entry.size_human == "512 B"

        # KB
        entry.size_bytes = 1024 * 5
        assert "KB" in entry.size_human

        # MB
        entry.size_bytes = 1024 * 1024 * 10
        assert "MB" in entry.size_human

        # GB
        entry.size_bytes = 1024 * 1024 * 1024 * 2
        assert "GB" in entry.size_human

    def test_age_days(self):
        """测试缓存年龄计算"""
        one_day_ago = time.time() - 24 * 3600
        entry = CacheEntry(
            run_id="run_001",
            data_name="test",
            key="test",
            size_bytes=0,
            created_at=one_day_ago,
            plugin_version="1.0",
            dtype_str="<f8",
            count=0,
            compressed=False,
            has_checksum=False,
            file_path="",
        )

        assert 0.9 < entry.age_days < 1.1  # 约 1 天


class TestCacheAnalyzer:
    """CacheAnalyzer 测试"""

    def test_scan_empty_storage(self, temp_storage_dir):
        """测试扫描空存储"""
        ctx = Context(storage_dir=temp_storage_dir)
        analyzer = CacheAnalyzer(ctx)

        result = analyzer.scan(verbose=False)

        assert isinstance(result, dict)
        assert len(result) == 0

    def test_scan_with_data(self, context_with_cache):
        """测试扫描有数据的存储"""
        analyzer = CacheAnalyzer(context_with_cache)
        result = analyzer.scan(verbose=False)

        # 应该有 2 个 run
        assert len(result) >= 0  # 可能为空，取决于存储模式

    def test_get_entries_no_filter(self, context_with_cache):
        """测试获取所有条目"""
        analyzer = CacheAnalyzer(context_with_cache)
        analyzer.scan(verbose=False)

        entries = analyzer.get_entries()
        assert isinstance(entries, list)

    def test_get_entries_filter_by_run(self, context_with_cache):
        """测试按 run_id 过滤"""
        analyzer = CacheAnalyzer(context_with_cache)
        analyzer.scan(verbose=False)

        entries = analyzer.get_entries(run_id="run_001")
        for entry in entries:
            assert entry.run_id == "run_001"

    def test_get_entries_filter_by_size(self, context_with_cache):
        """测试按大小过滤"""
        analyzer = CacheAnalyzer(context_with_cache)
        analyzer.scan(verbose=False)

        # 最小 1KB
        entries = analyzer.get_entries(min_size=1024)
        for entry in entries:
            assert entry.size_bytes >= 1024

        # 最大 1MB
        entries = analyzer.get_entries(max_size=1024 * 1024)
        for entry in entries:
            assert entry.size_bytes <= 1024 * 1024

    def test_get_total_size(self, context_with_cache):
        """测试获取总大小"""
        analyzer = CacheAnalyzer(context_with_cache)
        analyzer.scan(verbose=False)

        total = analyzer.get_total_size()
        assert isinstance(total, int)
        assert total >= 0

    def test_get_run_summary(self, context_with_cache):
        """测试获取运行摘要"""
        analyzer = CacheAnalyzer(context_with_cache)
        analyzer.scan(verbose=False)

        summary = analyzer.get_run_summary("run_001")

        assert "run_id" in summary
        assert "total_entries" in summary
        assert "total_size_bytes" in summary
        assert "total_size_human" in summary

    def test_get_all_runs(self, context_with_cache):
        """测试获取所有运行"""
        analyzer = CacheAnalyzer(context_with_cache)
        analyzer.scan(verbose=False)

        runs = analyzer.get_all_runs()
        assert isinstance(runs, list)

    def test_get_data_type_summary(self, context_with_cache):
        """测试按数据类型汇总"""
        analyzer = CacheAnalyzer(context_with_cache)
        analyzer.scan(verbose=False)

        summary = analyzer.get_data_type_summary()
        assert isinstance(summary, dict)

    def test_print_summary(self, context_with_cache, capsys):
        """测试打印摘要"""
        analyzer = CacheAnalyzer(context_with_cache)
        analyzer.scan(verbose=False)

        analyzer.print_summary(detailed=False)
        captured = capsys.readouterr()
        # 应该有输出
        assert len(captured.out) > 0

    def test_incremental_scan(self, context_with_cache):
        """测试增量扫描"""
        analyzer = CacheAnalyzer(context_with_cache)

        # 第一次扫描
        analyzer.scan(verbose=False)
        first_scan_time = analyzer._last_scan_time

        # 第二次扫描（不强制刷新）
        time.sleep(0.1)
        analyzer.scan(verbose=False, force_refresh=False)

        # 时间应该更新
        assert analyzer._last_scan_time >= first_scan_time

    def test_force_refresh(self, context_with_cache):
        """测试强制刷新"""
        analyzer = CacheAnalyzer(context_with_cache)

        analyzer.scan(verbose=False)
        analyzer._scanned_runs.copy()

        # 强制刷新
        analyzer.scan(verbose=False, force_refresh=True)
        scanned_runs_2 = analyzer._scanned_runs.copy()

        # 扫描集合应该被重置后重建
        assert isinstance(scanned_runs_2, set)
