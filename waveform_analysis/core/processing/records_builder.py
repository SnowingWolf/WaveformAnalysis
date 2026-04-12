"""
Records + wave_pool utilities.

This module provides a lightweight event index (records) paired with a
contiguous wave_pool for variable-length waveforms.
"""

from collections.abc import Sequence
from contextlib import nullcontext
from dataclasses import dataclass
from pathlib import Path
import tempfile
import time

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


@dataclass
class _RecordsPartRef:
    records_path: Path
    wave_pool_path: Path
    n_records: int
    n_samples: int


def _normalize_baseline_samples(
    baseline_samples: int | tuple[int, int] | list[int] | None,
) -> int | tuple[int, int] | None:
    if isinstance(baseline_samples, list):
        return tuple(baseline_samples)
    return baseline_samples


def _validate_baseline_samples(
    baseline_samples: int | tuple[int, int] | list[int] | None,
) -> None:
    baseline_samples = _normalize_baseline_samples(baseline_samples)
    if baseline_samples is None:
        return
    if isinstance(baseline_samples, tuple):
        if len(baseline_samples) != 2:
            raise ValueError(
                "baseline_samples tuple must have 2 elements (start, end), "
                f"got {len(baseline_samples)}"
            )
        start, end = baseline_samples
        if not isinstance(start, int) or not isinstance(end, int):
            raise TypeError(
                "baseline_samples tuple elements must be int, "
                f"got ({type(start).__name__}, {type(end).__name__})"
            )
        if start < 0 or end < 0:
            raise ValueError(f"baseline_samples indices must be non-negative, got ({start}, {end})")
        if start >= end:
            raise ValueError(f"baseline_samples start must be less than end, got ({start}, {end})")
        return
    if isinstance(baseline_samples, int):
        if baseline_samples <= 0:
            raise ValueError(f"baseline_samples must be positive, got {baseline_samples}")
        return
    raise TypeError(
        "baseline_samples must be int or tuple (start, end), "
        f"got {type(baseline_samples).__name__}"
    )


def _resolve_baseline_window(
    baseline_samples: int | tuple[int, int] | list[int] | None,
    samples_start: int,
    baseline_start: int,
    baseline_end: int,
) -> tuple[int, int]:
    baseline_samples = _normalize_baseline_samples(baseline_samples)
    if baseline_samples is None:
        return baseline_start, baseline_end
    if isinstance(baseline_samples, tuple):
        return samples_start + baseline_samples[0], samples_start + baseline_samples[1]
    return baseline_start, baseline_start + int(baseline_samples)


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


def _hardware_channel_index_groups(
    st_waveforms: np.ndarray,
) -> list[tuple[HardwareChannel, np.ndarray]]:
    """Return per-channel row indices without copying the full structured array."""
    if st_waveforms is None or len(st_waveforms) == 0:
        return []
    if not isinstance(st_waveforms, np.ndarray) or st_waveforms.dtype.names is None:
        raise ValueError("st_waveforms must be a structured numpy array")
    if "board" not in st_waveforms.dtype.names or "channel" not in st_waveforms.dtype.names:
        raise ValueError("st_waveforms missing required 'board'/'channel' fields")

    groups = group_indices_by_hardware_channel(st_waveforms["board"], st_waveforms["channel"])
    return [(hw_channel, indices) for hw_channel, indices in groups.items()]


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


