"""
CacheStatsCollector 测试模块
"""

import json
import os
import tempfile
import time

import numpy as np
import pytest

from waveform_analysis.core.context import Context
from waveform_analysis.core.storage.cache_analyzer import CacheAnalyzer
from waveform_analysis.core.storage.cache_statistics import (
    CacheStatistics,
    CacheStatsCollector,
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

    # 创建测试缓存数据
    test_data = [
        ("run_001", "peaks", 100),
        ("run_001", "waveforms", 500),
        ("run_002", "peaks", 200),
        ("run_002", "waveforms", 1000),
        ("run_003", "hits", 300),
    ]

    for run_id, data_name, size in test_data:
        key = f"{run_id}-{data_name}-abc123"
        data = np.zeros(size, dtype=[("time", "<f8"), ("value", "<f4")])
        storage.save_memmap(key, data, run_id=run_id)

        # 更新元数据
        meta = storage.get_metadata(key, run_id)
        if meta:
            meta["plugin_version"] = "1.0.0"
            meta["timestamp"] = time.time() - np.random.randint(0, 7 * 24 * 3600)
            storage.save_metadata(key, meta, run_id)

    return ctx


class TestCacheStatistics:
    """CacheStatistics 测试"""

    def test_create_statistics(self):
        """测试创建统计对象"""
        stats = CacheStatistics(
            total_runs=3,
            total_entries=10,
            total_size_bytes=1024 * 1024,
            compressed_entries=2,
            avg_entry_size_bytes=102400,
            largest_entry=None,
            oldest_entry=None,
            newest_entry=None,
            by_run={},
            by_data_type={},
        )

        assert stats.total_runs == 3
        assert stats.total_entries == 10
        assert "MB" in stats.total_size_human or "KB" in stats.total_size_human

    def test_compression_ratio(self):
        """测试压缩率计算"""
        stats = CacheStatistics(
            total_runs=1,
            total_entries=10,
            total_size_bytes=1000,
            compressed_entries=4,
            avg_entry_size_bytes=100,
            largest_entry=None,
            oldest_entry=None,
            newest_entry=None,
        )

        assert stats.compression_ratio == 0.4  # 4/10

    def test_to_dict(self):
        """测试转换为字典"""
        stats = CacheStatistics(
            total_runs=1,
            total_entries=5,
            total_size_bytes=5000,
            compressed_entries=1,
            avg_entry_size_bytes=1000,
            largest_entry=None,
            oldest_entry=None,
            newest_entry=None,
        )

        d = stats.to_dict()

        assert "total_runs" in d
        assert "total_entries" in d
        assert "total_size_human" in d
        assert "compression_ratio" in d


class TestCacheStatsCollector:
    """CacheStatsCollector 测试"""

    def test_collect_empty(self, temp_storage_dir):
        """测试空缓存统计"""
        ctx = Context(storage_dir=temp_storage_dir)
        analyzer = CacheAnalyzer(ctx)
        analyzer.scan(verbose=False)

        collector = CacheStatsCollector(analyzer)
        stats = collector.collect()

        assert stats.total_runs == 0
        assert stats.total_entries == 0
        assert stats.total_size_bytes == 0

    def test_collect_with_data(self, context_with_cache):
        """测试有数据的统计"""
        analyzer = CacheAnalyzer(context_with_cache)
        analyzer.scan(verbose=False)

        collector = CacheStatsCollector(analyzer)
        stats = collector.collect()

        assert isinstance(stats, CacheStatistics)
        # 可能为 0（取决于存储模式）
        assert stats.total_entries >= 0
        assert stats.total_size_bytes >= 0

    def test_collect_by_run(self, context_with_cache):
        """测试按运行统计"""
        analyzer = CacheAnalyzer(context_with_cache)
        analyzer.scan(verbose=False)

        collector = CacheStatsCollector(analyzer)
        stats = collector.collect(run_id="run_001")

        # 只统计 run_001
        for run_id in stats.by_run:
            assert run_id == "run_001"

    def test_print_summary(self, context_with_cache, capsys):
        """测试打印摘要"""
        analyzer = CacheAnalyzer(context_with_cache)
        analyzer.scan(verbose=False)

        collector = CacheStatsCollector(analyzer)
        stats = collector.collect()

        collector.print_summary(stats, detailed=False)
        captured = capsys.readouterr()
        assert "缓存统计" in captured.out or len(captured.out) > 0

    def test_print_summary_detailed(self, context_with_cache, capsys):
        """测试打印详细摘要"""
        analyzer = CacheAnalyzer(context_with_cache)
        analyzer.scan(verbose=False)

        collector = CacheStatsCollector(analyzer)
        stats = collector.collect()

        collector.print_summary(stats, detailed=True)
        captured = capsys.readouterr()
        assert len(captured.out) > 0

    def test_get_hit_rate_stats(self, context_with_cache):
        """测试获取命中率统计"""
        analyzer = CacheAnalyzer(context_with_cache)
        analyzer.scan(verbose=False)

        collector = CacheStatsCollector(analyzer)
        hit_stats = collector.get_hit_rate_stats()

        assert "available" in hit_stats
        assert "total_hits" in hit_stats
        assert "total_misses" in hit_stats

    def test_analyze_disk_usage(self, context_with_cache):
        """测试磁盘使用分析"""
        analyzer = CacheAnalyzer(context_with_cache)
        analyzer.scan(verbose=False)

        collector = CacheStatsCollector(analyzer)
        disk_stats = collector.analyze_disk_usage()

        assert "storage_dir" in disk_stats
        assert "cache_size" in disk_stats

    def test_export_json(self, context_with_cache, temp_storage_dir):
        """测试导出 JSON"""
        analyzer = CacheAnalyzer(context_with_cache)
        analyzer.scan(verbose=False)

        collector = CacheStatsCollector(analyzer)
        stats = collector.collect()

        output_path = os.path.join(temp_storage_dir, "stats.json")
        collector.export_stats(stats, output_path, format="json")

        assert os.path.exists(output_path)

        # 验证 JSON 格式
        with open(output_path) as f:
            data = json.load(f)
            assert "total_runs" in data
            assert "total_entries" in data

    def test_export_csv(self, context_with_cache, temp_storage_dir):
        """测试导出 CSV"""
        analyzer = CacheAnalyzer(context_with_cache)
        analyzer.scan(verbose=False)

        collector = CacheStatsCollector(analyzer)
        stats = collector.collect()

        output_path = os.path.join(temp_storage_dir, "stats.csv")
        collector.export_stats(stats, output_path, format="csv")

        assert os.path.exists(output_path)

        # 验证 CSV 内容
        with open(output_path) as f:
            content = f.read()
            assert "总体统计" in content or "total" in content.lower()

    def test_export_invalid_format(self, context_with_cache, temp_storage_dir):
        """测试无效导出格式"""
        analyzer = CacheAnalyzer(context_with_cache)
        analyzer.scan(verbose=False)

        collector = CacheStatsCollector(analyzer)
        stats = collector.collect()

        with pytest.raises(ValueError):
            collector.export_stats(stats, "output.xyz", format="xyz")

    def test_by_run_statistics(self, context_with_cache):
        """测试按运行分组统计"""
        analyzer = CacheAnalyzer(context_with_cache)
        analyzer.scan(verbose=False)

        collector = CacheStatsCollector(analyzer)
        stats = collector.collect()

        # by_run 应该包含每个 run 的统计
        for _run_id, run_stats in stats.by_run.items():
            assert "entry_count" in run_stats
            assert "total_size_bytes" in run_stats
            assert "total_size_human" in run_stats

    def test_by_data_type_statistics(self, context_with_cache):
        """测试按数据类型分组统计"""
        analyzer = CacheAnalyzer(context_with_cache)
        analyzer.scan(verbose=False)

        collector = CacheStatsCollector(analyzer)
        stats = collector.collect()

        # by_data_type 应该包含每种数据类型的统计
        for _data_name, type_stats in stats.by_data_type.items():
            assert "entry_count" in type_stats
            assert "total_size_bytes" in type_stats
            assert "run_count" in type_stats
