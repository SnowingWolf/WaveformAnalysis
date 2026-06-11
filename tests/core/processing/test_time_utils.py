"""
测试 time_utils 模块
"""

import numpy as np
import pytest

from waveform_analysis.core.processing.time_utils import (
    compute_absolute_time_ps,
    compute_absolute_time_window_ps,
    get_pre_trigger_offset_ps,
)


class MockContext:
    """模拟 Context 对象用于测试"""

    def __init__(self, config=None):
        self.config = config or {}


def test_get_pre_trigger_offset_ps_default():
    """测试默认情况下 pre_trigger_ps = 0"""
    context = MockContext()
    assert get_pre_trigger_offset_ps(context) == 0


def test_get_pre_trigger_offset_ps_configured():
    """测试配置了 pre_trigger_ns 的情况"""
    context = MockContext(config={"pre_trigger_ns": 200})
    # 200 ns = 200000 ps
    assert get_pre_trigger_offset_ps(context) == 200000


def test_get_pre_trigger_offset_ps_zero():
    """测试显式配置为 0"""
    context = MockContext(config={"pre_trigger_ns": 0})
    assert get_pre_trigger_offset_ps(context) == 0


def test_compute_absolute_time_ps_no_pretrigger():
    """测试无 pre_trigger 时的时间计算"""
    # timestamp=1000000 ps, offset=50 samples, dt=2 ns
    result = compute_absolute_time_ps(
        timestamp_ps=1000000,
        sample_offset=50,
        dt_ns=2,
        pre_trigger_ps=0,
    )
    # 期望：1000000 + 50 * 2000 = 1100000
    assert result == 1100000


def test_compute_absolute_time_ps_with_pretrigger():
    """测试有 pre_trigger 时的时间计算"""
    # timestamp=1000000 ps, offset=50 samples, dt=2 ns, pre_trigger=200000 ps
    result = compute_absolute_time_ps(
        timestamp_ps=1000000,
        sample_offset=50,
        dt_ns=2,
        pre_trigger_ps=200000,
    )
    # 期望：(1000000 - 200000) + 50 * 2000 = 800000 + 100000 = 900000
    assert result == 900000


def test_compute_absolute_time_ps_negative_offset():
    """测试负偏移（样本在 position 之前）"""
    result = compute_absolute_time_ps(
        timestamp_ps=1000000,
        sample_offset=-10,
        dt_ns=2,
        pre_trigger_ps=0,
    )
    # 期望：1000000 + (-10) * 2000 = 980000
    assert result == 980000


def test_compute_absolute_time_ps_vectorized():
    """测试向量化计算"""
    timestamps = np.array([1000000, 2000000, 3000000], dtype=np.int64)
    offsets = np.array([0, 50, 100], dtype=np.int64)
    dt = np.array([2, 2, 2], dtype=np.int64)

    results = compute_absolute_time_ps(
        timestamp_ps=timestamps,
        sample_offset=offsets,
        dt_ns=dt,
        pre_trigger_ps=200000,
    )

    expected = np.array(
        [
            (1000000 - 200000) + 0 * 2000,  # 800000
            (2000000 - 200000) + 50 * 2000,  # 1900000
            (3000000 - 200000) + 100 * 2000,  # 3000000
        ],
        dtype=np.int64,
    )

    np.testing.assert_array_equal(results, expected)


def test_compute_absolute_time_ps_mixed_types():
    """测试混合标量和数组的情况"""
    timestamps = np.array([1000000, 2000000], dtype=np.int64)
    offset_scalar = 50  # 标量偏移
    dt_scalar = 2  # 标量 dt

    results = compute_absolute_time_ps(
        timestamp_ps=timestamps,
        sample_offset=offset_scalar,
        dt_ns=dt_scalar,
        pre_trigger_ps=100000,
    )

    expected = np.array(
        [
            (1000000 - 100000) + 50 * 2000,  # 1000000
            (2000000 - 100000) + 50 * 2000,  # 2000000
        ],
        dtype=np.int64,
    )

    np.testing.assert_array_equal(results, expected)


def test_compute_absolute_time_window_ps_no_pretrigger():
    """测试窗口时间计算（无 pre_trigger）"""
    t_start, t_end = compute_absolute_time_window_ps(
        timestamp_ps=1000000,
        start_sample=95,
        end_sample=105,
        position=100,
        dt_ns=2,
        pre_trigger_ps=0,
    )

    # start: 1000000 + (95-100)*2000 = 1000000 - 10000 = 990000
    # end: 1000000 + (105-100)*2000 = 1000000 + 10000 = 1010000
    assert t_start == 990000
    assert t_end == 1010000


def test_compute_absolute_time_window_ps_with_pretrigger():
    """测试窗口时间计算（有 pre_trigger）"""
    t_start, t_end = compute_absolute_time_window_ps(
        timestamp_ps=1000000,
        start_sample=95,
        end_sample=105,
        position=100,
        dt_ns=2,
        pre_trigger_ps=200000,
    )

    # corrected_timestamp = 1000000 - 200000 = 800000
    # start: 800000 + (95-100)*2000 = 800000 - 10000 = 790000
    # end: 800000 + (105-100)*2000 = 800000 + 10000 = 810000
    assert t_start == 790000
    assert t_end == 810000


def test_compute_absolute_time_window_ps_vectorized():
    """测试向量化窗口时间计算"""
    timestamps = np.array([1000000, 2000000], dtype=np.int64)
    starts = np.array([95, 90], dtype=np.int64)
    ends = np.array([105, 110], dtype=np.int64)
    positions = np.array([100, 100], dtype=np.int64)
    dt = np.array([2, 2], dtype=np.int64)

    t_starts, t_ends = compute_absolute_time_window_ps(
        timestamp_ps=timestamps,
        start_sample=starts,
        end_sample=ends,
        position=positions,
        dt_ns=dt,
        pre_trigger_ps=100000,
    )

    expected_starts = np.array(
        [
            (1000000 - 100000) + (95 - 100) * 2000,  # 890000
            (2000000 - 100000) + (90 - 100) * 2000,  # 1880000
        ],
        dtype=np.int64,
    )

    expected_ends = np.array(
        [
            (1000000 - 100000) + (105 - 100) * 2000,  # 910000
            (2000000 - 100000) + (110 - 100) * 2000,  # 1920000
        ],
        dtype=np.int64,
    )

    np.testing.assert_array_equal(t_starts, expected_starts)
    np.testing.assert_array_equal(t_ends, expected_ends)


def test_compute_absolute_time_ps_large_values():
    """测试大数值情况（接近 int64 上限）"""
    # 使用接近真实 DAQ 的时间戳（例如 10 秒 = 1e13 ps）
    large_timestamp = int(1e13)
    result = compute_absolute_time_ps(
        timestamp_ps=large_timestamp,
        sample_offset=1000,
        dt_ns=2,
        pre_trigger_ps=200000,
    )

    expected = (large_timestamp - 200000) + 1000 * 2000
    assert result == expected
