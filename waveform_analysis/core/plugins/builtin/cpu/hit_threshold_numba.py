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
