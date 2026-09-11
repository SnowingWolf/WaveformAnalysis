"""
集成测试：验证 pre_trigger_ns 配置对跨 record hit 合并的影响
"""

import numpy as np

from tests.utils import DummyContext
from waveform_analysis.core.plugins.builtin.hit_merged import HitMergePlugin
from waveform_analysis.core.plugins.builtin.hit_threshold import THRESHOLD_HIT_DTYPE


def test_hit_merge_with_pretrigger_backward_compatible():
    """测试 pre_trigger_ns=0 时向后兼容（默认行为）"""
    plugin = HitMergePlugin()
    dt_ns = 2

    # 两个 hit，timestamp 相差 2000 ps = 2 ns
    hit1 = np.array(
        [(100, 95, 105, 10.0, dt_ns, 1000000, 0, 0, 1)],
        dtype=THRESHOLD_HIT_DTYPE,
    )
    hit2 = np.array(
        [(100, 95, 105, 10.0, dt_ns, 1002000, 0, 0, 2)],
        dtype=THRESHOLD_HIT_DTYPE,
    )
    hits = np.concatenate([hit1, hit2])

    # 场景 1：没有设置 pre_trigger_ns（默认为 0）
    ctx_default = DummyContext(
        {"merge_gap_ns": 10.0, "max_total_width_ns": 10000.0},
        {"hit_threshold": hits.copy()},
    )
    merged_default = plugin.compute(ctx_default, "test_run")

    # 场景 2：显式设置 pre_trigger_ns = 0
    ctx_explicit_zero = DummyContext(
        {"merge_gap_ns": 10.0, "max_total_width_ns": 10000.0, "pre_trigger_ns": 0},
        {"hit_threshold": hits.copy()},
    )
    merged_explicit = plugin.compute(ctx_explicit_zero, "test_run")

    # 两者应该产生相同结果（都合并）
    assert len(merged_default) == 1
    assert len(merged_explicit) == 1
    assert merged_default[0]["component_count"] == 2
    assert merged_explicit[0]["component_count"] == 2


def test_hit_merge_pretrigger_affects_time_calculation():
    """测试 pre_trigger_ns 影响绝对时间计算"""
    plugin = HitMergePlugin()
    dt_ns = 2
    pre_trigger_ns = 200  # 100 个采样点 * 2 ns

    # 构造特殊场景：两个 hit 的 raw timestamp 相差很小
    # 但考虑 pre_trigger 后绝对时间计算会改变
    hit1 = np.array(
        [(100, 95, 105, 10.0, dt_ns, 1000000, 0, 0, 1)],
        dtype=THRESHOLD_HIT_DTYPE,
    )
    hit2 = np.array(
        [(100, 95, 105, 10.0, dt_ns, 1001000, 0, 0, 2)],
        dtype=THRESHOLD_HIT_DTYPE,
    )
    hits = np.concatenate([hit1, hit2])

    # 没有 pre_trigger：timestamp 差 1000 ps = 1 ns，应该合并
    ctx_no_pretrigger = DummyContext(
        {"merge_gap_ns": 5.0, "max_total_width_ns": 10000.0},
        {"hit_threshold": hits.copy()},
    )
    merged_no = plugin.compute(ctx_no_pretrigger, "test_run")
    assert len(merged_no) == 1, "Without pre_trigger, hits should merge"

    # 有 pre_trigger：时间修正后仍然间隔 1 ns，应该合并
    ctx_with_pretrigger = DummyContext(
        {"merge_gap_ns": 5.0, "max_total_width_ns": 10000.0, "pre_trigger_ns": pre_trigger_ns},
        {"hit_threshold": hits.copy()},
    )
    merged_with = plugin.compute(ctx_with_pretrigger, "test_run")
    assert len(merged_with) == 1, "With pre_trigger correction, hits should still merge"


def test_hit_merge_pretrigger_with_large_timestamps():
    """测试大时间戳值（接近真实 DAQ 场景）"""
    plugin = HitMergePlugin()
    dt_ns = 2
    pre_trigger_ns = 200

    # 使用接近真实的大时间戳（例如 10 秒 = 1e13 ps）
    large_timestamp = int(1e13)

    hit1 = np.array(
        [(100, 95, 105, 10.0, dt_ns, large_timestamp, 0, 0, 1)],
        dtype=THRESHOLD_HIT_DTYPE,
    )
    hit2 = np.array(
        [(100, 95, 105, 10.0, dt_ns, large_timestamp + 5000, 0, 0, 2)],
        dtype=THRESHOLD_HIT_DTYPE,
    )
    hits = np.concatenate([hit1, hit2])

    ctx = DummyContext(
        {"merge_gap_ns": 10.0, "max_total_width_ns": 10000.0, "pre_trigger_ns": pre_trigger_ns},
        {"hit_threshold": hits},
    )

    merged = plugin.compute(ctx, "test_run")

    # 应该能够正确处理大数值，合并成功
    assert len(merged) == 1
    assert merged[0]["component_count"] == 2
    # 时间戳应该在合理范围内（不应该溢出）
    assert merged[0]["timestamp"] > 0
    assert merged[0]["timestamp"] < large_timestamp + 1000000
