"""Tests for chunk_utils module."""

import numpy as np
import pytest

from tests.utils import make_test_data, make_test_dtype
from waveform_analysis.core.processing.chunk import (
    DT_FIELD,
    ENDTIME_FIELD,
    LENGTH_FIELD,
    # 常量
    TIME_FIELD,
    # 数据类
    ChunkInfo,
    ValidationResult,
    add_endtime_field,
    check_chunk_boundaries,
    check_chunk_continuity,
    # 检查函数
    check_monotonic,
    check_no_overlap,
    check_sorted_by_time,
    clip_to_time_range,
    # Endtime 操作
    compute_endtime,
    concat_sorted,
    get_endtime,
    # 时间范围操作
    get_time_range,
    merge_chunks,
    # Rechunk
    rechunk,
    samples_to_time,
    select_time_range,
    # 工具函数
    sort_by_time,
    split_by_breaks,
    split_by_count,
    # Chunk 分割
    split_by_time,
    time_to_samples,
    validate_endtime,
)


# =============================================================================
# ChunkInfo 测试
# =============================================================================


class TestChunkInfo:
    def test_creation(self):
        info = ChunkInfo(start_time=0, end_time=1000, n_records=10)
        assert info.start_time == 0
        assert info.end_time == 1000
        assert info.n_records == 10
        assert info.duration == 1000

    def test_overlaps(self):
        info1 = ChunkInfo(start_time=0, end_time=1000, n_records=10)
        info2 = ChunkInfo(start_time=500, end_time=1500, n_records=10)
        info3 = ChunkInfo(start_time=1000, end_time=2000, n_records=10)

        assert info1.overlaps(info2)
        assert not info1.overlaps(info3)  # 边界相接不算重叠

    def test_contains(self):
        info = ChunkInfo(start_time=100, end_time=200, n_records=10)
        assert info.contains(100)
        assert info.contains(150)
        assert not info.contains(200)  # end is exclusive
        assert not info.contains(50)


class TestValidationResult:
    def test_bool_conversion(self):
        valid = ValidationResult(is_valid=True)
        invalid = ValidationResult(is_valid=False, errors=["error"])

        assert valid
        assert not invalid

    def test_raise_if_invalid(self):
        valid = ValidationResult(is_valid=True)
        valid.raise_if_invalid()  # should not raise

        invalid = ValidationResult(is_valid=False, errors=["test error"])
        with pytest.raises(ValueError, match="test error"):
            invalid.raise_if_invalid()


# =============================================================================
# Endtime 测试
# =============================================================================


class TestEndtime:
    def test_compute_endtime(self):
        data = make_test_data(n=5, start_time=0, dt=10, length=100)
        endtime = compute_endtime(data)

        expected = data[TIME_FIELD] + data[DT_FIELD] * data[LENGTH_FIELD]
        np.testing.assert_array_equal(endtime, expected)

    def test_add_endtime_field(self):
        data = make_test_data(n=5, with_endtime=False)
        result = add_endtime_field(data)

        assert ENDTIME_FIELD in result.dtype.names
        expected = data[TIME_FIELD] + data[DT_FIELD] * data[LENGTH_FIELD]
        np.testing.assert_array_equal(result[ENDTIME_FIELD], expected)

    def test_add_endtime_field_already_exists(self):
        data = make_test_data(n=5, with_endtime=True)
        # 故意设置错误的 endtime
        data[ENDTIME_FIELD] = 0

        result = add_endtime_field(data)
        expected = data[TIME_FIELD] + data[DT_FIELD] * data[LENGTH_FIELD]
        np.testing.assert_array_equal(result[ENDTIME_FIELD], expected)

    def test_validate_endtime_correct(self):
        data = make_test_data(n=5, with_endtime=True)
        result = validate_endtime(data)

        assert result.is_valid
        assert result.stats["n_mismatch"] == 0

    def test_validate_endtime_mismatch(self):
        data = make_test_data(n=5, with_endtime=True)
        data[ENDTIME_FIELD][0] = 0  # 错误值

        result = validate_endtime(data)
        assert not result.is_valid
        assert result.stats["n_mismatch"] == 1

    def test_get_endtime_with_field(self):
        data = make_test_data(n=5, with_endtime=True)
        endtime = get_endtime(data)
        np.testing.assert_array_equal(endtime, data[ENDTIME_FIELD])

    def test_get_endtime_without_field(self):
        data = make_test_data(n=5, with_endtime=False)
        endtime = get_endtime(data)
        expected = compute_endtime(data)
        np.testing.assert_array_equal(endtime, expected)


