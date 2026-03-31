"""
Records + wave_pool utilities.

This module provides a lightweight event index (records) paired with a
contiguous wave_pool for variable-length waveforms.
"""

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from waveform_analysis.core.foundation.utils import exporter
from waveform_analysis.core.hardware.channel import (
    HardwareChannel,
    group_indices_by_hardware_channel,
)
from waveform_analysis.core.processing.dtypes import (
    EVENTS_DTYPE as _EVENTS_DTYPE,
)
from waveform_analysis.core.processing.dtypes import (
    RECORDS_DTYPE as _RECORDS_DTYPE,
)

export, __all__ = exporter()

RECORDS_DTYPE = export(_RECORDS_DTYPE, name="RECORDS_DTYPE")
EVENTS_DTYPE = export(_EVENTS_DTYPE, name="EVENTS_DTYPE")


@export
@dataclass
class RecordsBundle:
    records: np.ndarray
    wave_pool: np.ndarray


EventsBundle = export(RecordsBundle, name="EventsBundle")


def _clip_wave_to_uint16(wave: np.ndarray) -> np.ndarray:
    wave = np.asarray(wave)
    if wave.dtype == np.uint16:
        return wave
    return wave.astype(np.uint16, copy=False)


def _records_sort_order(records: np.ndarray) -> np.ndarray:
    """Return a stable global sort order for final records output."""
    seq = np.arange(len(records), dtype=np.int64)
    return np.lexsort(
        (seq, records["channel"], records["board"], records["pid"], records["timestamp"])
    )


@export
def split_by_hardware_channel(st_waveforms: np.ndarray) -> list[tuple[HardwareChannel, np.ndarray]]:
    """Split a structured array into per-hardware-channel views."""
    if st_waveforms is None or len(st_waveforms) == 0:
        return []
    if not isinstance(st_waveforms, np.ndarray) or st_waveforms.dtype.names is None:
        raise ValueError("st_waveforms must be a structured numpy array")
    if "board" not in st_waveforms.dtype.names or "channel" not in st_waveforms.dtype.names:
        raise ValueError("st_waveforms missing required 'board'/'channel' fields")

    groups = group_indices_by_hardware_channel(st_waveforms["board"], st_waveforms["channel"])
    return [(hw_channel, st_waveforms[indices]) for hw_channel, indices in groups.items()]


@export
def split_by_channel(st_waveforms: np.ndarray) -> list[tuple[int, np.ndarray]]:
    """Backward-compatible helper for single-board inputs only."""
    groups = split_by_hardware_channel(st_waveforms)
    if any(hw_channel.board != 0 for hw_channel, _ in groups):
        raise ValueError(
            "split_by_channel no longer supports multi-board data; use "
            "split_by_hardware_channel instead."
        )
    return [(hw_channel.channel, group) for hw_channel, group in groups]


