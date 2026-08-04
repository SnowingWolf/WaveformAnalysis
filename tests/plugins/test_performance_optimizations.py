"""测试性能优化的正确性和加速效果。

测试覆盖：
1. Peaklets Numba 加速的功能正确性
2. Hit merged features parallel 模式
3. 优化前后输出一致性
"""

import numpy as np
import pytest

from tests.utils import DummyContext, make_hit, make_records
from waveform_analysis.core.plugins.builtin.cpu.hit_merge import (
    HIT_MERGED_DTYPE,
    HitMergedComponentsPlugin,
    HitMergePlugin,
)
from waveform_analysis.core.plugins.builtin.cpu.hit_merged_features import (
    HIT_MERGED_FEATURES_DTYPE,
    HitMergedFeaturesPlugin,
)
from waveform_analysis.core.plugins.builtin.cpu.peaklets import (
    PEAKLET_DTYPE,
    PeakletComponentsPlugin,
    PeakletPlugin,
    PeakletWaveformPlugin,
)
from waveform_analysis.core.plugins.builtin.hit.hit_finder import THRESHOLD_HIT_DTYPE
from waveform_analysis.core.plugins.builtin.peaklets._compute import _cluster_merged_hits

try:
    from numba import njit  # noqa: F401

    HAS_NUMBA = True
except ImportError:
    HAS_NUMBA = False


def _make_test_context(n_hits=10, n_channels=4, time_gap=2):
    """创建测试上下文，包含完整的数据流"""
    # 生成测试数据：多通道、时间上有轻微间隔
    hits = []
    for i in range(n_hits):
        channel = i % n_channels
        timestamp = i * time_gap * 1000  # 每个 hit 间隔 time_gap ns
        hit = make_hit(
            record_id=i,
            board=0,
            channel=channel,
            edge_start=10,
            edge_end=20,
            dt=2,
            timestamp=timestamp,
        )
        hits.append(hit)

    hits = np.array(hits, dtype=THRESHOLD_HIT_DTYPE)

    # 创建 records 和 wave_pool
    records = make_records(n_records=n_hits, event_length=50, baseline=100.0, dt=2)
    for i in range(n_hits):
        records[i]["board"] = hits[i]["board"]
        records[i]["channel"] = hits[i]["channel"]
        records[i]["timestamp"] = hits[i]["timestamp"]
        records[i]["polarity"] = "negative"

    # 生成测试波形数据
    wave_pool = np.random.randint(90, 110, size=n_hits * 50, dtype=np.uint16)

    # 构建完整的数据流
    merge_ctx = DummyContext(
        {"merge_gap_ns": 100.0, "max_total_width_ns": 10000.0, "dt": 2},
        {"hit_threshold": hits},
    )
    merge_plugin = HitMergePlugin()
    merged = merge_plugin.compute(merge_ctx, "test_run")

    comp_ctx = DummyContext(
        {"merge_gap_ns": 100.0, "max_total_width_ns": 10000.0, "dt": 2},
        {"hit_threshold": hits, "hit_merged": merged},
    )
    comp_ctx._plugins = {"hit_merged": merge_plugin}
    comp_ctx.get_plugin = lambda name: comp_ctx._plugins.get(name)
    components = HitMergedComponentsPlugin().compute(comp_ctx, "test_run")

    return hits, records, wave_pool, merged, components