# =============================================================================
# 单调性与重叠检查测试
# =============================================================================


class TestMonotonicCheck:
    def test_monotonic_increasing(self):
        data = make_test_data(n=10, gap=10)
        result = check_monotonic(data, TIME_FIELD)
        assert result.is_valid

    def test_monotonic_strict_with_equal(self):
        data = make_test_data(n=10, gap=0)
        # 创建相等的时间
        data[TIME_FIELD][2] = data[TIME_FIELD][1]

        result = check_monotonic(data, TIME_FIELD, strict=True)
        assert not result.is_valid

    def test_monotonic_decreasing(self):
        data = make_test_data(n=10)
        data[TIME_FIELD][5] = data[TIME_FIELD][0]  # 违反单调性

        result = check_monotonic(data, TIME_FIELD)
        assert not result.is_valid
        assert "decreasing" in result.errors[0]

    def test_empty_data(self):
        data = make_test_data(n=0)
        result = check_monotonic(data, TIME_FIELD)
        assert result.is_valid


class TestOverlapCheck:
    def test_no_overlap(self):
        data = make_test_data(n=5, gap=10)
        result = check_no_overlap(data)
        assert result.is_valid

    def test_with_overlap(self):
        data = make_test_data(n=5, gap=-100)  # 负间隙 = 重叠
        result = check_no_overlap(data)
        assert not result.is_valid
        assert result.stats["n_overlaps"] > 0

    def test_touching_no_overlap(self):
        # 边界相接但不重叠
        data = make_test_data(n=5, gap=0)
        result = check_no_overlap(data)
        assert result.is_valid


class TestSortedByTimeCheck:
    def test_sorted_no_overlap(self):
        data = make_test_data(n=5, gap=10)
        result = check_sorted_by_time(data)
        assert result.is_valid

    def test_unsorted(self):
        data = make_test_data(n=5)
        data[TIME_FIELD][2] = data[TIME_FIELD][0] - 100

        result = check_sorted_by_time(data)
        assert not result.is_valid


# =============================================================================
# 时间范围操作测试
# =============================================================================


class TestTimeRange:
    def test_get_time_range(self):
        data = make_test_data(n=5, start_time=100, dt=10, length=100)
        start, end = get_time_range(data)

        assert start == 100
        expected_end = 100 + 5 * (10 * 100)  # 最后一条记录的 endtime
        assert end == expected_end - 10 * 100 + 10 * 100  # 简化：最后记录 endtime

    def test_get_time_range_empty(self):
        data = make_test_data(n=0)
        start, end = get_time_range(data)
        assert start == 0
        assert end == 0

    def test_select_time_range_loose(self):
        data = make_test_data(n=10, start_time=0, dt=10, length=100, gap=0)
        # 每条记录占用 1000ns

        # 选择 500-2500 范围
        selected = select_time_range(data, start=500, end=2500, strict=False)
        # 应该包含有交集的记录
        assert len(selected) > 0
        assert all(get_endtime(selected) > 500)
        assert all(selected[TIME_FIELD] < 2500)

    def test_select_time_range_strict(self):
        data = make_test_data(n=10, start_time=0, dt=10, length=100, gap=0)

        # 严格模式
        selected = select_time_range(data, start=1000, end=5000, strict=True)
        assert len(selected) > 0
        assert all(selected[TIME_FIELD] >= 1000)
        assert all(get_endtime(selected) <= 5000)


class TestClipToTimeRange:
    def test_clip_no_change(self):
        data = make_test_data(n=5, start_time=1000, dt=10, length=100)
        # 范围足够大，不需要裁剪
        clipped = clip_to_time_range(data, start=0, end=100000)
        assert len(clipped) == len(data)

    def test_clip_start(self):
        data = make_test_data(n=5, start_time=0, dt=10, length=100)
        # 裁剪起始
        clipped = clip_to_time_range(data, start=500)

        # 第一条记录应该被裁剪
        assert all(clipped[TIME_FIELD] >= 500)

    def test_clip_end(self):
        data = make_test_data(n=5, start_time=0, dt=10, length=100)
        # 裁剪结束
        clipped = clip_to_time_range(data, end=500)

        # 所有 endtime 应该 <= 500
        assert all(get_endtime(clipped) <= 500)


# =============================================================================
# Chunk 分割测试
# =============================================================================