def _build_records_part_from_raw_array(
    raw_arr: np.ndarray,
    *,
    channel_idx: int,
    default_dt_ns: int,
    cols: object,
    normalize_timestamp_to_ps,
    baseline_samples: int | tuple[int, int] | list[int] | None,
) -> RecordsBundle:
    if raw_arr.size == 0:
        return RecordsBundle(np.zeros(0, dtype=RECORDS_DTYPE), np.zeros(0, dtype=np.uint16))

    if raw_arr.ndim != 2:
        raise ValueError("raw waveform array must be 2D")

    try:
        timestamps = raw_arr[:, cols.timestamp].astype(np.int64)
    except Exception:
        timestamps = np.array([int(row[cols.timestamp]) for row in raw_arr], dtype=np.int64)
    timestamps = normalize_timestamp_to_ps(timestamps, dt_ns=int(default_dt_ns))

    try:
        board_vals = raw_arr[:, cols.board].astype(np.int16)
    except Exception:
        board_vals = np.zeros(len(raw_arr), dtype=np.int16)

    try:
        channel_vals = raw_arr[:, cols.channel].astype(np.int16)
    except Exception:
        channel_vals = np.full(len(raw_arr), int(channel_idx), dtype=np.int16)

    baseline_start, baseline_end = _resolve_baseline_window(
        baseline_samples,
        cols.samples_start,
        cols.baseline_start,
        cols.baseline_end,
    )
    if baseline_end > raw_arr.shape[1]:
        baseline_end = raw_arr.shape[1]
    if baseline_end <= baseline_start:
        baseline_vals = np.full(len(raw_arr), np.nan, dtype=np.float64)
    else:
        try:
            baseline_vals = np.mean(raw_arr[:, baseline_start:baseline_end].astype(float), axis=1)
        except Exception:
            baseline_vals = np.full(len(raw_arr), np.nan, dtype=np.float64)

    samples_end = cols.samples_end if cols.samples_end is not None else raw_arr.shape[1]
    if samples_end > raw_arr.shape[1]:
        samples_end = raw_arr.shape[1]
    if raw_arr.shape[1] <= cols.samples_start or samples_end <= cols.samples_start:
        wave_data = np.zeros((len(raw_arr), 0), dtype=np.int16)
    else:
        wave_data = raw_arr[:, cols.samples_start : samples_end]

    n_records = len(raw_arr)
    records = np.zeros(n_records, dtype=RECORDS_DTYPE)
    records["timestamp"] = timestamps.astype(np.int64, copy=False)
    records["pid"] = 0
    records["board"] = board_vals.astype(np.int16, copy=False)
    records["channel"] = channel_vals.astype(np.int16, copy=False)
    records["baseline"] = baseline_vals.astype(np.float64, copy=False)
    records["baseline_upstream"] = np.nan
    records["polarity"] = "unknown"
    records["dt"] = np.int32(default_dt_ns)
    records["trigger_type"] = 0
    records["flags"] = np.uint32(0)
    records["time"] = records["timestamp"].astype(np.int64, copy=False) // 1000

    wave_data = np.asarray(wave_data)
    if wave_data.ndim != 2:
        raise ValueError("waveform samples must be a 2D array")

    wave_length = int(wave_data.shape[1]) if wave_data.ndim == 2 else 0
    if wave_length > np.iinfo(np.int32).max:
        raise ValueError("event_length exceeds int32 range")
    records["event_length"] = np.int32(wave_length)

    order = _records_sort_order(records)
    records = records[order]

    if wave_length <= 0:
        records["wave_offset"] = 0
        records["record_id"] = np.arange(n_records, dtype=np.int64)
        return RecordsBundle(records=records, wave_pool=np.zeros(0, dtype=np.uint16))

    ordered_waves = wave_data[order]
    wave_pool = np.asarray(ordered_waves, dtype=np.uint16).reshape(-1)
    records["wave_offset"] = np.arange(n_records, dtype=np.int64) * wave_length
    records["record_id"] = np.arange(n_records, dtype=np.int64)
    return RecordsBundle(records=records, wave_pool=wave_pool)


def _write_records_part(
    bundle: RecordsBundle, part_dir: Path, part_idx: int
) -> _RecordsPartRef | None:
    if len(bundle.records) == 0:
        return None

    records_path = part_dir / f"records_part_{part_idx}.dat"
    wave_pool_path = part_dir / f"wave_pool_part_{part_idx}.dat"

    records_mm = np.memmap(
        records_path,
        dtype=RECORDS_DTYPE,
        mode="w+",
        shape=(len(bundle.records),),
    )
    records_mm[:] = bundle.records
    records_mm.flush()

    wave_pool_mm = np.memmap(
        wave_pool_path,
        dtype=np.uint16,
        mode="w+",
        shape=(len(bundle.wave_pool),),
    )
    if len(bundle.wave_pool) > 0:
        wave_pool_mm[:] = bundle.wave_pool
    wave_pool_mm.flush()

    return _RecordsPartRef(
        records_path=records_path,
        wave_pool_path=wave_pool_path,
        n_records=len(bundle.records),
        n_samples=len(bundle.wave_pool),
    )