def _build_records_from_wave_list(
    waves: Sequence[tuple[int, int, int, int, int, np.ndarray]],
    default_dt_ns: int,
) -> RecordsBundle:
    if not waves:
        return RecordsBundle(np.zeros(0, dtype=RECORDS_DTYPE), np.zeros(0, dtype=np.uint16))

    total_records = len(waves)
    records = np.zeros(total_records, dtype=RECORDS_DTYPE)
    source_idx = np.arange(total_records, dtype=np.int64)

    for i, (board, channel, timestamp_ps, baseline, flags, waveform) in enumerate(waves):
        records["timestamp"][i] = timestamp_ps
        records["pid"][i] = 0
        records["board"][i] = board
        records["channel"][i] = channel
        records["baseline"][i] = baseline
        records["baseline_upstream"][i] = np.nan
        records["polarity"][i] = "unknown"
        records["dt"][i] = np.int32(default_dt_ns)
        records["trigger_type"][i] = 0
        records["flags"][i] = np.uint32(flags)
        length = int(len(waveform))
        if length > np.iinfo(np.int32).max:
            raise ValueError("event_length exceeds int32 range")
        records["event_length"][i] = np.int32(length)
        records["time"][i] = int(timestamp_ps // 1000)

    order = _records_sort_order(records)
    records = records[order]
    source_idx = source_idx[order]

    total_samples = int(records["event_length"].astype(np.int64, copy=False).sum())
    wave_pool = np.zeros(total_samples, dtype=np.uint16)

    wave_cursor = 0
    for idx in range(total_records):
        wave = waves[int(source_idx[idx])][5]
        length = int(records["event_length"][idx])
        if length > 0:
            wave_pool[wave_cursor : wave_cursor + length] = _clip_wave_to_uint16(wave[:length])
        records["wave_offset"][idx] = wave_cursor
        wave_cursor += length

    records["record_id"] = np.arange(total_records, dtype=np.int64)
    return RecordsBundle(records=records, wave_pool=wave_pool)


def _build_records_from_channels(
    channels: Sequence[tuple[np.ndarray, HardwareChannel]], default_dt_ns: int
) -> RecordsBundle:
    if not channels:
        return RecordsBundle(np.zeros(0, dtype=RECORDS_DTYPE), np.zeros(0, dtype=np.uint16))

    total_records = sum(len(ch) for ch, _ in channels)
    if total_records == 0:
        return RecordsBundle(np.zeros(0, dtype=RECORDS_DTYPE), np.zeros(0, dtype=np.uint16))

    records = np.zeros(total_records, dtype=RECORDS_DTYPE)
    source_channel = np.zeros(total_records, dtype=np.int32)
    source_row = np.zeros(total_records, dtype=np.int64)
    source_record_id = np.full(total_records, -1, dtype=np.int64)

    cursor = 0
    for local_idx, (ch, hw_channel) in enumerate(channels):
        count = len(ch)
        if count == 0:
            continue

        if "timestamp" in ch.dtype.names:
            records["timestamp"][cursor : cursor + count] = ch["timestamp"]
        else:
            records["timestamp"][cursor : cursor + count] = 0

        records["pid"][cursor : cursor + count] = 0

        if "channel" in ch.dtype.names:
            records["channel"][cursor : cursor + count] = ch["channel"]
        else:
            records["channel"][cursor : cursor + count] = hw_channel.channel
        if "board" in ch.dtype.names:
            records["board"][cursor : cursor + count] = ch["board"].astype(np.int16, copy=False)
        else:
            records["board"][cursor : cursor + count] = hw_channel.board

        if "baseline" in ch.dtype.names:
            records["baseline"][cursor : cursor + count] = ch["baseline"]
        else:
            records["baseline"][cursor : cursor + count] = 0.0

        if "baseline_upstream" in ch.dtype.names:
            records["baseline_upstream"][cursor : cursor + count] = ch["baseline_upstream"]
        else:
            records["baseline_upstream"][cursor : cursor + count] = np.nan

        if "polarity" in ch.dtype.names:
            records["polarity"][cursor : cursor + count] = ch["polarity"]
        else:
            records["polarity"][cursor : cursor + count] = "unknown"

        if "event_length" in ch.dtype.names:
            lengths = ch["event_length"].astype(np.int64, copy=False)
            if lengths.size and lengths.max() > np.iinfo(np.int32).max:
                raise ValueError("event_length exceeds int32 range")
            records["event_length"][cursor : cursor + count] = lengths.astype(np.int32, copy=False)
        elif "wave" in ch.dtype.names:
            wave_len = ch["wave"].shape[1]
            records["event_length"][cursor : cursor + count] = np.int32(wave_len)
        else:
            records["event_length"][cursor : cursor + count] = 0

        if "dt" in ch.dtype.names:
            records["dt"][cursor : cursor + count] = ch["dt"].astype(np.int32, copy=False)
        else:
            records["dt"][cursor : cursor + count] = np.int32(default_dt_ns)

        if "trigger_type" in ch.dtype.names:
            records["trigger_type"][cursor : cursor + count] = ch["trigger_type"].astype(
                np.int16, copy=False
            )
        else:
            records["trigger_type"][cursor : cursor + count] = 0

        if "flags" in ch.dtype.names:
            records["flags"][cursor : cursor + count] = ch["flags"].astype(np.uint32, copy=False)
        else:
            records["flags"][cursor : cursor + count] = 0

        if "time" in ch.dtype.names:
            records["time"][cursor : cursor + count] = ch["time"]
        else:
            records["time"][cursor : cursor + count] = (
                records["timestamp"][cursor : cursor + count] // 1000
            )
        if "record_id" in ch.dtype.names:
            source_record_id[cursor : cursor + count] = ch["record_id"].astype(np.int64, copy=False)

        source_channel[cursor : cursor + count] = local_idx
        source_row[cursor : cursor + count] = np.arange(count, dtype=np.int64)
        cursor += count

    order = _records_sort_order(records)
    records = records[order]
    source_channel = source_channel[order]
    source_row = source_row[order]
    source_record_id = source_record_id[order]
    if np.all(source_record_id >= 0):
        records["record_id"] = source_record_id
    else:
        records["record_id"] = np.arange(total_records, dtype=np.int64)

    adjusted_lengths = np.zeros(total_records, dtype=np.int64)
    total_samples = 0
    for idx in range(total_records):
        length = int(records["event_length"][idx])
        if length < 0:
            length = 0
        ch = channels[int(source_channel[idx])][0]
        if "wave" not in ch.dtype.names:
            raise ValueError("st_waveforms missing 'wave' field required for wave_pool")
        wave = ch["wave"][int(source_row[idx])]
        max_len = wave.shape[-1]
        if length > max_len:
            length = max_len
        adjusted_lengths[idx] = length
        total_samples += length

    records["event_length"] = adjusted_lengths.astype(np.int32, copy=False)

    wave_pool = np.zeros(total_samples, dtype=np.uint16)
    wave_cursor = 0
    for idx in range(total_records):
        length = int(adjusted_lengths[idx])
        ch = channels[int(source_channel[idx])][0]
        wave = ch["wave"][int(source_row[idx])]
        if length > 0:
            wave_pool[wave_cursor : wave_cursor + length] = _clip_wave_to_uint16(wave[:length])
        records["wave_offset"][idx] = wave_cursor
        wave_cursor += length

    return RecordsBundle(records=records, wave_pool=wave_pool)


@export
def build_records_from_st_waveforms(
    st_waveforms: np.ndarray,
    default_dt_ns: int = 1,
) -> RecordsBundle:
    """
    Build records + wave_pool from st_waveforms.

    Baseline implementation: single pass, sorted by (timestamp, pid, board, channel).
    """
    channels = [(arr, hw_channel) for hw_channel, arr in split_by_hardware_channel(st_waveforms)]
    return _build_records_from_channels(channels, default_dt_ns=default_dt_ns)


@export
def build_records_from_v1725_files(
    file_paths: list[str],
    dt_ns: int,
) -> RecordsBundle:
    if not file_paths:
        return RecordsBundle(np.zeros(0, dtype=RECORDS_DTYPE), np.zeros(0, dtype=np.uint16))

    from waveform_analysis.utils.formats import get_adapter

    adapter = get_adapter("v1725")
    reader = adapter.format_reader
    if not hasattr(reader, "iter_waves"):
        raise RuntimeError("V1725 adapter does not provide iter_waves")

    parts = []
    for file_path in file_paths:
        waves = []
        for wave in reader.iter_waves([file_path]):
            timestamp_ps = int(
                adapter.normalize_timestamp_to_ps(np.array([wave.timestamp]), dt_ns=dt_ns)[0]
            )
            flags = 1 if wave.trunc else 0
            waves.append(
                (int(wave.board), wave.channel, timestamp_ps, wave.baseline, flags, wave.waveform)
            )
        if waves:
            parts.append(_build_records_from_wave_list(waves, default_dt_ns=dt_ns))

    if not parts:
        return RecordsBundle(np.zeros(0, dtype=RECORDS_DTYPE), np.zeros(0, dtype=np.uint16))
    if len(parts) == 1:
        return parts[0]
    return merge_records_parts(parts)


@export
def merge_records_parts(parts: Sequence[RecordsBundle]) -> RecordsBundle:
    """
    Merge sorted records parts and build a global wave_pool.

    Each part must have records sorted by (timestamp, pid, board, channel).
    """
    if not parts:
        return RecordsBundle(np.zeros(0, dtype=RECORDS_DTYPE), np.zeros(0, dtype=np.uint16))

    total_records = sum(len(part.records) for part in parts)
    if total_records == 0:
        return RecordsBundle(np.zeros(0, dtype=RECORDS_DTYPE), np.zeros(0, dtype=np.uint16))

    total_samples = 0
    for part in parts:
        if len(part.records) > 0:
            total_samples += int(part.records["event_length"].astype(np.int64, copy=False).sum())

    records_out = np.zeros(total_records, dtype=RECORDS_DTYPE)
    wave_pool_out = np.zeros(total_samples, dtype=np.uint16)

    import heapq

    heap = []
    for part_idx, part in enumerate(parts):
        if len(part.records) == 0:
            continue
        rec = part.records[0]
        key = (
            int(rec["timestamp"]),
            int(rec["pid"]),
            int(rec["board"]),
            int(rec["channel"]),
            part_idx,
            0,
        )
        heapq.heappush(heap, key)

    out_idx = 0
    wave_cursor = 0
    while heap:
        _, _, _, _, part_idx, row_idx = heapq.heappop(heap)
        part = parts[part_idx]
        rec = part.records[row_idx]
        length = int(rec["event_length"])
        if length < 0:
            length = 0

        if length > 0:
            offset = int(rec["wave_offset"])
            wave_pool_out[wave_cursor : wave_cursor + length] = part.wave_pool[
                offset : offset + length
            ]

        records_out[out_idx] = rec
        records_out[out_idx]["wave_offset"] = wave_cursor
        out_idx += 1
        wave_cursor += length

        next_row = row_idx + 1
        if next_row < len(part.records):
            next_rec = part.records[next_row]
            key = (
                int(next_rec["timestamp"]),
                int(next_rec["pid"]),
                int(next_rec["board"]),
                int(next_rec["channel"]),
                part_idx,
                next_row,
            )
            heapq.heappush(heap, key)

    record_ids = records_out["record_id"].astype(np.int64, copy=False)
    if len(np.unique(record_ids)) != len(record_ids):
        records_out["record_id"] = np.arange(total_records, dtype=np.int64)
    return RecordsBundle(records=records_out, wave_pool=wave_pool_out)


@export
def build_records_from_st_waveforms_sharded(
    st_waveforms: np.ndarray,
    part_size: int = 200_000,
    default_dt_ns: int = 1,
) -> RecordsBundle:
    """
    Build records + wave_pool using sharded parts and k-way merge.

    part_size controls the max number of events per part. If part_size <= 0 or
    total records <= part_size, this falls back to the baseline builder.
    """
    if part_size <= 0:
        return build_records_from_st_waveforms(st_waveforms, default_dt_ns=default_dt_ns)

    total_records = len(st_waveforms)
    if total_records <= part_size:
        return build_records_from_st_waveforms(st_waveforms, default_dt_ns=default_dt_ns)

    parts: list[RecordsBundle] = []
    for hw_channel, ch in split_by_hardware_channel(st_waveforms):
        count = len(ch)
        if count == 0:
            continue
        start = 0
        while start < count:
            stop = min(count, start + part_size)
            part = _build_records_from_channels(
                [(ch[start:stop], hw_channel)],
                default_dt_ns=default_dt_ns,
            )
            if len(part.records) > 0:
                parts.append(part)
            start = stop

    if not parts:
        return RecordsBundle(np.zeros(0, dtype=RECORDS_DTYPE), np.zeros(0, dtype=np.uint16))
    if len(parts) == 1:
        return parts[0]
    return merge_records_parts(parts)
