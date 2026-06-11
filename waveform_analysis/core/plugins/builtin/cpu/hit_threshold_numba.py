"""Numba kernels for ThresholdHitPlugin ragged records backend."""

from numba import njit
import numpy as np


@njit(cache=True, nogil=True)
def count_ragged_hits(
    wave_pool,
    wave_offsets,
    record_lengths,
    baselines,
    thresholds,
    positive_mask,
    start_idx,
    end_idx,
):
    counts = np.zeros(end_idx - start_idx, dtype=np.int64)
    for local_i in range(end_idx - start_idx):
        record_i = start_idx + local_i
        offset = int(wave_offsets[record_i])
        length = int(record_lengths[record_i])
        if length <= 0:
            continue

        baseline = float(baselines[record_i])
        threshold = float(thresholds[record_i])
        positive = bool(positive_mask[record_i])
        threshold_level = baseline + threshold if positive else baseline - threshold
        in_hit = False
        n_hits = 0

        for sample_i in range(length):
            value = float(wave_pool[offset + sample_i])
            is_hit = value >= threshold_level if positive else value <= threshold_level
            if is_hit and not in_hit:
                in_hit = True
            elif in_hit and not is_hit:
                n_hits += 1
                in_hit = False

        if in_hit:
            n_hits += 1
        counts[local_i] = n_hits
    return counts


@njit(cache=True, nogil=True)
def fill_ragged_hits(
    wave_pool,
    wave_offsets,
    record_lengths,
    baselines,
    thresholds,
    positive_mask,
    timestamps,
    boards,
    channels,
    record_ids,
    dt_values,
    left_extension,
    right_extension,
    start_idx,
    end_idx,
    chunk_offsets,
    positions,
    edge_starts,
    edge_ends,
    widths,
    dts,
    hit_timestamps,
    hit_boards,
    hit_channels,
    hit_record_ids,
):
    for local_i in range(end_idx - start_idx):
        record_i = start_idx + local_i
        offset = int(wave_offsets[record_i])
        length = int(record_lengths[record_i])
        if length <= 0:
            continue

        baseline = float(baselines[record_i])
        threshold = float(thresholds[record_i])
        positive = bool(positive_mask[record_i])
        threshold_level = baseline + threshold if positive else baseline - threshold
        write_idx = int(chunk_offsets[local_i])
        hit_start = 0
        in_hit = False

        for sample_i in range(length):
            value = float(wave_pool[offset + sample_i])
            is_hit = value >= threshold_level if positive else value <= threshold_level
            if is_hit and not in_hit:
                hit_start = sample_i
                in_hit = True
            elif in_hit and not is_hit:
                seg_start = hit_start - left_extension
                if seg_start < 0:
                    seg_start = 0
                seg_end = sample_i + right_extension
                if seg_end > length:
                    seg_end = length
                if seg_end < seg_start:
                    seg_end = seg_start

                pos = (hit_start + sample_i - 1) // 2
                dt_ns = int(dt_values[record_i])
                positions[write_idx] = pos
                edge_starts[write_idx] = seg_start
                edge_ends[write_idx] = seg_end
                widths[write_idx] = float(seg_end - seg_start)
                dts[write_idx] = dt_ns
                hit_timestamps[write_idx] = int(timestamps[record_i]) + pos * dt_ns * 1000
                hit_boards[write_idx] = int(boards[record_i])
                hit_channels[write_idx] = int(channels[record_i])
                hit_record_ids[write_idx] = int(record_ids[record_i])
                write_idx += 1
                in_hit = False

        if in_hit:
            seg_start = hit_start - left_extension
            if seg_start < 0:
                seg_start = 0
            seg_end = length + right_extension
            if seg_end > length:
                seg_end = length
            if seg_end < seg_start:
                seg_end = seg_start

            pos = (hit_start + length - 1) // 2
            dt_ns = int(dt_values[record_i])
            positions[write_idx] = pos
            edge_starts[write_idx] = seg_start
            edge_ends[write_idx] = seg_end
            widths[write_idx] = float(seg_end - seg_start)
            dts[write_idx] = dt_ns
            hit_timestamps[write_idx] = int(timestamps[record_i]) + pos * dt_ns * 1000
            hit_boards[write_idx] = int(boards[record_i])
            hit_channels[write_idx] = int(channels[record_i])
            hit_record_ids[write_idx] = int(record_ids[record_i])


@njit(cache=True, nogil=True)
def batch_prefilter_records(
    wave_pool,
    wave_offsets,
    record_lengths,
    baselines,
    thresholds,
    positive_mask,
):
    """批量预筛选 records，返回通过阈值检查的 mask。

    使用 min/max 快速判断 record 是否可能包含 hit，避免逐样本扫描。

    Args:
        wave_pool: 波形数据池
        wave_offsets: 每条 record 在 wave_pool 中的起始偏移
        record_lengths: 每条 record 的长度
        baselines: 基线数组
        thresholds: 阈值数组
        positive_mask: 极性掩码（True=正极性）

    Returns:
        Boolean mask，True 表示该 record 可能包含 hit
    """
    n_records = len(record_lengths)
    pass_mask = np.zeros(n_records, dtype=np.bool_)

    for i in range(n_records):
        offset = int(wave_offsets[i])
        length = int(record_lengths[i])

        if length <= 0:
            continue

        # 计算阈值水平
        baseline = float(baselines[i])
        threshold = float(thresholds[i])
        positive = bool(positive_mask[i])

        # 找到 wave 的 min/max
        wave_min = float(wave_pool[offset])
        wave_max = float(wave_pool[offset])

        for j in range(1, length):
            val = float(wave_pool[offset + j])
            if val < wave_min:
                wave_min = val
            if val > wave_max:
                wave_max = val

        # 检查是否过阈
        if positive:
            threshold_level = baseline + threshold
            if wave_max >= threshold_level:
                pass_mask[i] = True
        else:
            threshold_level = baseline - threshold
            if wave_min <= threshold_level:
                pass_mask[i] = True

    return pass_mask


@njit(cache=True, nogil=True)
def contiguous_regions_numba(indices):
    """Numba 加速的连续区域查找。

    从排序的索引数组中找到连续区域的起始和结束位置。

    Args:
        indices: 排序的索引数组

    Returns:
        (starts, ends): 半开区间 [start, end) 的起始和结束数组
    """
    if len(indices) == 0:
        return np.empty(0, dtype=np.int64), np.empty(0, dtype=np.int64)

    # 计算有多少个区域
    n_regions = 1
    for i in range(1, len(indices)):
        if indices[i] - indices[i - 1] > 1:
            n_regions += 1

    starts = np.empty(n_regions, dtype=np.int64)
    ends = np.empty(n_regions, dtype=np.int64)

    region_idx = 0
    starts[0] = indices[0]

    for i in range(1, len(indices)):
        if indices[i] - indices[i - 1] > 1:
            # 当前区域结束
            ends[region_idx] = indices[i - 1] + 1
            region_idx += 1
            # 新区域开始
            starts[region_idx] = indices[i]

    # 最后一个区域
    ends[region_idx] = indices[-1] + 1

    return starts, ends