def _merge_records_part_refs(parts: Sequence[_RecordsPartRef]) -> RecordsBundle:
    if not parts:
        return RecordsBundle(np.zeros(0, dtype=RECORDS_DTYPE), np.zeros(0, dtype=np.uint16))

    if len(parts) == 1:
        part = parts[0]
        records = np.array(
            np.memmap(part.records_path, dtype=RECORDS_DTYPE, mode="r", shape=(part.n_records,)),
            copy=True,
        )
        wave_pool = np.array(
            np.memmap(part.wave_pool_path, dtype=np.uint16, mode="r", shape=(part.n_samples,)),
            copy=True,
        )
        if len(records) > 0:
            records["record_id"] = np.arange(len(records), dtype=np.int64)
        return RecordsBundle(records=records, wave_pool=wave_pool)

    total_records = sum(part.n_records for part in parts)
    if total_records == 0:
        return RecordsBundle(np.zeros(0, dtype=RECORDS_DTYPE), np.zeros(0, dtype=np.uint16))

    total_samples = sum(part.n_samples for part in parts)
    records_out = np.zeros(total_records, dtype=RECORDS_DTYPE)
    wave_pool_out = np.zeros(total_samples, dtype=np.uint16)

    import heapq

    records_parts = [
        np.memmap(part.records_path, dtype=RECORDS_DTYPE, mode="r", shape=(part.n_records,))
        for part in parts
    ]
    wave_pool_parts = [
        np.memmap(part.wave_pool_path, dtype=np.uint16, mode="r", shape=(part.n_samples,))
        for part in parts
    ]

    heap = []
    for part_idx, records in enumerate(records_parts):
        if len(records) == 0:
            continue
        rec = records[0]
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
        records = records_parts[part_idx]
        rec = records[row_idx]
        length = max(int(rec["event_length"]), 0)

        if length > 0:
            offset = int(rec["wave_offset"])
            wave_pool_out[wave_cursor : wave_cursor + length] = wave_pool_parts[part_idx][
                offset : offset + length
            ]

        records_out[out_idx] = rec
        records_out[out_idx]["wave_offset"] = wave_cursor
        out_idx += 1
        wave_cursor += length

        next_row = row_idx + 1
        if next_row < len(records):
            next_rec = records[next_row]
            key = (
                int(next_rec["timestamp"]),
                int(next_rec["pid"]),
                int(next_rec["board"]),
                int(next_rec["channel"]),
                part_idx,
                next_row,
            )
            heapq.heappush(heap, key)

    records_out["record_id"] = np.arange(total_records, dtype=np.int64)
    return RecordsBundle(records=records_out, wave_pool=wave_pool_out)


