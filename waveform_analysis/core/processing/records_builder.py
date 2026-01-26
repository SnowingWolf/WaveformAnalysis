# -*- coding: utf-8 -*-
"""
Records + wave_pool utilities.

This module provides a lightweight event index (records) paired with a
contiguous wave_pool for variable-length waveforms.
"""

from dataclasses import dataclass
from typing import List, Sequence, Tuple

import numpy as np

from waveform_analysis.core.foundation.utils import exporter

export, __all__ = exporter()

RECORDS_DTYPE = export(
    np.dtype(
        [
            ("timestamp", "i8"),    # ADC timestamp (ps)
            ("pid", "i4"),          # partition id (tie-breaker)
            ("channel", "i2"),      # physical channel
            ("baseline", "f8"),     # baseline (match st_waveforms)
            ("event_id", "i8"),     # sequential id after sorting
            ("dt", "i4"),           # sample interval (ns, aligned to time)
            ("trigger_type", "i2"), # trigger type code
            ("flags", "u4"),        # bit flags
            ("wave_offset", "i8"),  # index in wave_pool
            ("event_length", "i4"), # waveform length in samples
            ("time", "i8"),         # system time (ns, optional semantics)
        ]
    ),
    name="RECORDS_DTYPE",
)
EVENTS_DTYPE = export(RECORDS_DTYPE, name="EVENTS_DTYPE")


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
    data = np.rint(wave).astype(np.int64, copy=False)
    data = np.clip(data, 0, np.iinfo(np.uint16).max)
    return data.astype(np.uint16, copy=False)


