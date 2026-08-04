"""
测试 hit_threshold 插件的跨 records 排序行为

关键验证点：
1. hit_threshold 输出按 record 输入顺序连接，不按时间戳排序
2. 单个 record 内的 hits 按 sample position 有序
3. 并行和串行模式产生相同的顺序
"""

import numpy as np
import pytest

from tests.utils import DummyContext
from waveform_analysis.core.data.records_view import RecordsView
from waveform_analysis.core.plugins.builtin.hit.hit_finder import (
    THRESHOLD_HIT_DTYPE,
    ThresholdHitPlugin,
)
from waveform_analysis.core.processing.dtypes import create_record_dtype
from waveform_analysis.core.processing.records_builder import (
    RECORDS_DTYPE,
    build_records_from_st_waveforms,
)


def _make_records_with_timestamps(timestamps, baselines, wave_configs):
    """
    创建具有指定时间戳和波形配置的 records

    参数
    ----
    timestamps : list of int
        每个 record 的时间戳（单位：ps 或 ns，取决于 dt）
    baselines : list of float
        每个 record 的 baseline
    wave_configs : list of dict
        每个 record 的波形配置，包含：
        - wave: 波形数组或标量（填充整个波形）
        - dt: 采样间隔（ns）
        - board: board ID
        - channel: channel ID

    返回
    ----
    RecordsView
    """
    n_records = len(timestamps)
    assert len(baselines) == n_records
    assert len(wave_configs) == n_records

    # 计算总波形长度
    wave_lengths = [
        len(cfg["wave"]) if isinstance(cfg["wave"], np.ndarray) else 64 for cfg in wave_configs
    ]
    total_wave_len = sum(wave_lengths)

    # 创建 records 数组
    records = np.zeros(n_records, dtype=RECORDS_DTYPE)
    wave_pool = np.zeros(total_wave_len, dtype=np.uint16)

    offset = 0
    for i, (ts, bl, cfg, wlen) in enumerate(
        zip(timestamps, baselines, wave_configs, wave_lengths, strict=True)
    ):
        records[i]["timestamp"] = ts
        records[i]["baseline"] = bl
        records[i]["record_id"] = i
        records[i]["board"] = cfg.get("board", 0)
        records[i]["channel"] = cfg.get("channel", 0)
        records[i]["dt"] = cfg.get("dt", 2)
        records[i]["event_length"] = wlen
        records[i]["wave_offset"] = offset

        # 填充波形
        if isinstance(cfg["wave"], np.ndarray):
            wave_pool[offset : offset + wlen] = cfg["wave"]
        else:
            wave_pool[offset : offset + wlen] = cfg["wave"]

        offset += wlen

    return RecordsView(records, wave_pool)


def test_hit_threshold_follows_record_order_not_timestamp():
    """
    验证 hit_threshold 输出跟随 record 顺序，不是时间戳顺序

    场景：
    - 创建 3 个 records，时间戳故意乱序：[1000, 3000, 2000]
    - 每个 record 包含 1 个明确的 hit（baseline=100, 中间有低于阈值的信号）
    - 验证输出 hits 的顺序与 record 顺序一致（record_id: [0, 1, 2]）
    - 验证不是按时间戳顺序（如果按时间戳应该是 [0, 2, 1]）
    """
    # 创建波形：baseline=100，中间 4 个点降到 80（低于阈值 15）
    wave1 = np.array([100, 100, 80, 80, 80, 80, 100, 100], dtype=np.uint16)
    wave2 = np.array([100, 100, 80, 80, 80, 80, 100, 100], dtype=np.uint16)
    wave3 = np.array([100, 100, 80, 80, 80, 80, 100, 100], dtype=np.uint16)

    # 时间戳故意乱序：[1000, 3000, 2000]
    timestamps = [1000, 3000, 2000]
    baselines = [100.0, 100.0, 100.0]
    wave_configs = [
        {"wave": wave1, "dt": 2, "board": 0, "channel": 0},
        {"wave": wave2, "dt": 2, "board": 0, "channel": 1},
        {"wave": wave3, "dt": 2, "board": 0, "channel": 2},
    ]

    records_view = _make_records_with_timestamps(timestamps, baselines, wave_configs)

    # 设置 context 并运行 hit_threshold
    context = DummyContext(
        config={
            "hit_threshold": {
                "threshold": 15.0,
                "left_extension": 0,
                "right_extension": 0,
                "wave_source": "records",
            }
        },
        data={
            "records": records_view.records,
            "wave_pool": records_view.wave_pool,
        },
    )

    plugin = ThresholdHitPlugin()
    hits = plugin.compute_array(context, "test")

    # 验证：应该有 3 个 hits
    assert len(hits) == 3, f"Expected 3 hits, got {len(hits)}"

    # 验证：hits 的 record_id 应该按 [0, 1, 2] 顺序（record 输入顺序）
    record_ids = hits["record_id"]
    assert list(record_ids) == [0, 1, 2], f"Expected record_ids [0, 1, 2], got {list(record_ids)}"

    # 验证：hits 的 timestamp 应该按 record 顺序保留乱序输入。
    # hit timestamp 是 hit 代表位置的时间，不是 record 起始时间：
    # record timestamp + hit position * dt(ns) * 1000(ps/ns)。
    # 这证明了输出不是按时间戳排序的
    hit_timestamps = hits["timestamp"]
    expected_timestamps = [7000, 9000, 8000]
    np.testing.assert_array_equal(
        hit_timestamps,
        expected_timestamps,
        err_msg=f"Expected timestamps {expected_timestamps}, got {list(hit_timestamps)}",
    )


