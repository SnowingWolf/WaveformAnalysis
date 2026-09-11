"""Numba kernels for CAEN V1725 binary parsing."""

from __future__ import annotations

from numba import njit, prange
import numpy as np


@njit(cache=True, nogil=True)
def parse_channel_headers_numba(headers_data):
    """Parse V1725 12-byte channel headers."""
    n_headers = headers_data.shape[0]
    ch_sizes = np.empty(n_headers, dtype=np.uint32)
    timestamps = np.empty(n_headers, dtype=np.uint64)
    truncs = np.empty(n_headers, dtype=np.bool_)
    baselines = np.empty(n_headers, dtype=np.uint16)

    for i in range(n_headers):
        ch_sizes[i] = (
            np.uint32(headers_data[i, 0])
            | (np.uint32(headers_data[i, 1]) << 8)
            | ((np.uint32(headers_data[i, 2]) & np.uint32(0x3F)) << 16)
        )
        timestamps[i] = (
            np.uint64(headers_data[i, 4])
            | (np.uint64(headers_data[i, 5]) << 8)
            | (np.uint64(headers_data[i, 6]) << 16)
            | (np.uint64(headers_data[i, 7]) << 24)
            | (np.uint64(headers_data[i, 8]) << 32)
            | (np.uint64(headers_data[i, 9]) << 40)
        )
        truncs[i] = ((headers_data[i, 3] >> 6) & 1) == 1
        baselines[i] = np.uint16(headers_data[i, 10]) | (np.uint16(headers_data[i, 11]) << 8)

    return ch_sizes, timestamps, truncs, baselines


@njit(cache=True, nogil=True)
def fill_v1725_records_metadata_serial(
    timestamp_ticks,
    boards,
    channels,
    baselines,
    truncs,
    event_lengths,
    dt_ns,
    timestamp_ps,
    pid,
    board_out,
    channel_out,
    baseline_out,
    baseline_upstream,
    dt,
    trigger_type,
    flags,
    event_length_out,
    time_out,
):
    """Fill numeric V1725 records metadata fields serially."""
    for i in range(timestamp_ticks.shape[0]):
        ts_ps = np.int64(timestamp_ticks[i]) * np.int64(dt_ns) * np.int64(1000)
        timestamp_ps[i] = ts_ps
        pid[i] = 0
        board_out[i] = boards[i]
        channel_out[i] = channels[i]
        baseline_out[i] = np.float64(baselines[i])
        baseline_upstream[i] = np.nan
        dt[i] = np.int32(dt_ns)
        trigger_type[i] = 0
        flags[i] = np.uint32(1) if truncs[i] else np.uint32(0)
        event_length_out[i] = np.int32(event_lengths[i])
        time_out[i] = ts_ps // np.int64(1000)


@njit(cache=True, nogil=True, parallel=True)
def fill_v1725_records_metadata_parallel(
    timestamp_ticks,
    boards,
    channels,
    baselines,
    truncs,
    event_lengths,
    dt_ns,
    timestamp_ps,
    pid,
    board_out,
    channel_out,
    baseline_out,
    baseline_upstream,
    dt,
    trigger_type,
    flags,
    event_length_out,
    time_out,
):
    """Fill numeric V1725 records metadata fields with independent row writes."""
    for i in prange(timestamp_ticks.shape[0]):
        ts_ps = np.int64(timestamp_ticks[i]) * np.int64(dt_ns) * np.int64(1000)
        timestamp_ps[i] = ts_ps
        pid[i] = 0
        board_out[i] = boards[i]
        channel_out[i] = channels[i]
        baseline_out[i] = np.float64(baselines[i])
        baseline_upstream[i] = np.nan
        dt[i] = np.int32(dt_ns)
        trigger_type[i] = 0
        flags[i] = np.uint32(1) if truncs[i] else np.uint32(0)
        event_length_out[i] = np.int32(event_lengths[i])
        time_out[i] = ts_ps // np.int64(1000)


