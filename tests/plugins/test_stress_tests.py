"""压力测试和边界情况测试。

测试覆盖：
1. 大数据集处理
2. 边界情况（空数据、单通道、极端参数）
3. 内存压力测试
4. 循环依赖检测
"""

import gc
import tracemalloc

import numpy as np
import pytest

from tests.utils import DummyContext, make_records
from waveform_analysis.core.plugins.builtin.cpu.hit_merge import (
    HIT_MERGED_DTYPE,
    HitMergedComponentsPlugin,
    HitMergePlugin,
)
from waveform_analysis.core.plugins.builtin.cpu.hit_merged_features import (
    HitMergedFeaturesPlugin,
)
from waveform_analysis.core.plugins.builtin.cpu.peaklets import (
    PeakletComponentsPlugin,
    PeakletPlugin,
)
from waveform_analysis.core.plugins.builtin.hit.hit_finder import THRESHOLD_HIT_DTYPE


def generate_large_dataset(n_records=10000, n_channels=16, hits_per_record=5):
    """生成大规模测试数据集"""
    total_hits = n_records * hits_per_record
    hits = np.zeros(total_hits, dtype=THRESHOLD_HIT_DTYPE)

    for i in range(total_hits):
        record_id = i // hits_per_record
        channel = record_id % n_channels
        timestamp = record_id * 1000 + (i % hits_per_record) * 100

        hits[i]["record_id"] = record_id
        hits[i]["board"] = 0
        hits[i]["channel"] = channel
        hits[i]["edge_start"] = 10
        hits[i]["edge_end"] = 20
        hits[i]["position"] = 15
        hits[i]["width"] = 10
        hits[i]["dt"] = 2
        hits[i]["timestamp"] = timestamp

    records = make_records(n_records=n_records, event_length=50, baseline=100.0, dt=2)
    for i in range(n_records):
        records[i]["board"] = 0
        records[i]["channel"] = i % n_channels
        records[i]["timestamp"] = i * 1000
        records[i]["polarity"] = "negative"

    wave_pool = np.random.randint(90, 110, size=n_records * 50, dtype=np.uint16)

    return hits, records, wave_pool


