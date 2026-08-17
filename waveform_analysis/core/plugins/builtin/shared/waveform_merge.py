"""Canonical absolute-time merging for records-backed waveform segments."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import numpy as np


class WaveformOverlapConflictError(ValueError):
    """Raised when one hardware channel has unequal samples at one absolute time."""


def _empty_result(*, dense: bool) -> dict[str, Any]:
    return {
        "waveform": np.zeros(0, dtype=np.float32),
        "abs_time_ps": np.zeros(0, dtype=np.int64),
        "dt": 0,
        "dense": dense,
    }


def merge_waveform_segments(
    segments: Iterable[dict[str, Any]],
    *,
    sum_channels: bool,
    dense: bool,
    context: str = "waveform",
) -> dict[str, Any]:
    """Merge waveform segments on ``(board, channel, abs_time_ps)``.

    Equal float32 samples on the same hardware channel and absolute time are
    duplicate observations and are retained once.  Unequal observations are
    rejected.  When ``sum_channels`` is true, the already-deduplicated channel
    samples are summed by absolute time.  ``dense`` fills unobserved time bins
    with zero after the channel merge.
    """

    materialized: list[dict[str, Any]] = []
    for seg in segments:
        values = np.asarray(seg.get("waveform", ()), dtype=np.float32)
        times = np.asarray(seg.get("abs_time_ps", ()), dtype=np.int64)
        if values.ndim != 1 or times.ndim != 1 or len(values) != len(times):
            raise ValueError(
                f"{context} segment waveform/time lengths differ: " f"{len(values)} != {len(times)}"
            )
        if not np.all(np.isfinite(values)):
            raise ValueError(f"{context} contains non-finite waveform samples")
        if len(values) == 0:
            continue
        materialized.append({**seg, "waveform": values, "abs_time_ps": times})
    if not materialized:
        return _empty_result(dense=dense)

    dts = np.asarray([int(seg.get("dt", 0)) for seg in materialized], dtype=np.int64)
    if np.any(dts <= 0):
        raise ValueError(f"{context} requires positive dt; got {dts.tolist()}")
    if np.any(dts != dts[0]):
        raise ValueError(f"{context} has mixed dt values: {dts.tolist()}")
    dt_ns = int(dts[0])
    dt_ps = dt_ns * 1000

    values_parts: list[np.ndarray] = []
    times_parts: list[np.ndarray] = []
    boards_parts: list[np.ndarray] = []
    channels_parts: list[np.ndarray] = []
    record_parts: list[np.ndarray] = []
    merged_parts: list[np.ndarray] = []

    for seg in materialized:
        values = seg["waveform"]
        times = seg["abs_time_ps"]
        if len(times) > 1 and np.any(np.diff(times) != dt_ps):
            raise ValueError(f"{context} segment is not aligned to its dt={dt_ns} ns grid")

        values_parts.append(values)
        times_parts.append(times)
        boards_parts.append(np.full(len(values), int(seg.get("board", -1)), dtype=np.int16))
        channels_parts.append(np.full(len(values), int(seg.get("channel", -1)), dtype=np.int16))
        record_parts.append(np.full(len(values), int(seg.get("record_id", -1)), dtype=np.int64))
        merged_parts.append(np.full(len(values), int(seg.get("merged_index", -1)), dtype=np.int64))

    values = np.concatenate(values_parts)
    times = np.concatenate(times_parts)
    boards = np.concatenate(boards_parts)
    channels = np.concatenate(channels_parts)
    record_ids = np.concatenate(record_parts)
    merged_indices = np.concatenate(merged_parts)

    order = np.lexsort((times, channels, boards))
    values = values[order]
    times = times[order]
    boards = boards[order]
    channels = channels[order]
    record_ids = record_ids[order]
    merged_indices = merged_indices[order]

    group_start = np.r_[
        True,
        (boards[1:] != boards[:-1]) | (channels[1:] != channels[:-1]) | (times[1:] != times[:-1]),
    ]
    starts = np.flatnonzero(group_start)
    ends = np.r_[starts[1:], len(values)]
    for start, end in zip(starts, ends, strict=True):
        if end - start <= 1:
            continue
        first_value = values[start]
        mismatch = np.flatnonzero(
            values[start + 1 : end].view(np.uint32) != first_value.view(np.uint32)
        )
        if len(mismatch) == 0:
            continue
        other = start + 1 + int(mismatch[0])
        raise WaveformOverlapConflictError(
            f"{context} has conflicting overlap at board={int(boards[start])}, "
            f"channel={int(channels[start])}, abs_time_ps={int(times[start])}: "
            f"value={float(values[start])} (record_id={int(record_ids[start])}, "
            f"merged_index={int(merged_indices[start])}) != "
            f"value={float(values[other])} (record_id={int(record_ids[other])}, "
            f"merged_index={int(merged_indices[other])})"
        )

    keep = starts
    values = values[keep]
    times = times[keep]
    boards = boards[keep]
    channels = channels[keep]

    if sum_channels:
        order = np.argsort(times, kind="stable")
        values = values[order]
        times = times[order]
        time_starts = np.r_[True, times[1:] != times[:-1]]
        time_groups = np.flatnonzero(time_starts)
        values = np.add.reduceat(values.astype(np.float64), time_groups).astype(np.float32)
        times = times[time_groups]
    else:
        hardware_keys = np.unique(np.column_stack((boards, channels)), axis=0)
        if len(hardware_keys) != 1:
            raise ValueError(
                f"{context} expected one hardware channel, got "
                f"{[tuple(map(int, row)) for row in hardware_keys]}"
            )
        order = np.argsort(times, kind="stable")
        values = values[order]
        times = times[order]

    if len(times) > 1 and np.any(np.diff(times) <= 0):
        raise AssertionError(f"{context} produced a non-increasing absolute time axis")

    if len(times):
        relative = times - int(times[0])
        if np.any(relative % dt_ps != 0):
            raise ValueError(f"{context} samples are not aligned to a common dt grid")

    if dense and len(times):
        indices = (relative // dt_ps).astype(np.int64)
        dense_values = np.zeros(int(indices[-1]) + 1, dtype=np.float32)
        dense_values[indices] = values
        values = dense_values
        times = int(times[0]) + np.arange(len(values), dtype=np.int64) * dt_ps

    return {
        "waveform": values.astype(np.float32, copy=False),
        "abs_time_ps": times.astype(np.int64, copy=False),
        "dt": dt_ns,
        "dense": dense,
    }


__all__ = ["WaveformOverlapConflictError", "merge_waveform_segments"]