def _build_records_from_wave_list(
    waves: Sequence[Tuple[int, int, int, int, np.ndarray]],
    default_dt_ns: int,
) -> RecordsBundle:
    if not waves:
        return RecordsBundle(np.zeros(0, dtype=RECORDS_DTYPE), np.zeros(0, dtype=np.uint16))

    total_records = len(waves)
    records = np.zeros(total_records, dtype=RECORDS_DTYPE)
    source_idx = np.arange(total_records, dtype=np.int64)

    for i, (channel, timestamp_ps, baseline, flags, waveform) in enumerate(waves):
        records["timestamp"][i] = timestamp_ps
        records["pid"][i] = 0
        records["channel"][i] = channel
        records["baseline"][i] = baseline
        records["dt"][i] = np.int32(default_dt_ns)
        records["trigger_type"][i] = 0
        records["flags"][i] = np.uint32(flags)
        length = int(len(waveform))
        if length > np.iinfo(np.int32).max:
            raise ValueError("event_length exceeds int32 range")
        records["event_length"][i] = np.int32(length)
        records["time"][i] = int(timestamp_ps // 1000)

    seq = np.arange(total_records, dtype=np.int64)
    order = np.lexsort((seq, records["channel"], records["pid"], records["timestamp"]))
    records = records[order]
    source_idx = source_idx[order]

    total_samples = int(records["event_length"].astype(np.int64, copy=False).sum())
    wave_pool = np.zeros(total_samples, dtype=np.uint16)

    wave_cursor = 0
    for idx in range(total_records):
        wave = waves[int(source_idx[idx])][4]
        length = int(records["event_length"][idx])
        if length > 0:
            wave_pool[wave_cursor:wave_cursor + length] = _clip_wave_to_uint16(wave[:length])
        records["wave_offset"][idx] = wave_cursor
        wave_cursor += length

    records["event_id"] = np.arange(total_records, dtype=np.int64)
    return RecordsBundle(records=records, wave_pool=wave_pool)


def _build_records_from_channels(
    channels: Sequence[Tuple[np.ndarray, int]],
    default_dt_ns: int
) -> RecordsBundle:
    if not channels:
        return RecordsBundle(np.zeros(0, dtype=RECORDS_DTYPE), np.zeros(0, dtype=np.uint16))

    total_records = sum(len(ch) for ch, _ in channels)
    if total_records == 0:
        return RecordsBundle(np.zeros(0, dtype=RECORDS_DTYPE), np.zeros(0, dtype=np.uint16))

    records = np.zeros(total_records, dtype=RECORDS_DTYPE)
    source_channel = np.zeros(total_records, dtype=np.int32)
    source_row = np.zeros(total_records, dtype=np.int64)

    cursor = 0
    for local_idx, (ch, channel_fallback) in enumerate(channels):
        count = len(ch)
        if count == 0:
            continue

        if "timestamp" in ch.dtype.names:
            records["timestamp"][cursor:cursor + count] = ch["timestamp"]
        else:
            records["timestamp"][cursor:cursor + count] = 0

        records["pid"][cursor:cursor + count] = 0

        if "channel" in ch.dtype.names:
            records["channel"][cursor:cursor + count] = ch["channel"]
        else:
            records["channel"][cursor:cursor + count] = channel_fallback

        if "baseline" in ch.dtype.names:
            records["baseline"][cursor:cursor + count] = ch["baseline"]
        else:
            records["baseline"][cursor:cursor + count] = 0.0

        if "event_length" in ch.dtype.names:
            lengths = ch["event_length"].astype(np.int64, copy=False)
            if lengths.size and lengths.max() > np.iinfo(np.int32).max:
                raise ValueError("event_length exceeds int32 range")
            records["event_length"][cursor:cursor + count] = lengths.astype(np.int32, copy=False)
        elif "wave" in ch.dtype.names:
            wave_len = ch["wave"].shape[1]
            records["event_length"][cursor:cursor + count] = np.int32(wave_len)
        else:
            records["event_length"][cursor:cursor + count] = 0

        if "dt" in ch.dtype.names:
            records["dt"][cursor:cursor + count] = ch["dt"].astype(np.int32, copy=False)
        else:
            records["dt"][cursor:cursor + count] = np.int32(default_dt_ns)

        if "trigger_type" in ch.dtype.names:
            records["trigger_type"][cursor:cursor + count] = ch["trigger_type"].astype(
                np.int16, copy=False
            )
        else:
            records["trigger_type"][cursor:cursor + count] = 0

        if "flags" in ch.dtype.names:
            records["flags"][cursor:cursor + count] = ch["flags"].astype(
                np.uint32, copy=False
            )
        else:
            records["flags"][cursor:cursor + count] = 0

        if "time" in ch.dtype.names:
            records["time"][cursor:cursor + count] = ch["time"]
        else:
            records["time"][cursor:cursor + count] = records["timestamp"][cursor:cursor + count] // 1000

        source_channel[cursor:cursor + count] = local_idx
        source_row[cursor:cursor + count] = np.arange(count, dtype=np.int64)
        cursor += count

    seq = np.arange(total_records, dtype=np.int64)
    order = np.lexsort((seq, records["channel"], records["pid"], records["timestamp"]))
    records = records[order]
    records["event_id"] = np.arange(total_records, dtype=np.int64)
    source_channel = source_channel[order]
    source_row = source_row[order]

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
            wave_pool[wave_cursor:wave_cursor + length] = _clip_wave_to_uint16(wave[:length])
        records["wave_offset"][idx] = wave_cursor
        wave_cursor += length

    return RecordsBundle(records=records, wave_pool=wave_pool)


@export
def build_records_from_st_waveforms(
    st_waveforms: List[np.ndarray],
    default_dt_ns: int = 1,
) -> RecordsBundle:
    """
    Build records + wave_pool from st_waveforms.

    Baseline implementation: single pass, sorted by (timestamp, pid, channel).
    """
    channels = [(ch, idx) for idx, ch in enumerate(st_waveforms)]
    return _build_records_from_channels(channels, default_dt_ns=default_dt_ns)


@export
def build_records_from_v1725_files(
    file_paths: List[str],
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
            timestamp_ps = int(wave.timestamp) * int(dt_ns) * 1000
            flags = 1 if wave.trunc else 0
            waves.append((wave.channel, timestamp_ps, wave.baseline, flags, wave.waveform))
        if waves:
            parts.append(_build_records_from_wave_list(waves, default_dt_ns=dt_ns))

    if not parts:
        return RecordsBundle(np.zeros(0, dtype=RECORDS_DTYPE), np.zeros(0, dtype=np.uint16))
    if len(parts) == 1:
        return parts[0]
    return merge_records_parts(parts)


@export
def build_records_from_waveforms(
    waveforms: List[np.ndarray],
    dt_ns: int,
) -> RecordsBundle:
    if isinstance(waveforms, np.ndarray):
        waveforms = [waveforms]

    if not waveforms:
        return RecordsBundle(np.zeros(0, dtype=RECORDS_DTYPE), np.zeros(0, dtype=np.uint16))

    waves = []
    for ch in waveforms:
        if ch is None or len(ch) == 0:
            continue
        if ch.dtype.names is None or "wave" not in ch.dtype.names:
            raise ValueError("waveforms must contain structured arrays with 'wave' field")
        has_trunc = "trunc" in ch.dtype.names
        has_channel = "channel" in ch.dtype.names
        for rec in ch:
            timestamp_ps = int(rec["timestamp"]) * int(dt_ns) * 1000
            baseline = int(rec["baseline"]) if "baseline" in ch.dtype.names else 0
            flags = 1 if (has_trunc and bool(rec["trunc"])) else 0
            channel = int(rec["channel"]) if has_channel else 0
            waveform = np.asarray(rec["wave"])
            waves.append((channel, timestamp_ps, baseline, flags, waveform))

    return _build_records_from_wave_list(waves, default_dt_ns=dt_ns)


@export
def merge_records_parts(parts: Sequence[RecordsBundle]) -> RecordsBundle:
    """
    Merge sorted records parts and build a global wave_pool.

    Each part must have records sorted by (timestamp, pid, channel).
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
        key = (int(rec["timestamp"]), int(rec["pid"]), int(rec["channel"]), part_idx, 0)
        heapq.heappush(heap, key)

    out_idx = 0
    wave_cursor = 0
    while heap:
        _, _, _, part_idx, row_idx = heapq.heappop(heap)
        part = parts[part_idx]
        rec = part.records[row_idx]
        length = int(rec["event_length"])
        if length < 0:
            length = 0

        if length > 0:
            offset = int(rec["wave_offset"])
            wave_pool_out[wave_cursor:wave_cursor + length] = part.wave_pool[
                offset:offset + length
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
                int(next_rec["channel"]),
                part_idx,
                next_row,
            )
            heapq.heappush(heap, key)

    records_out["event_id"] = np.arange(total_records, dtype=np.int64)
    return RecordsBundle(records=records_out, wave_pool=wave_pool_out)


@export
def build_records_from_st_waveforms_sharded(
    st_waveforms: List[np.ndarray],
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

    total_records = sum(len(ch) for ch in st_waveforms)
    if total_records <= part_size:
        return build_records_from_st_waveforms(st_waveforms, default_dt_ns=default_dt_ns)

    parts: List[RecordsBundle] = []
    for ch_idx, ch in enumerate(st_waveforms):
        count = len(ch)
        if count == 0:
            continue
        start = 0
        while start < count:
            stop = min(count, start + part_size)
            part = _build_records_from_channels(
                [(ch[start:stop], ch_idx)],
                default_dt_ns=default_dt_ns,
            )
            if len(part.records) > 0:
                parts.append(part)
            start = stop

    if not parts:
        return RecordsBundle(np.zeros(0, dtype=RECORDS_DTYPE), np.zeros(0, dtype=np.uint16))
    if len(parts) == 1:
        return parts[0]
    merged = merge_records_parts(parts)
    merged.records["event_id"] = np.arange(len(merged.records), dtype=np.int64)
    return merged