class TestLargeDatasets:
    """测试大数据集处理"""

    @pytest.mark.slow
    def test_hit_merge_large_dataset(self):
        """测试 HitMergePlugin 在大数据集上的表现"""
        hits, _, _ = generate_large_dataset(n_records=10000, n_channels=16)

        ctx = DummyContext(
            {"merge_gap_ns": 50.0, "max_total_width_ns": 10000.0, "dt": 2},
            {"hit_threshold": hits},
        )

        plugin = HitMergePlugin()
        merged = plugin.compute(ctx, "large_run")

        # 验证结果
        assert isinstance(merged, np.ndarray)
        assert merged.dtype == HIT_MERGED_DTYPE
        assert len(merged) > 0
        assert len(merged) <= len(hits)  # merged 应该少于或等于原始 hits

        # 验证数据完整性
        assert np.all(merged["channel"] >= 0)

        # 契约：跨 record 的 cluster 没有唯一 sample 窗口，sample_start/sample_end/width
        # 合法标记为 -1（is_single_record=False），而 time_start/time_end 始终有效。
        single = merged[merged["is_single_record"]]
        assert np.all(single["sample_start"] >= 0)
        assert np.all(single["sample_end"] > single["sample_start"])

        cross = merged[~merged["is_single_record"]]
        assert np.all(cross["sample_start"] == -1)
        assert np.all(cross["sample_end"] == -1)
        assert np.all(cross["time_start"] < cross["time_end"])  # 时间范围仍然有效

    @pytest.mark.slow
    def test_peaklets_large_dataset(self):
        """测试 Peaklets 在大数据集上的表现"""
        hits, records, wave_pool = generate_large_dataset(n_records=5000, n_channels=8)

        # 构建完整流水线
        merge_ctx = DummyContext(
            {"merge_gap_ns": 100.0, "max_total_width_ns": 10000.0, "dt": 2},
            {"hit_threshold": hits},
        )
        merge_plugin = HitMergePlugin()
        merged = merge_plugin.compute(merge_ctx, "large_run")

        ctx = DummyContext(
            {"time_window_ns": 100.0, "max_total_width_ns": 10000.0, "dt": 2},
            {"hit_merged": merged},
        )

        # PeakletPlugin 依赖 peaklet_components，由 PeakletComponentsPlugin 先行产出
        peaklet_components = PeakletComponentsPlugin().compute_array(ctx, "large_run")
        ctx._data["peaklet_components"] = peaklet_components

        plugin = PeakletPlugin()
        peaklets = plugin.compute_array(ctx, "large_run")

        # 验证结果
        assert isinstance(peaklets, np.ndarray)
        assert len(peaklets) > 0
        assert np.all(peaklets["n_hits"] > 0)
        assert np.all(peaklets["n_channels"] > 0)

    @pytest.mark.slow
    def test_features_large_dataset(self):
        """测试 Features 在大数据集上的表现"""
        hits, records, wave_pool = generate_large_dataset(n_records=3000, n_channels=4)

        # 构建数据流
        merge_ctx = DummyContext(
            {"merge_gap_ns": 50.0, "max_total_width_ns": 10000.0, "dt": 2},
            {"hit_threshold": hits},
        )
        merge_plugin = HitMergePlugin()
        merged = merge_plugin.compute(merge_ctx, "large_run")

        comp_ctx = DummyContext(
            {"merge_gap_ns": 50.0, "max_total_width_ns": 10000.0, "dt": 2},
            {"hit_threshold": hits, "hit_merged": merged},
        )
        comp_ctx._plugins = {"hit_merged": merge_plugin}
        comp_ctx.get_plugin = lambda name: comp_ctx._plugins.get(name)
        components = HitMergedComponentsPlugin().compute(comp_ctx, "large_run")

        ctx = DummyContext(
            {"wave_source": "records", "use_filtered": False, "dt": 2},
            {
                "hit_merged": merged,
                "hit_merged_components": components,
                "hit_threshold": hits,
                "records": records,
                "wave_pool": wave_pool,
            },
        )

        plugin = HitMergedFeaturesPlugin()
        features = plugin.compute(ctx, "large_run")

        # 验证结果
        assert isinstance(features, np.ndarray)
        assert len(features) == len(merged)
        assert np.all(features["valid"] == 1)