class TestPeakletsNumbaAcceleration:
    """测试 Peaklets 插件的 Numba 加速功能"""

    @pytest.mark.skipif(not HAS_NUMBA, reason="Numba not available")
    def test_cluster_merged_hits_basic(self):
        """测试基本的聚类功能"""
        # 创建简单的 merged hits
        merged = np.zeros(3, dtype=HIT_MERGED_DTYPE)
        merged[0]["timestamp"] = 1000000
        merged[0]["sample_start"] = 0
        merged[0]["sample_end"] = 10
        merged[0]["dt"] = 2
        merged[0]["position"] = 5
        merged[0]["channel"] = 0
        merged[0]["time_start"] = 1000000
        merged[0]["time_end"] = 1020000

        merged[1]["timestamp"] = 1050000  # 50 ns 后
        merged[1]["sample_start"] = 0
        merged[1]["sample_end"] = 10
        merged[1]["dt"] = 2
        merged[1]["position"] = 5
        merged[1]["channel"] = 1
        merged[1]["time_start"] = 1050000
        merged[1]["time_end"] = 1070000

        merged[2]["timestamp"] = 2000000  # 远离前两个
        merged[2]["sample_start"] = 0
        merged[2]["sample_end"] = 10
        merged[2]["dt"] = 2
        merged[2]["position"] = 5
        merged[2]["channel"] = 0
        merged[2]["time_start"] = 2000000
        merged[2]["time_end"] = 2020000

        # 使用小的时间窗口聚类
        clusters = _cluster_merged_hits(merged, time_window_ns=100.0, max_total_width_ns=10000.0)

        # 验证聚类结果
        assert len(clusters) == 2, "应该生成 2 个 clusters"
        assert len(clusters[0]) == 2, "第一个 cluster 应包含 2 个 hits"
        assert len(clusters[1]) == 1, "第二个 cluster 应包含 1 个 hit"

    @pytest.mark.skipif(not HAS_NUMBA, reason="Numba not available")
    def test_cluster_respects_max_width(self):
        """测试 max_total_width 约束"""
        merged = np.zeros(2, dtype=HIT_MERGED_DTYPE)
        merged[0]["timestamp"] = 1000000
        merged[0]["sample_start"] = 0
        merged[0]["sample_end"] = 1000  # 很宽
        merged[0]["dt"] = 2
        merged[0]["position"] = 0
        merged[0]["channel"] = 0
        merged[0]["time_start"] = 1000000
        merged[0]["time_end"] = 3000000

        merged[1]["timestamp"] = 1010000  # 10 ns 后
        merged[1]["sample_start"] = 0
        merged[1]["sample_end"] = 1000
        merged[1]["dt"] = 2
        merged[1]["position"] = 0
        merged[1]["channel"] = 1
        merged[1]["time_start"] = 1010000
        merged[1]["time_end"] = 3010000

        # 使用小的 max_total_width
        clusters = _cluster_merged_hits(merged, time_window_ns=100.0, max_total_width_ns=500.0)

        # 应该分成两个 cluster，因为总宽度超过限制
        assert len(clusters) == 2, "应该因为宽度限制分成 2 个 clusters"

    def test_peaklet_plugin_with_numba(self):
        """测试 PeakletPlugin 在大数据集上的正确性"""
        # 生成足够多的数据触发 Numba 路径（如果可用）
        hits, records, wave_pool, merged, components = _make_test_context(
            n_hits=100, n_channels=8, time_gap=2
        )

        ctx = DummyContext(
            {
                "time_window_ns": 100.0,
                "max_total_width_ns": 10000.0,
                "dt": 2,
                "use_filtered": False,
            },
            {
                "hit_merged": merged,
                "hit_threshold": hits,
                "records": records,
                "wave_pool": wave_pool,
            },
        )

        peaklet_components = PeakletComponentsPlugin().compute_array(ctx, "test_run")
        ctx._data["peaklet_components"] = peaklet_components
        plugin = PeakletPlugin()
        peaklets = plugin.compute_array(ctx, "test_run")

        # 验证输出结构
        assert peaklets.dtype == PEAKLET_DTYPE
        assert len(peaklets) > 0, "应该生成 peaklets"

        # 验证字段合理性
        for peaklet in peaklets:
            assert peaklet["time_start"] < peaklet["time_end"], "time_start 应小于 time_end"
            assert peaklet["n_hits"] > 0, "n_hits 应大于 0"
            assert peaklet["n_channels"] > 0, "n_channels 应大于 0"
            assert peaklet["component_count"] > 0, "component_count 应大于 0"

    @pytest.mark.skipif(not HAS_NUMBA, reason="Numba not available")
    def test_peaklet_waveform_numba_vs_python(self):
        """对比 Numba 和 Python fallback 的输出一致性"""
        hits, records, wave_pool, merged, components = _make_test_context(
            n_hits=20, n_channels=4, time_gap=2
        )

        ctx = DummyContext(
            {
                "time_window_ns": 100.0,
                "max_total_width_ns": 10000.0,
                "dt": 2,
                "use_filtered": False,
            },
            {
                "hit_merged": merged,
                "hit_threshold": hits,
                "records": records,
                "wave_pool": wave_pool,
            },
        )

        # 生成正式 flat membership，再由 peaklets 消费该依赖。
        comp_plugin = PeakletComponentsPlugin()
        peaklet_components = comp_plugin.compute_array(ctx, "test_run")
        ctx._data["peaklet_components"] = peaklet_components
        peaklet_plugin = PeakletPlugin()
        peaklets = peaklet_plugin.compute_array(ctx, "test_run")
        ctx._data["peaklets"] = peaklets

        wf_plugin = PeakletWaveformPlugin()
        wf_plugin._hit_merged_components = components
        wf_plugin._hit_threshold = hits
        wf_plugin._clip_negative_signal = False
        wf_plugin._debug_numba = True

        python_waveforms, python_pool = wf_plugin._build_python(
            peaklets=peaklets,
            components=peaklet_components,
            merged=merged,
            records=records,
            wave_pool=wave_pool,
        )
        optimized_waveforms, optimized_pool = wf_plugin._build(
            peaklets=peaklets,
            components=peaklet_components,
            merged=merged,
            records=records,
            wave_pool=wave_pool,
        )

        assert optimized_waveforms.dtype == python_waveforms.dtype
        for field in optimized_waveforms.dtype.names:
            np.testing.assert_array_equal(
                optimized_waveforms[field],
                python_waveforms[field],
                err_msg=f"优化路径和 Python 的 {field} 字段不一致",
            )
        np.testing.assert_array_equal(
            optimized_pool,
            python_pool,
            err_msg="优化路径和 Python 的 waveform pool 不一致",
        )