def _build_records_part_refs_for_channel(
    *,
    channel_idx: int,
    channel_files: Sequence[str],
    part_root: str | Path,
    adapter_name: str,
    default_dt_ns: int,
    part_size: int | None,
    baseline_samples: int | tuple[int, int] | list[int] | None,
    epoch_ns: int | None,
    parse_engine: str | None,
    n_jobs: int | None,
    chunksize: int | None,
    use_process_pool: bool,
) -> tuple[int, list[_RecordsPartRef], dict[str, tuple[float, int]]]:
    from waveform_analysis.utils.formats import get_adapter

    adapter = get_adapter(adapter_name)
    reader = adapter.format_reader
    cols = adapter.format_spec.columns

    effective_n_jobs = 1 if n_jobs is None else max(int(n_jobs), 1)
    file_batch_size = max(1, effective_n_jobs)
    channel_part_dir = Path(part_root) / f"channel_{channel_idx}"
    channel_part_dir.mkdir(parents=True, exist_ok=True)

    try:
        raw_iter = reader.read_files_generator(
            list(channel_files),
            chunk_size=file_batch_size,
            chunksize=chunksize,
            n_jobs=effective_n_jobs,
            use_process_pool=use_process_pool,
            parse_engine=parse_engine,
            show_progress=False,
        )
    except TypeError:
        raw_iter = reader.read_files_generator(list(channel_files), chunk_size=file_batch_size)

    part_refs: list[_RecordsPartRef] = []
    profile = {
        "records.read": [0.0, 0],
        "records.part_build": [0.0, 0],
    }
    part_idx = 0

    while True:
        read_started = time.perf_counter()
        try:
            raw_arr = next(raw_iter)
        except StopIteration:
            break
        profile["records.read"][0] += time.perf_counter() - read_started
        profile["records.read"][1] += 1

        if raw_arr.size == 0:
            continue
        if part_size is None or part_size <= 0:
            slices = [raw_arr]
        else:
            slices = [
                raw_arr[start : start + part_size] for start in range(0, len(raw_arr), part_size)
            ]

        for raw_slice in slices:
            build_started = time.perf_counter()
            part = _build_records_part_from_raw_array(
                raw_slice,
                channel_idx=channel_idx,
                default_dt_ns=default_dt_ns,
                cols=cols,
                normalize_timestamp_to_ps=adapter.format_spec.normalize_timestamp_to_ps,
                baseline_samples=baseline_samples,
            )
            profile["records.part_build"][0] += time.perf_counter() - build_started
            profile["records.part_build"][1] += 1
            if len(part.records) == 0:
                continue
            if epoch_ns is not None and "time" in part.records.dtype.names:
                part.records["time"] = np.int64(epoch_ns) + (
                    part.records["timestamp"].astype(np.int64, copy=False) // 1000
                )
            part_ref = _write_records_part(part, channel_part_dir, part_idx)
            part_idx += 1
            if part_ref is not None:
                part_refs.append(part_ref)

    return (
        channel_idx,
        part_refs,
        {key: (float(values[0]), int(values[1])) for key, values in profile.items()},
    )