class TestEdgeCases:
    """测试边界情况"""

    def test_empty_input(self):
        """测试空输入"""
        empty_hits = np.zeros(0, dtype=THRESHOLD_HIT_DTYPE)

        ctx = DummyContext(
            {"merge_gap_ns": 50.0, "max_total_width_ns": 10000.0, "dt": 2},
            {"hit_threshold": empty_hits},
        )

        plugin = HitMergePlugin()
        merged = plugin.compute(ctx, "empty_run")

        assert isinstance(merged, np.ndarray)
        assert len(merged) == 0
        assert merged.dtype == HIT_MERGED_DTYPE

    def test_single_channel_data(self):
        """测试单通道数据"""
        n_hits = 100
        hits = np.zeros(n_hits, dtype=THRESHOLD_HIT_DTYPE)

        for i in range(n_hits):
            hits[i]["record_id"] = i
            hits[i]["board"] = 0
            hits[i]["channel"] = 0  # 所有 hits 都在通道 0
            hits[i]["edge_start"] = 10 + i
            hits[i]["edge_end"] = 20 + i
            hits[i]["position"] = 15 + i
            hits[i]["dt"] = 2
            hits[i]["timestamp"] = i * 100

        ctx = DummyContext(
            {"merge_gap_ns": 50.0, "max_total_width_ns": 10000.0, "dt": 2},
            {"hit_threshold": hits},
        )

        plugin = HitMergePlugin()
        merged = plugin.compute(ctx, "single_channel")

        # 验证结果
        assert len(merged) > 0
        assert np.all(merged["channel"] == 0)

    def test_single_hit(self):
        """测试单个 hit"""
        hit = np.zeros(1, dtype=THRESHOLD_HIT_DTYPE)
        hit[0]["record_id"] = 0
        hit[0]["board"] = 0
        hit[0]["channel"] = 0
        hit[0]["edge_start"] = 10
        hit[0]["edge_end"] = 20
        hit[0]["position"] = 15
        hit[0]["dt"] = 2
        hit[0]["timestamp"] = 1000

        ctx = DummyContext(
            {"merge_gap_ns": 50.0, "max_total_width_ns": 10000.0, "dt": 2},
            {"hit_threshold": hit},
        )

        plugin = HitMergePlugin()
        merged = plugin.compute(ctx, "single_hit")

        assert len(merged) == 1
        assert merged[0]["channel"] == 0

    def test_extreme_time_gaps(self):
        """测试极端时间间隔"""
        hits = np.zeros(3, dtype=THRESHOLD_HIT_DTYPE)

        # 第一个 hit
        hits[0]["record_id"] = 0
        hits[0]["channel"] = 0
        hits[0]["edge_start"] = 10
        hits[0]["edge_end"] = 20
        hits[0]["position"] = 15
        hits[0]["dt"] = 2
        hits[0]["timestamp"] = 1000

        # 第二个 hit（非常接近）
        hits[1]["record_id"] = 1
        hits[1]["channel"] = 0
        hits[1]["edge_start"] = 10
        hits[1]["edge_end"] = 20
        hits[1]["position"] = 15
        hits[1]["dt"] = 2
        hits[1]["timestamp"] = 1010  # 仅 10 ps 间隔

        # 第三个 hit（非常远）
        hits[2]["record_id"] = 2
        hits[2]["channel"] = 0
        hits[2]["edge_start"] = 10
        hits[2]["edge_end"] = 20
        hits[2]["position"] = 15
        hits[2]["dt"] = 2
        hits[2]["timestamp"] = 1000000  # 非常远

        ctx = DummyContext(
            {"merge_gap_ns": 50.0, "max_total_width_ns": 10000.0, "dt": 2},
            {"hit_threshold": hits},
        )

        plugin = HitMergePlugin()
        merged = plugin.compute(ctx, "extreme_gaps")

        # 前两个应该合并，第三个独立
        assert len(merged) == 2

    def test_extreme_parameters(self):
        """测试极端参数值"""
        hits, _, _ = generate_large_dataset(n_records=100, n_channels=2)

        # 测试极小的 merge_gap
        ctx1 = DummyContext(
            {"merge_gap_ns": 0.0, "max_total_width_ns": 10000.0, "dt": 2},
            {"hit_threshold": hits},
        )
        plugin = HitMergePlugin()
        merged1 = plugin.compute(ctx1, "small_gap")
        assert len(merged1) > 0

        # 测试极大的 merge_gap
        ctx2 = DummyContext(
            {"merge_gap_ns": 1000000.0, "max_total_width_ns": 1000000.0, "dt": 2},
            {"hit_threshold": hits},
        )
        merged2 = plugin.compute(ctx2, "large_gap")
        assert len(merged2) > 0
        assert len(merged2) < len(merged1)  # 更大的 gap 应该导致更多合并

    def test_zero_width_hits(self):
        """测试零宽度 hits"""
        hits = np.zeros(2, dtype=THRESHOLD_HIT_DTYPE)

        # 正常 hit
        hits[0]["record_id"] = 0
        hits[0]["channel"] = 0
        hits[0]["edge_start"] = 10
        hits[0]["edge_end"] = 20
        hits[0]["position"] = 15
        hits[0]["dt"] = 2
        hits[0]["timestamp"] = 1000

        # 零宽度 hit（可能是数据错误）
        hits[1]["record_id"] = 1
        hits[1]["channel"] = 0
        hits[1]["edge_start"] = 15
        hits[1]["edge_end"] = 15  # 零宽度
        hits[1]["position"] = 15
        hits[1]["dt"] = 2
        hits[1]["timestamp"] = 2000

        ctx = DummyContext(
            {"merge_gap_ns": 50.0, "max_total_width_ns": 10000.0, "dt": 2},
            {"hit_threshold": hits},
        )

        plugin = HitMergePlugin()
        merged = plugin.compute(ctx, "zero_width")

        # 应该能处理（可能过滤掉零宽度的）
        assert isinstance(merged, np.ndarray)

    def test_many_channels(self):
        """测试大量通道"""
        n_channels = 128
        hits_per_channel = 50
        total_hits = n_channels * hits_per_channel

        hits = np.zeros(total_hits, dtype=THRESHOLD_HIT_DTYPE)

        for i in range(total_hits):
            channel = i % n_channels
            hits[i]["record_id"] = i
            hits[i]["board"] = channel // 64  # 分布在多个 board
            hits[i]["channel"] = channel % 64
            hits[i]["edge_start"] = 10
            hits[i]["edge_end"] = 20
            hits[i]["position"] = 15
            hits[i]["dt"] = 2
            hits[i]["timestamp"] = (i // n_channels) * 1000

        ctx = DummyContext(
            {"merge_gap_ns": 50.0, "max_total_width_ns": 10000.0, "dt": 2},
            {"hit_threshold": hits},
        )

        plugin = HitMergePlugin()
        merged = plugin.compute(ctx, "many_channels")

        assert len(merged) > 0
        # 验证所有通道都被处理
        unique_channels = {tuple(r) for r in merged[["board", "channel"]]}
        assert len(unique_channels) > 0


class TestMemoryPressure:
    """测试内存压力"""

    @pytest.mark.slow
    def test_memory_usage_large_dataset(self):
        """测试大数据集的内存使用"""
        tracemalloc.start()
        initial_mem = tracemalloc.get_traced_memory()[0]

        # 生成大数据集
        hits, records, wave_pool = generate_large_dataset(n_records=5000, n_channels=8)

        # 运行完整流水线
        merge_ctx = DummyContext(
            {"merge_gap_ns": 50.0, "max_total_width_ns": 10000.0, "dt": 2},
            {"hit_threshold": hits},
        )
        merge_plugin = HitMergePlugin()
        merge_plugin.compute(merge_ctx, "mem_test")

        peak_mem = tracemalloc.get_traced_memory()[1]
        tracemalloc.stop()

        # 验证内存使用合理（< 500MB）
        mem_used_mb = (peak_mem - initial_mem) / (1024 * 1024)
        print(f"内存使用: {mem_used_mb:.2f} MB")
        assert mem_used_mb < 500, f"内存使用过高: {mem_used_mb:.2f} MB"

    @pytest.mark.slow
    def test_memory_cleanup(self):
        """测试内存清理"""
        gc.collect()
        initial_objects = len(gc.get_objects())

        # 运行多次
        for i in range(5):
            hits, _, _ = generate_large_dataset(n_records=1000, n_channels=4)

            ctx = DummyContext(
                {"merge_gap_ns": 50.0, "max_total_width_ns": 10000.0, "dt": 2},
                {"hit_threshold": hits},
            )
            plugin = HitMergePlugin()
            _ = plugin.compute(ctx, f"cleanup_test_{i}")

            # 清理
            del hits, ctx
            gc.collect()

        # 验证没有内存泄漏（对象数量不应显著增加）
        final_objects = len(gc.get_objects())
        object_increase = final_objects - initial_objects

        print(f"对象增加: {object_increase}")
        # 允许一些增加，但不应该太多
        assert object_increase < 1000, f"可能存在内存泄漏: {object_increase} 新对象"


class TestDependencyCycles:
    """测试循环依赖检测"""

    def test_detect_simple_cycle(self):
        """测试检测简单循环"""
        from tests.core.test_parallel_execution import detect_cycles

        # A -> B -> A
        graph = {
            "A": {"B"},
            "B": {"A"},
        }

        cycles = detect_cycles(graph)
        assert len(cycles) > 0, "应该检测到循环依赖"

    def test_detect_self_cycle(self):
        """测试检测自循环"""
        from tests.core.test_parallel_execution import detect_cycles

        # A -> A
        graph = {
            "A": {"A"},
        }

        cycles = detect_cycles(graph)
        assert len(cycles) > 0, "应该检测到自循环"

    def test_detect_long_cycle(self):
        """测试检测长循环链"""
        from tests.core.test_parallel_execution import detect_cycles

        # A -> B -> C -> D -> B
        graph = {
            "A": set(),
            "B": {"A"},
            "C": {"B"},
            "D": {"C"},
        }
        graph["B"] = {"A", "D"}  # 创建循环

        cycles = detect_cycles(graph)
        assert len(cycles) > 0, "应该检测到长循环"

    def test_no_false_positives(self):
        """测试不应误报循环"""
        from tests.core.test_parallel_execution import detect_cycles

        # 复杂但无循环的图
        graph = {
            "A": set(),
            "B": {"A"},
            "C": {"A"},
            "D": {"B", "C"},
            "E": {"B"},
            "F": {"D", "E"},
        }

        cycles = detect_cycles(graph)
        assert len(cycles) == 0, "不应该检测到循环"


class TestRobustness:
    """测试健壮性"""

    def test_mixed_dt_values(self):
        """测试混合 dt 值"""
        hits = np.zeros(3, dtype=THRESHOLD_HIT_DTYPE)

        hits[0]["record_id"] = 0
        hits[0]["channel"] = 0
        hits[0]["dt"] = 2
        hits[0]["edge_start"] = 10
        hits[0]["edge_end"] = 20
        hits[0]["position"] = 15
        hits[0]["timestamp"] = 1000

        hits[1]["record_id"] = 1
        hits[1]["channel"] = 0
        hits[1]["dt"] = 4  # 不同的 dt
        hits[1]["edge_start"] = 10
        hits[1]["edge_end"] = 20
        hits[1]["position"] = 15
        hits[1]["timestamp"] = 2000

        hits[2]["record_id"] = 2
        hits[2]["channel"] = 1
        hits[2]["dt"] = 2
        hits[2]["edge_start"] = 10
        hits[2]["edge_end"] = 20
        hits[2]["position"] = 15
        hits[2]["timestamp"] = 1000

        ctx = DummyContext(
            {"merge_gap_ns": 50.0, "max_total_width_ns": 10000.0, "dt": 2},
            {"hit_threshold": hits},
        )

        plugin = HitMergePlugin()
        merged = plugin.compute(ctx, "mixed_dt")

        # 应该能处理（可能分别处理不同 dt 的数据）
        assert isinstance(merged, np.ndarray)
        assert len(merged) > 0

    def test_unsorted_input(self):
        """测试未排序的输入"""
        hits = np.zeros(5, dtype=THRESHOLD_HIT_DTYPE)

        # 故意打乱时间顺序
        timestamps = [5000, 1000, 3000, 2000, 4000]

        for i, ts in enumerate(timestamps):
            hits[i]["record_id"] = i
            hits[i]["channel"] = 0
            hits[i]["edge_start"] = 10
            hits[i]["edge_end"] = 20
            hits[i]["position"] = 15
            hits[i]["dt"] = 2
            hits[i]["timestamp"] = ts

        ctx = DummyContext(
            {"merge_gap_ns": 50.0, "max_total_width_ns": 10000.0, "dt": 2},
            {"hit_threshold": hits},
        )

        plugin = HitMergePlugin()
        merged = plugin.compute(ctx, "unsorted")

        # 应该能正确处理（内部会排序）
        assert isinstance(merged, np.ndarray)
        assert len(merged) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "not slow"])
