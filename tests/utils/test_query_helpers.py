"""测试 query_helpers 模块的查询函数"""

import numpy as np
import pandas as pd
import pytest

from waveform_analysis.utils.query_helpers import (
    build_merged_to_hit_lookup,
    build_peak_to_merged_lookup,
    get_hit_indices_for_merged,
    get_hits_for_merged,
    get_hits_for_peak,
    get_merged_indices_for_peak,
)

# =============================================================================
# 测试数据构建
# =============================================================================


def create_test_peaklet_components():
    """创建测试用的 peaklet_components 数据"""
    dtype = np.dtype([("peak_id", "i8"), ("merged_index", "i8")])
    data = np.array(
        [
            (100, 200),  # peak 100 包含 merged 200, 201, 202
            (100, 201),
            (100, 202),
            (101, 203),  # peak 101 包含 merged 203
            (102, 204),  # peak 102 包含 merged 204, 205
            (102, 205),
        ],
        dtype=dtype,
    )
    return data


def create_test_hit_merged_components():
    """创建测试用的 hit_merged_components 数据"""
    dtype = np.dtype([("merged_index", "i8"), ("hit_index", "i8")])
    data = np.array(
        [
            (200, 0),  # merged 200 包含 hit 0, 1
            (200, 1),
            (201, 2),  # merged 201 包含 hit 2, 3, 4
            (201, 3),
            (201, 4),
            (202, 5),  # merged 202 包含 hit 5
            (203, 6),  # merged 203 包含 hit 6, 7
            (203, 7),
            (204, 8),  # merged 204 包含 hit 8
        ],
        dtype=dtype,
    )
    return data


def create_test_hit_threshold():
    """创建测试用的 hit_threshold 数据"""
    dtype = np.dtype(
        [
            ("position", "i8"),
            ("edge_start", "i4"),
            ("edge_end", "i4"),
            ("width", "f4"),
            ("dt", "i4"),
            ("timestamp", "i8"),
            ("board", "i2"),
            ("channel", "i2"),
            ("record_id", "i8"),
        ]
    )

    # 创建 9 个 hit（对应上面的 hit_index 0-8）
    data = np.zeros(9, dtype=dtype)

    for i in range(9):
        data[i]["position"] = 100 + i * 10
        data[i]["edge_start"] = 100 + i * 10  # edge_start == position（简化）
        data[i]["edge_end"] = 110 + i * 10
        data[i]["width"] = 10.0
        data[i]["dt"] = 10  # 10 ns 采样间隔
        data[i]["timestamp"] = 1000000 + i * 1000  # ps，每个 hit 间隔 1000 ps
        data[i]["board"] = 1
        data[i]["channel"] = i % 4
        data[i]["record_id"] = 1000 + i // 3

    return data


# =============================================================================
# 基础查询函数测试
# =============================================================================


def test_get_merged_indices_for_peak():
    """测试 get_merged_indices_for_peak 基本功能"""
    peaklet_components = create_test_peaklet_components()

    # 测试 peak 100（包含 3 个 merged）
    merged_indices = get_merged_indices_for_peak(100, peaklet_components)
    assert len(merged_indices) == 3
    assert set(merged_indices) == {200, 201, 202}

    # 测试 peak 101（包含 1 个 merged）
    merged_indices = get_merged_indices_for_peak(101, peaklet_components)
    assert len(merged_indices) == 1
    assert merged_indices[0] == 203

    # 测试不存在的 peak
    merged_indices = get_merged_indices_for_peak(999, peaklet_components)
    assert len(merged_indices) == 0


def test_get_merged_indices_for_peak_empty_input():
    """测试空输入情况"""
    empty_array = np.array([], dtype=[("peak_id", "i8"), ("merged_index", "i8")])
    merged_indices = get_merged_indices_for_peak(100, empty_array)
    assert len(merged_indices) == 0

    # 测试 None 输入
    merged_indices = get_merged_indices_for_peak(100, None)
    assert len(merged_indices) == 0


def test_get_hit_indices_for_merged():
    """测试 get_hit_indices_for_merged 基本功能"""
    hit_merged_components = create_test_hit_merged_components()

    # 测试 merged 200（包含 2 个 hit）
    hit_indices = get_hit_indices_for_merged(200, hit_merged_components)
    assert len(hit_indices) == 2
    assert set(hit_indices) == {0, 1}

    # 测试 merged 201（包含 3 个 hit）
    hit_indices = get_hit_indices_for_merged(201, hit_merged_components)
    assert len(hit_indices) == 3
    assert set(hit_indices) == {2, 3, 4}

    # 测试不存在的 merged
    hit_indices = get_hit_indices_for_merged(999, hit_merged_components)
    assert len(hit_indices) == 0