@export
def build_records_from_raw_files_streaming(
    raw_files: list[list[str]],
    adapter_name: str,
    default_dt_ns: int = 1,
    part_size: int | None = 250_000,
    baseline_samples: int | tuple[int, int] | list[int] | None = None,
    epoch_ns: int | None = None,
    show_progress: bool = False,
    parse_engine: str | None = "auto",
    n_jobs: int | None = None,
    chunksize: int | None = None,
    use_process_pool: bool = False,
    channel_workers: int | None = None,
    channel_executor: str = "thread",
    profiler=None,
) -> RecordsBundle:
    _validate_baseline_samples(baseline_samples)

    timer = profiler.timeit if profiler else None

    channel_entries = [
        (channel_idx, channel_files) for channel_idx, channel_files in enumerate(raw_files)
    ]
    if not channel_entries:
        return RecordsBundle(np.zeros(0, dtype=RECORDS_DTYPE), np.zeros(0, dtype=np.uint16))

    nonempty_channels = [
        (channel_idx, channel_files)
        for channel_idx, channel_files in channel_entries
        if channel_files
    ]
    if not nonempty_channels:
        return RecordsBundle(np.zeros(0, dtype=RECORDS_DTYPE), np.zeros(0, dtype=np.uint16))

    if show_progress:
        try:
            from tqdm import tqdm

            iterator = tqdm(channel_entries, desc="Building records", leave=False)
        except ImportError:
            iterator = channel_entries
    else:
        iterator = channel_entries

    with tempfile.TemporaryDirectory(prefix="records_parts_") as tmp_dir:
        part_dir = Path(tmp_dir)
        part_refs: list[_RecordsPartRef] = []
        channel_results: dict[int, list[_RecordsPartRef]] = {}

        effective_channel_workers = 1 if channel_workers is None else max(int(channel_workers), 1)
        if effective_channel_workers <= 1 or len(nonempty_channels) <= 1:
            for channel_idx, channel_files in iterator:
                if not channel_files:
                    continue
                result_idx, result_parts, profile = _build_records_part_refs_for_channel(
                    channel_idx=channel_idx,
                    channel_files=channel_files,
                    part_root=part_dir,
                    adapter_name=adapter_name,
                    default_dt_ns=default_dt_ns,
                    part_size=part_size,
                    baseline_samples=baseline_samples,
                    epoch_ns=epoch_ns,
                    parse_engine=parse_engine,
                    n_jobs=n_jobs,
                    chunksize=chunksize,
                    use_process_pool=use_process_pool,
                )
                channel_results[result_idx] = result_parts
                if profiler:
                    for key, (duration, count) in profile.items():
                        profiler.durations[key] += duration
                        profiler.counts[key] += count
        else:
            from concurrent.futures import as_completed

            from waveform_analysis.core.execution.manager import get_executor

            max_workers = min(effective_channel_workers, len(nonempty_channels))
            with get_executor(
                "records_channel_build",
                executor_type=channel_executor,
                max_workers=max_workers,
                reuse=True,
            ) as executor:
                futures = {
                    executor.submit(
                        _build_records_part_refs_for_channel,
                        channel_idx=channel_idx,
                        channel_files=channel_files,
                        part_root=part_dir,
                        adapter_name=adapter_name,
                        default_dt_ns=default_dt_ns,
                        part_size=part_size,
                        baseline_samples=baseline_samples,
                        epoch_ns=epoch_ns,
                        parse_engine=parse_engine,
                        n_jobs=n_jobs,
                        chunksize=chunksize,
                        use_process_pool=use_process_pool,
                    ): channel_idx
                    for channel_idx, channel_files in nonempty_channels
                }
                pbar = iterator if hasattr(iterator, "update") else None
                for future in as_completed(futures):
                    result_idx, result_parts, profile = future.result()
                    channel_results[result_idx] = result_parts
                    if profiler:
                        for key, (duration, count) in profile.items():
                            profiler.durations[key] += duration
                            profiler.counts[key] += count
                    if pbar is not None:
                        pbar.update(1)

        for channel_idx, _ in channel_entries:
            part_refs.extend(channel_results.get(channel_idx, []))

        with timer("records.merge") if timer else nullcontext():
            return _merge_records_part_refs(part_refs)


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
    channels = [
        (st_waveforms[indices], hw_channel)
        for hw_channel, indices in _hardware_channel_index_groups(st_waveforms)
    ]
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
def build_records_from_raw_files(
    raw_files: list[list[str]],
    adapter_name: str,
    default_dt_ns: int = 1,
    part_size: int | None = 250_000,
    baseline_samples: int | tuple[int, int] | list[int] | None = None,
    epoch_ns: int | None = None,
    show_progress: bool = False,
    parse_engine: str | None = "auto",
    n_jobs: int | None = None,
    chunksize: int | None = None,
    use_process_pool: bool = False,
    channel_workers: int | None = None,
    channel_executor: str = "thread",
    profiler=None,
) -> RecordsBundle:
    """Build records + wave_pool from raw files using the streaming part builder."""
    return build_records_from_raw_files_streaming(
        raw_files=raw_files,
        adapter_name=adapter_name,
        default_dt_ns=default_dt_ns,
        part_size=part_size,
        baseline_samples=baseline_samples,
        epoch_ns=epoch_ns,
        show_progress=show_progress,
        parse_engine=parse_engine,
        n_jobs=n_jobs,
        chunksize=chunksize,
        use_process_pool=use_process_pool,
        channel_workers=channel_workers,
        channel_executor=channel_executor,
        profiler=profiler,
    )


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
    if part_size is None or part_size <= 0:
        return build_records_from_st_waveforms(st_waveforms, default_dt_ns=default_dt_ns)

    total_records = len(st_waveforms)
    if total_records <= part_size:
        return build_records_from_st_waveforms(st_waveforms, default_dt_ns=default_dt_ns)

    parts: list[RecordsBundle] = []
    for hw_channel, indices in _hardware_channel_index_groups(st_waveforms):
        count = len(indices)
        if count == 0:
            continue
        start = 0
        while start < count:
            stop = min(count, start + part_size)
            shard_indices = indices[start:stop]
            part = _build_records_from_channels(
                [(st_waveforms[shard_indices], hw_channel)],
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