@njit(cache=True, nogil=True)
def parse_v1725_events_mmap(
    data: np.ndarray,  # uint8 array from mmap
    board_id: int,
) -> tuple:
    """
    Numba 加速的 V1725 二进制数据批量解析（用于 mmap）。

    两遍扫描策略：
    1. 第一遍：快速计数总 wave 数量
    2. 第二遍：解析所有元数据和波形偏移

    Args:
        data: 内存映射的 uint8 数组（完整文件内容）
        board_id: 板卡 ID

    Returns:
        (timestamps, boards, channels, truncs, baselines, waveform_offsets)
        waveform_offsets: (N, 2) 数组，每行为 (start_offset, byte_size)
    """
    data_len = len(data)

    # ==================== 第一遍扫描：计数 ====================
    n_waves = 0
    offset = 0

    while offset + 16 <= data_len:
        # 解析事件头（16 字节）
        mask_low = np.uint16(data[offset + 4])
        mask_high = np.uint16(data[offset + 11])
        channel_mask = mask_low | (mask_high << 8)

        # 计算活跃通道数
        n_channels = 0
        for bit in range(16):
            if (channel_mask >> bit) & 1:
                n_channels += 1

        offset += 16

        # 跳过所有通道数据
        for _ in range(n_channels):
            if offset + 12 > data_len:
                break

            # 读取通道大小
            ch_size = (
                np.uint32(data[offset])
                | (np.uint32(data[offset + 1]) << 8)
                | ((np.uint32(data[offset + 2]) & np.uint32(0x3F)) << 16)
            )
            sig_size = (ch_size - 3) << 2

            if offset + 12 + sig_size > data_len:
                break

            offset += 12 + sig_size
            n_waves += 1

    # ==================== 预分配输出数组 ====================
    timestamps = np.empty(n_waves, dtype=np.uint64)
    boards = np.full(n_waves, board_id, dtype=np.int16)
    channels = np.empty(n_waves, dtype=np.int16)
    truncs = np.empty(n_waves, dtype=np.bool_)
    baselines = np.empty(n_waves, dtype=np.uint16)
    waveform_offsets = np.empty((n_waves, 2), dtype=np.int64)  # (start, size)

    # ==================== 第二遍扫描：解析 ====================
    wave_idx = 0
    offset = 0

    while offset + 16 <= data_len and wave_idx < n_waves:
        # 解析事件头
        mask_low = np.uint16(data[offset + 4])
        mask_high = np.uint16(data[offset + 11])
        channel_mask = mask_low | (mask_high << 8)

        offset += 16

        # 解析每个活跃通道
        for ch_bit in range(16):
            if not ((channel_mask >> ch_bit) & 1):
                continue

            if offset + 12 > data_len or wave_idx >= n_waves:
                break

            # 解析通道头（12 字节）
            ch_size = (
                np.uint32(data[offset])
                | (np.uint32(data[offset + 1]) << 8)
                | ((np.uint32(data[offset + 2]) & np.uint32(0x3F)) << 16)
            )
            sig_size = (ch_size - 3) << 2

            if offset + 12 + sig_size > data_len:
                break

            # 解析 timestamp（6 字节，offset 4-9）
            timestamp = (
                np.uint64(data[offset + 4])
                | (np.uint64(data[offset + 5]) << 8)
                | (np.uint64(data[offset + 6]) << 16)
                | (np.uint64(data[offset + 7]) << 24)
                | (np.uint64(data[offset + 8]) << 32)
                | (np.uint64(data[offset + 9]) << 40)
            )

            # 解析 trunc 标志（offset 3, bit 6）
            trunc = ((data[offset + 3] >> 6) & 1) == 1

            # 解析 baseline（2 字节，offset 10-11）
            baseline = np.uint16(data[offset + 10]) | (np.uint16(data[offset + 11]) << 8)

            # 记录元数据
            timestamps[wave_idx] = timestamp
            channels[wave_idx] = ch_bit
            truncs[wave_idx] = trunc
            baselines[wave_idx] = baseline
            waveform_offsets[wave_idx, 0] = offset + 12
            waveform_offsets[wave_idx, 1] = sig_size

            offset += 12 + sig_size
            wave_idx += 1

    # 返回实际解析的数据（可能少于预分配）
    return (
        timestamps[:wave_idx],
        boards[:wave_idx],
        channels[:wave_idx],
        truncs[:wave_idx],
        baselines[:wave_idx],
        waveform_offsets[:wave_idx],
    )