class TestHitMergedFeaturesParallel:
    """测试 HitMergedFeaturesPlugin 的并行模式"""

    def test_features_basic_correctness(self):
        """测试基本的特征计算正确性"""
        hits, records, wave_pool, merged, components = _make_test_context(
            n_hits=50, n_channels=4, time_gap=2
        )

        ctx = DummyContext(
            {
                "wave_source": "records",
                "use_filtered": False,
                "dt": 2,
            },
            {
                "hit_merged": merged,
                "hit_merged_components": components,
                "hit_threshold": hits,
                "records": records,
                "wave_pool": wave_pool,
            },
        )

        plugin = HitMergedFeaturesPlugin()
        features = plugin.compute(ctx, "test_run")

        # 验证输出结构
        assert features.dtype == HIT_MERGED_FEATURES_DTYPE
        assert len(features) == len(merged), "每个 merged hit 应有一个 feature"

        # 验证字段合理性
        for feature in features:
            assert feature["time_start"] < feature["time_end"], "time_start 应小于 time_end"
            assert feature["area"] >= 0, "area 应非负"
            assert feature["height"] >= 0, "height 应非负"
            assert feature["width"] >= 0, "width 应非负"
            assert feature["valid"] == 1, "所有 features 应该是 valid 的"

    @pytest.mark.skipif(not HAS_NUMBA, reason="Numba not available")
    def test_features_numba_fast_kernel(self):
        """测试 Numba 快速内核的正确性"""
        from waveform_analysis.core.plugins.builtin.hit.hit_merged_features import (
            _features_fast_kernel,
        )

        # 创建简单的测试数据
        n = 5
        wave_pool = np.array([100, 105, 110, 105, 100] * n, dtype=np.uint16)
        rec_indices = np.arange(n, dtype=np.int64)
        rec_wave_offset = np.arange(0, n * 5, 5, dtype=np.int64)
        rec_event_length = np.full(n, 5, dtype=np.int64)
        rec_baseline = np.full(n, 100.0, dtype=np.float32)
        rec_polarity_sign = np.full(n, -1.0, dtype=np.float32)

        merged_sample_start = np.zeros(n, dtype=np.int64)
        merged_sample_end = np.full(n, 5, dtype=np.int64)
        merged_timestamp = np.arange(0, n * 10000, 10000, dtype=np.int64)
        merged_dt = np.full(n, 2, dtype=np.int64)
        merged_position = np.zeros(n, dtype=np.int64)

        # 调用 Numba 内核：签名要求第 12 个参数为预分配的 out 数组，内核直接写入而非返回
        out = np.zeros(n, dtype=HIT_MERGED_FEATURES_DTYPE)
        _features_fast_kernel(
            wave_pool,
            rec_indices,
            rec_wave_offset,
            rec_event_length,
            rec_baseline,
            rec_polarity_sign,
            merged_sample_start,
            merged_sample_end,
            merged_timestamp,
            merged_dt,
            merged_position,
            out,
        )

        # 验证输出（从 out 的字段读取）
        assert np.all(out["valid"] == 1), "所有结果应该是 valid 的"
        assert np.all(out["time_start"] < out["time_end"]), "time_start 应小于 time_end"
        assert np.all(out["area"] >= 0), "area 应非负"
        assert np.all(out["height"] >= 0), "height 应非负"
        assert np.all(out["width"] >= 0), "width 应非负"
        assert np.all(out["time_start"] <= out["center_time"]) and np.all(
            out["center_time"] <= out["time_end"]
        ), "center_time 应位于 [time_start, time_end] 内"
        assert np.all(out["time_start"] <= out["max_time"]) and np.all(
            out["max_time"] <= out["time_end"]
        ), "max_time 应位于 [time_start, time_end] 内"
        assert np.all(out["rise_time"] >= 0), "rise_time 应非负"
        assert np.all(out["fall_time"] >= 0), "fall_time 应非负"

    def test_features_edge_cases(self):
        """测试边界情况"""
        # 空输入
        empty_merged = np.zeros(0, dtype=HIT_MERGED_DTYPE)
        empty_components = np.zeros(
            0, dtype=np.dtype([("merged_index", "i8"), ("hit_index", "i8")])
        )
        empty_hits = np.zeros(0, dtype=THRESHOLD_HIT_DTYPE)
        empty_records = make_records(n_records=0)
        empty_wave_pool = np.zeros(0, dtype=np.uint16)

        ctx = DummyContext(
            {"wave_source": "records", "use_filtered": False, "dt": 2},
            {
                "hit_merged": empty_merged,
                "hit_merged_components": empty_components,
                "hit_threshold": empty_hits,
                "records": empty_records,
                "wave_pool": empty_wave_pool,
            },
        )

        plugin = HitMergedFeaturesPlugin()
        features = plugin.compute(ctx, "test_run")

        assert len(features) == 0, "空输入应返回空输出"
        assert features.dtype == HIT_MERGED_FEATURES_DTYPE


