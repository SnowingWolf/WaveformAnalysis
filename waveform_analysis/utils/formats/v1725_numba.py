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