def test_hit_threshold_within_record_sample_order():
    """
    验证单个 record 内 hits 按 sample position 排序

    场景：
    - 单个 record 包含 2 个分离的 hits（两个低于阈值的区域）
    - 验证这些 hits 按 sample position 递增顺序排列
    """
    # 创建波形：baseline=100，两个分离的低值区域
    # 区域1：index 2-3 (值 80)
    # 区域2：index 5-6 (值 75)
    wave = np.array([100, 100, 80, 80, 100, 75, 75, 100], dtype=np.uint16)

    timestamps = [1000]
    baselines = [100.0]
    wave_configs = [{"wave": wave, "dt": 2, "board": 0, "channel": 0}]

    records_view = _make_records_with_timestamps(timestamps, baselines, wave_configs)

    # 设置 context 并运行 hit_threshold
    context = DummyContext(
        config={
            "hit_threshold": {
                "threshold": 15.0,
                "left_extension": 0,
                "right_extension": 0,
                "wave_source": "records",
            }
        },
        data={
            "records": records_view.records,
            "wave_pool": records_view.wave_pool,
        },
    )

    plugin = ThresholdHitPlugin()
    hits = plugin.compute_array(context, "test")

    # 验证：应该有 2 个 hits
    assert len(hits) == 2, f"Expected 2 hits, got {len(hits)}"

    # 验证：两个 hits 的 edge_start 应该递增
    edge_starts = hits["edge_start"]
    assert edge_starts[0] < edge_starts[1], (
        f"Hits should be ordered by sample position, " f"got edge_starts {list(edge_starts)}"
    )

    # 验证：具体位置
    assert edge_starts[0] == 2, f"First hit should start at index 2, got {edge_starts[0]}"
    assert edge_starts[1] == 5, f"Second hit should start at index 5, got {edge_starts[1]}"


def test_hit_threshold_empty_and_mixed_records():
    """
    验证混合有 hits 和无 hits 的 records

    场景：
    - 创建 4 个 records：[有hit, 无hit, 有hit, 无hit]
    - 时间戳顺序：[1000, 2000, 3000, 4000]
    - 验证只有包含 hits 的 records 出现在输出中
    - 验证 record_id 保持正确
    """
    # Record 0 和 2 有 hit，1 和 3 无 hit
    wave_with_hit = np.array([100, 100, 80, 80, 80, 80, 100, 100], dtype=np.uint16)
    wave_no_hit = np.array([100, 100, 100, 100, 100, 100, 100, 100], dtype=np.uint16)

    timestamps = [1000, 2000, 3000, 4000]
    baselines = [100.0, 100.0, 100.0, 100.0]
    wave_configs = [
        {"wave": wave_with_hit, "dt": 2, "board": 0, "channel": 0},
        {"wave": wave_no_hit, "dt": 2, "board": 0, "channel": 1},
        {"wave": wave_with_hit, "dt": 2, "board": 0, "channel": 2},
        {"wave": wave_no_hit, "dt": 2, "board": 0, "channel": 3},
    ]

    records_view = _make_records_with_timestamps(timestamps, baselines, wave_configs)

    # 设置 context 并运行 hit_threshold
    context = DummyContext(
        config={
            "hit_threshold": {
                "threshold": 15.0,
                "left_extension": 0,
                "right_extension": 0,
                "wave_source": "records",
            }
        },
        data={
            "records": records_view.records,
            "wave_pool": records_view.wave_pool,
        },
    )

    plugin = ThresholdHitPlugin()
    hits = plugin.compute_array(context, "test")

    # 验证：应该有 2 个 hits（来自 record 0 和 2）
    assert len(hits) == 2, f"Expected 2 hits, got {len(hits)}"

    # 验证：record_id 应该是 [0, 2]
    record_ids = hits["record_id"]
    assert list(record_ids) == [0, 2], f"Expected record_ids [0, 2], got {list(record_ids)}"

    # 验证：timestamp 应该按 record 顺序对应 hit 代表位置时间
    hit_timestamps = hits["timestamp"]
    expected_timestamps = [7000, 9000]
    np.testing.assert_array_equal(
        hit_timestamps,
        expected_timestamps,
        err_msg=f"Expected timestamps {expected_timestamps}, got {list(hit_timestamps)}",
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