def test_get_hit_indices_for_merged_empty_input():
    """测试空输入情况"""
    empty_array = np.array([], dtype=[("merged_index", "i8"), ("hit_index", "i8")])
    hit_indices = get_hit_indices_for_merged(200, empty_array)
    assert len(hit_indices) == 0

    # 测试 None 输入
    hit_indices = get_hit_indices_for_merged(200, None)
    assert len(hit_indices) == 0


# =============================================================================
# 完整数据查询函数测试
# =============================================================================


def test_get_hits_for_merged():
    """测试 get_hits_for_merged 基本功能"""
    hit_merged_components = create_test_hit_merged_components()
    hit_threshold = create_test_hit_threshold()

    # 测试 merged 200（包含 hit 0, 1）
    df = get_hits_for_merged(200, hit_merged_components, hit_threshold)

    assert isinstance(df, pd.DataFrame)
    assert len(df) == 2
    assert list(df["hit_index"]) == [0, 1]

    # 验证列存在
    assert "position" in df.columns
    assert "edge_start" in df.columns
    assert "edge_end" in df.columns
    assert "time_start" in df.columns
    assert "time_end" in df.columns
    assert "dt_start_to_start_ns" in df.columns
    assert "dt_end_to_start_ns" in df.columns

    # 验证第一行的时间间隔为 NaN
    assert pd.isna(df.iloc[0]["dt_start_to_start_ns"])
    assert pd.isna(df.iloc[0]["dt_end_to_start_ns"])

    # 验证第二行的时间间隔
    # hit 0: time_start = 1000000 ps
    # hit 1: time_start = 1001000 ps
    # dt_start_to_start_ns = (1001000 - 1000000) / 1000.0 = 1.0 ns
    assert df.iloc[1]["dt_start_to_start_ns"] == pytest.approx(1.0)


def test_get_hits_for_merged_time_calculation():
    """测试时间计算的正确性"""
    hit_merged_components = create_test_hit_merged_components()
    hit_threshold = create_test_hit_threshold()

    df = get_hits_for_merged(200, hit_merged_components, hit_threshold)

    # 验证 time_start 和 time_end 的计算
    # 对于 hit 0:
    # position = 100, edge_start = 100, edge_end = 110
    # timestamp = 1000000 ps, dt = 10 ns
    # time_start = 1000000 + (100 - 100) * 10 * 1000 = 1000000 ps
    # time_end = 1000000 + (110 - 100) * 10 * 1000 = 1100000 ps
    hit_0 = df[df["hit_index"] == 0].iloc[0]
    assert hit_0["time_start"] == 1000000
    assert hit_0["time_end"] == 1100000


def test_get_hits_for_merged_empty():
    """测试不存在的 merged_index"""
    hit_merged_components = create_test_hit_merged_components()
    hit_threshold = create_test_hit_threshold()

    df = get_hits_for_merged(999, hit_merged_components, hit_threshold)

    assert isinstance(df, pd.DataFrame)
    assert len(df) == 0
    # 验证列结构存在
    assert "hit_index" in df.columns
    assert "time_start" in df.columns


def test_get_hits_for_peak():
    """测试 get_hits_for_peak 基本功能"""
    peaklet_components = create_test_peaklet_components()
    hit_merged_components = create_test_hit_merged_components()
    hit_threshold = create_test_hit_threshold()

    # 测试 peak 100（包含 merged 200, 201, 202）
    # merged 200: hit 0, 1
    # merged 201: hit 2, 3, 4
    # merged 202: hit 5
    df = get_hits_for_peak(100, peaklet_components, hit_merged_components, hit_threshold)

    assert isinstance(df, pd.DataFrame)
    assert len(df) == 6  # 总共 6 个 hit
    assert set(df["hit_index"]) == {0, 1, 2, 3, 4, 5}

    # 验证 peak_id 和 merged_index 列存在
    assert "peak_id" in df.columns
    assert "merged_index" in df.columns

    # 验证所有行的 peak_id 都是 100
    assert (df["peak_id"] == 100).all()

    # 验证 merged_index 的分布
    assert set(df["merged_index"]) == {200, 201, 202}


def test_get_hits_for_peak_sorting():
    """测试 get_hits_for_peak 的排序功能"""
    peaklet_components = create_test_peaklet_components()
    hit_merged_components = create_test_hit_merged_components()
    hit_threshold = create_test_hit_threshold()

    df = get_hits_for_peak(100, peaklet_components, hit_merged_components, hit_threshold)

    # 验证按 time_start 排序
    time_starts = df["time_start"].values
    assert (time_starts[:-1] <= time_starts[1:]).all(), "DataFrame 应该按 time_start 排序"