class TestOptimizationConsistency:
    """测试优化前后的输出一致性"""

    def test_peaklet_clustering_determinism(self):
        """测试聚类结果的确定性"""
        hits, records, wave_pool, merged, components = _make_test_context(
            n_hits=100, n_channels=8, time_gap=2
        )

        ctx = DummyContext(
            {"time_window_ns": 100.0, "max_total_width_ns": 10000.0, "dt": 2},
            {"hit_merged": merged},
        )

        peaklet_components = PeakletComponentsPlugin().compute_array(ctx, "test_run")
        ctx._data["peaklet_components"] = peaklet_components
        plugin = PeakletPlugin()

        # 多次运行，验证结果一致
        result1 = plugin.compute_array(ctx, "test_run")
        result2 = plugin.compute_array(ctx, "test_run")
        result3 = plugin.compute_array(ctx, "test_run")

        # 验证完全一致
        for field in result1.dtype.names:
            np.testing.assert_array_equal(
                result1[field], result2[field], err_msg=f"第二次运行的 {field} 不一致"
            )
            np.testing.assert_array_equal(
                result1[field], result3[field], err_msg=f"第三次运行的 {field} 不一致"
            )

    def test_features_computation_stability(self):
        """测试特征计算的稳定性"""
        hits, records, wave_pool, merged, components = _make_test_context(
            n_hits=50, n_channels=4, time_gap=2
        )

        ctx = DummyContext(
            {
                "wave_source": "records",
                "use_filtered": False,
                "dt": 2,
            },
            {
                "hit_merged": merged,
                "hit_merged_components": components,
                "hit_threshold": hits,
                "records": records,
                "wave_pool": wave_pool,
            },
        )

        plugin = HitMergedFeaturesPlugin()

        # 多次运行
        result1 = plugin.compute(ctx, "test_run")
        result2 = plugin.compute(ctx, "test_run")

        # 验证数值特征一致（允许浮点误差）
        for field in ["area", "height", "width", "rise_time", "fall_time"]:
            np.testing.assert_allclose(
                result1[field], result2[field], rtol=1e-6, err_msg=f"特征 {field} 计算不稳定"
            )

        # 验证整数字段完全一致
        for field in ["merged_index", "time_start", "time_end", "max_time", "center_time", "valid"]:
            np.testing.assert_array_equal(
                result1[field], result2[field], err_msg=f"字段 {field} 不一致"
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