class TestSplitByTime:
    def test_split_by_time(self):
        data = make_test_data(n=20, start_time=0, dt=10, length=100, gap=0)
        # 每条记录 1000ns，共 20000ns

        chunks = list(split_by_time(data, chunk_duration_ns=5000))
        assert len(chunks) >= 4  # 至少 4 个 chunk

        # 验证每个 chunk
        for chunk_data, info in chunks:
            assert len(chunk_data) > 0
            assert info.n_records == len(chunk_data)


class TestSplitByCount:
    def test_split_by_count(self):
        data = make_test_data(n=25)

        chunks = list(split_by_count(data, chunk_size=10))
        assert len(chunks) == 3  # 10 + 10 + 5

        assert len(chunks[0][0]) == 10
        assert len(chunks[1][0]) == 10
        assert len(chunks[2][0]) == 5


class TestSplitByBreaks:
    def test_split_at_breaks(self):
        data = make_test_data(n=20, gap=100)
        data[TIME_FIELD] *= 1000
        data[DT_FIELD] *= 1000

        # 在中间插入大间隙
        data[TIME_FIELD][10:] += 2_000_000_000_000  # 2秒间隙（ps）

        chunks = list(split_by_breaks(data, break_threshold_ps=1_000_000_000_000))
        assert len(chunks) == 2


class TestMergeChunks:
    def test_merge_chunks(self):
        data = make_test_data(n=20)
        chunks = [c for c, _ in split_by_count(data, chunk_size=5)]

        merged = merge_chunks(iter(chunks))
        assert len(merged) == 20


# =============================================================================
# Rechunk 测试
# =============================================================================


class TestRechunk:
    def test_rechunk_combines_small(self):
        data = make_test_data(n=100)

        # 先分成小 chunk
        small_chunks = list(split_by_count(data, chunk_size=10))
        assert len(small_chunks) == 10

        # 重新分块
        rechunked = list(rechunk(iter(small_chunks), target_size=30))
        # 应该合并成更少的 chunk
        assert len(rechunked) < len(small_chunks)


# =============================================================================
# Chunk 边界检查测试
# =============================================================================


class TestChunkBoundaries:
    def test_valid_boundaries(self):
        data = make_test_data(n=5, start_time=100, dt=10, length=100)
        result = check_chunk_boundaries(data, chunk_start=100, chunk_end=10000)
        assert result.is_valid

    def test_before_start(self):
        data = make_test_data(n=5, start_time=0)
        result = check_chunk_boundaries(data, chunk_start=100, chunk_end=10000)
        assert not result.is_valid
        assert result.stats["n_before_start"] > 0

    def test_after_end(self):
        data = make_test_data(n=5, start_time=0)
        result = check_chunk_boundaries(data, chunk_start=0, chunk_end=100)
        assert not result.is_valid
        assert result.stats["n_after_end"] > 0


class TestChunkContinuity:
    def test_continuous_chunks(self):
        data = make_test_data(n=20, gap=0)
        chunks = list(split_by_count(data, chunk_size=5))

        result = check_chunk_continuity(chunks)
        assert result.is_valid

    def test_overlapping_chunks(self):
        data1 = make_test_data(n=5, start_time=0)
        data2 = make_test_data(n=5, start_time=0)  # 重叠

        info1 = ChunkInfo(start_time=0, end_time=5000, n_records=5)
        info2 = ChunkInfo(start_time=0, end_time=5000, n_records=5)

        result = check_chunk_continuity([(data1, info1), (data2, info2)])
        assert not result.is_valid
        assert result.stats["n_overlaps"] > 0


# =============================================================================
# 工具函数测试
# =============================================================================


class TestUtilityFunctions:
    def test_sort_by_time(self):
        data = make_test_data(n=10)
        # 打乱顺序
        shuffled = data.copy()
        np.random.shuffle(shuffled)

        sorted_data = sort_by_time(shuffled)
        result = check_monotonic(sorted_data, TIME_FIELD, strict=False)
        assert result.is_valid

    def test_concat_sorted(self):
        data1 = make_test_data(n=5, start_time=0)
        data2 = make_test_data(n=5, start_time=10000)

        # 故意以错误顺序传入
        result = concat_sorted([data2, data1])

        # 结果应该是排序的
        check_result = check_monotonic(result, TIME_FIELD, strict=False)
        assert check_result.is_valid

    def test_time_samples_conversion(self):
        dt_ns = 10
        time_ns = 1000

        samples = time_to_samples(time_ns, dt_ns)
        assert samples == 100

        back_to_time = samples_to_time(samples, dt_ns)
        assert back_to_time == time_ns