def test_get_hits_for_peak_empty():
    """测试不存在的 peak_id"""
    peaklet_components = create_test_peaklet_components()
    hit_merged_components = create_test_hit_merged_components()
    hit_threshold = create_test_hit_threshold()

    df = get_hits_for_peak(999, peaklet_components, hit_merged_components, hit_threshold)

    assert isinstance(df, pd.DataFrame)
    assert len(df) == 0
    # 验证列结构存在
    assert "peak_id" in df.columns
    assert "merged_index" in df.columns
    assert "hit_index" in df.columns


# =============================================================================
# 批量优化函数测试
# =============================================================================


def test_build_peak_to_merged_lookup():
    """测试 build_peak_to_merged_lookup"""
    peaklet_components = create_test_peaklet_components()

    lookup = build_peak_to_merged_lookup(peaklet_components)

    assert isinstance(lookup, dict)
    assert 100 in lookup
    assert 101 in lookup
    assert 102 in lookup

    # 验证 peak 100 的映射
    assert len(lookup[100]) == 3
    assert set(lookup[100]) == {200, 201, 202}

    # 验证 peak 101 的映射
    assert len(lookup[101]) == 1
    assert lookup[101][0] == 203


def test_build_peak_to_merged_lookup_empty():
    """测试空输入"""
    empty_array = np.array([], dtype=[("peak_id", "i8"), ("merged_index", "i8")])
    lookup = build_peak_to_merged_lookup(empty_array)
    assert lookup == {}

    # 测试 None 输入
    lookup = build_peak_to_merged_lookup(None)
    assert lookup == {}


def test_build_merged_to_hit_lookup():
    """测试 build_merged_to_hit_lookup"""
    hit_merged_components = create_test_hit_merged_components()

    lookup = build_merged_to_hit_lookup(hit_merged_components)

    assert isinstance(lookup, dict)
    assert 200 in lookup
    assert 201 in lookup
    assert 203 in lookup

    # 验证 merged 200 的映射
    assert len(lookup[200]) == 2
    assert set(lookup[200]) == {0, 1}

    # 验证 merged 201 的映射
    assert len(lookup[201]) == 3
    assert set(lookup[201]) == {2, 3, 4}


def test_build_merged_to_hit_lookup_empty():
    """测试空输入"""
    empty_array = np.array([], dtype=[("merged_index", "i8"), ("hit_index", "i8")])
    lookup = build_merged_to_hit_lookup(empty_array)
    assert lookup == {}

    # 测试 None 输入
    lookup = build_merged_to_hit_lookup(None)
    assert lookup == {}


# =============================================================================
# 集成测试
# =============================================================================


def test_full_workflow():
    """测试完整的查询工作流"""
    peaklet_components = create_test_peaklet_components()
    hit_merged_components = create_test_hit_merged_components()
    hit_threshold = create_test_hit_threshold()

    # 1. 查询 peak 100 的 merged_indices
    merged_indices = get_merged_indices_for_peak(100, peaklet_components)
    assert len(merged_indices) == 3

    # 2. 对每个 merged_index 查询 hit_indices
    all_hit_indices = []
    for merged_index in merged_indices:
        hit_indices = get_hit_indices_for_merged(merged_index, hit_merged_components)
        all_hit_indices.extend(hit_indices)
    assert len(all_hit_indices) == 6

    # 3. 使用 get_hits_for_peak 一次性获取
    df = get_hits_for_peak(100, peaklet_components, hit_merged_components, hit_threshold)
    assert len(df) == 6
    assert set(df["hit_index"]) == set(all_hit_indices)


def test_time_intervals_calculation():
    """测试时间间隔计算的正确性"""
    hit_merged_components = create_test_hit_merged_components()
    hit_threshold = create_test_hit_threshold()

    # 测试 merged 201（包含 hit 2, 3, 4）
    df = get_hits_for_merged(201, hit_merged_components, hit_threshold)

    assert len(df) == 3

    # 第一行的时间间隔为 NaN
    assert pd.isna(df.iloc[0]["dt_start_to_start_ns"])
    assert pd.isna(df.iloc[0]["dt_end_to_start_ns"])

    # 第二行和第三行的时间间隔应该是 1.0 ns（因为每个 hit 间隔 1000 ps）
    assert df.iloc[1]["dt_start_to_start_ns"] == pytest.approx(1.0)
    assert df.iloc[2]["dt_start_to_start_ns"] == pytest.approx(1.0)
