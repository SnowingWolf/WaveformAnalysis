"""
RecordsView provides read-only access to records with an internal wave_pool.
"""

from collections.abc import Iterable
from typing import Any

import numpy as np

from waveform_analysis.core.foundation.utils import exporter

export, __all__ = exporter()


@export
class RecordsView:
    def __init__(self, records: np.ndarray, wave_pool: np.ndarray):
        if records.dtype.names is None:
            raise ValueError("records must be a structured array")
        required = ("record_id", "wave_offset", "event_length", "timestamp", "baseline")
        missing = [name for name in required if name not in records.dtype.names]
        if missing:
            raise ValueError(f"records missing required fields: {missing}")

        self.records = records
        self.wave_pool = wave_pool
        self._record_ids = records["record_id"].astype(np.int64, copy=False)
        self._wave_offsets = records["wave_offset"].astype(np.int64, copy=False)
        self._event_lengths = records["event_length"].astype(np.int64, copy=False)
        self._wave_ends = self._wave_offsets + self._event_lengths
        self._timestamps = records["timestamp"]
        self._record_id_lookup = self._build_record_id_lookup()
        self._validate_wave_bounds()

    def __len__(self) -> int:
        return len(self.records)

    def _build_record_id_lookup(self) -> dict[int, int]:
        lookup: dict[int, int] = {}
        for idx, record_id in enumerate(self._record_ids.tolist()):
            key = int(record_id)
            if key in lookup:
                raise ValueError(f"records field record_id must be unique, got duplicate {key}")
            lookup[key] = idx
        return lookup

    def _validate_wave_bounds(self) -> None:
        if len(self.records) == 0:
            return
        if np.any(self._wave_offsets < 0):
            raise ValueError("records contain negative wave_offset values")
        if np.any(self._event_lengths < 0):
            raise ValueError("records contain negative event_length values")
        wave_pool_size = len(self.wave_pool)
        if np.any(self._wave_ends > wave_pool_size):
            raise ValueError("records reference samples outside wave_pool bounds")

    def _resolve_record_index(self, record_id: int) -> int:
        key = int(record_id)
        if key not in self._record_id_lookup:
            raise KeyError(f"Unknown record_id: {key}")
        return self._record_id_lookup[key]

    def _resolve_record_indices(self, record_ids: Iterable[int] | np.ndarray) -> np.ndarray:
        ids = np.asarray(list(record_ids), dtype=np.int64)
        if ids.size == 0:
            return np.zeros(0, dtype=np.int64)
        try:
            return np.fromiter(
                (self._record_id_lookup[int(record_id)] for record_id in ids),
                dtype=np.int64,
                count=ids.size,
            )
        except KeyError as exc:
            missing = int(exc.args[0])
            raise KeyError(f"Unknown record_id: {missing}") from None

    def _resolve_signal_baseline(
        self,
        rec: np.void,
        dtype: np.dtype,
        baseline: float | None = None,
    ) -> np.ndarray:
        value = rec["baseline"] if baseline is None else baseline
        return np.asarray(value, dtype=dtype)

    def _normalize_polarity_wave(
        self,
        rec: np.void,
        wave: np.ndarray,
        dtype: np.dtype,
        baseline: float | None = None,
    ) -> np.ndarray:
        signal = wave.astype(dtype, copy=False) - self._resolve_signal_baseline(
            rec, dtype, baseline=baseline
        )
        polarity = str(rec["polarity"]) if "polarity" in rec.dtype.names else "unknown"
        if polarity == "positive":
            signal = -signal
        return signal

    def _resolve_window_bounds(
        self,
        length: int,
        sample_start: int = 0,
        sample_end: int | None = None,
    ) -> tuple[int, int]:
        start = max(int(sample_start), 0)
        end = length if sample_end is None else max(int(sample_end), 0)
        end = min(end, length)
        start = min(start, end)
        return start, end

    def _slice_window(
        self,
        values: np.ndarray,
        sample_start: int = 0,
        sample_end: int | None = None,
    ) -> np.ndarray:
        start, end = self._resolve_window_bounds(
            len(values),
            sample_start=sample_start,
            sample_end=sample_end,
        )
        return values[start:end]

    def _record_wave(self, rec_idx: int) -> np.ndarray:
        return self.wave_pool[self._wave_offsets[rec_idx] : self._wave_ends[rec_idx]]

    def _wave_one(
        self,
        record_id: int,
        sample_start: int = 0,
        sample_end: int | None = None,
        baseline_correct: bool = False,
        dtype: np.dtype | None = None,
    ) -> np.ndarray:
        rec_idx = self._resolve_record_index(int(record_id))
        rec = self.records[rec_idx]
        wave = self._record_wave(rec_idx)

        if baseline_correct:
            out_dtype = dtype or np.float32
            wave = wave.astype(out_dtype, copy=False)
            baseline = np.asarray(rec["baseline"], dtype=out_dtype)
            wave = wave - baseline
        elif dtype is not None and wave.dtype != dtype:
            wave = wave.astype(dtype, copy=False)

        return self._slice_window(wave, sample_start=sample_start, sample_end=sample_end)

    def _signal_one(
        self,
        record_id: int,
        sample_start: int = 0,
        sample_end: int | None = None,
        dtype: np.dtype | None = None,
        baseline: float | None = None,
    ) -> np.ndarray:
        rec_idx = self._resolve_record_index(int(record_id))
        rec = self.records[rec_idx]
        wave = self._record_wave(rec_idx)
        signal = self._normalize_polarity_wave(
            rec,
            wave,
            dtype or np.float32,
            baseline=baseline,
        )
        return self._slice_window(signal, sample_start=sample_start, sample_end=sample_end)

    def _allocate_batch_output(
        self,
        n_rows: int,
        lengths: np.ndarray,
        pad_to: int | None,
        dtype: np.dtype,
        mask: bool,
    ) -> tuple[np.ndarray, np.ndarray | None]:
        max_len = int(lengths.max()) if lengths.size else 0
        if pad_to is None:
            pad_len = max_len
        else:
            if pad_to < 0:
                raise ValueError("pad_to must be >= 0")
            if pad_to < max_len:
                raise ValueError(f"pad_to ({pad_to}) < max length ({max_len})")
            pad_len = int(pad_to)

        values_out = np.zeros((n_rows, pad_len), dtype=dtype)
        mask_out = np.zeros((n_rows, pad_len), dtype=bool) if mask else None
        return values_out, mask_out

    def _window_lengths(
        self,
        indices: np.ndarray,
        sample_start: int = 0,
        sample_end: int | None = None,
    ) -> np.ndarray:
        lengths = self._event_lengths[indices]
        starts = np.clip(int(sample_start), 0, lengths)
        if sample_end is None:
            ends = lengths
        else:
            ends = np.clip(int(sample_end), 0, lengths)
        starts = np.minimum(starts, ends)
        return (ends - starts).astype(np.int64, copy=False)

    def _waves_many(
        self,
        record_ids: Iterable[int] | np.ndarray,
        pad_to: int | None = None,
        mask: bool = False,
        baseline_correct: bool = False,
        dtype: np.dtype | None = None,
        sample_start: int = 0,
        sample_end: int | None = None,
    ) -> np.ndarray | tuple[np.ndarray, np.ndarray]:
        indices = self._resolve_record_indices(record_ids)
        if indices.size == 0:
            empty = np.zeros((0, 0), dtype=dtype or np.float32)
            return (empty, empty.astype(bool)) if mask else empty

        lengths = self._window_lengths(
            indices,
            sample_start=sample_start,
            sample_end=sample_end,
        )
        out_dtype = np.dtype(dtype or (np.float32 if baseline_correct else self.wave_pool.dtype))
        waves_out, mask_out = self._allocate_batch_output(
            len(indices),
            lengths,
            pad_to=pad_to,
            dtype=out_dtype,
            mask=mask,
        )

        for out_idx, rec_idx in enumerate(indices):
            start, end = self._resolve_window_bounds(
                int(self._event_lengths[rec_idx]),
                sample_start=sample_start,
                sample_end=sample_end,
            )
            if start == end:
                continue
            wave = self._record_wave(int(rec_idx))[start:end]
            if baseline_correct:
                baseline = np.asarray(self.records[int(rec_idx)]["baseline"], dtype=out_dtype)
                wave = wave.astype(out_dtype, copy=False) - baseline
            elif wave.dtype != out_dtype:
                wave = wave.astype(out_dtype, copy=False)
            waves_out[out_idx, : len(wave)] = wave
            if mask_out is not None:
                mask_out[out_idx, : len(wave)] = True

        if mask_out is not None:
            return waves_out, mask_out
        return waves_out

    def _signals_many(
        self,
        record_ids: Iterable[int] | np.ndarray,
        pad_to: int | None = None,
        mask: bool = False,
        dtype: np.dtype | None = None,
        sample_start: int = 0,
        sample_end: int | None = None,
    ) -> np.ndarray | tuple[np.ndarray, np.ndarray]:
        indices = self._resolve_record_indices(record_ids)
        if indices.size == 0:
            empty = np.zeros((0, 0), dtype=dtype or np.float32)
            return (empty, empty.astype(bool)) if mask else empty

        lengths = self._window_lengths(
            indices,
            sample_start=sample_start,
            sample_end=sample_end,
        )
        out_dtype = np.dtype(dtype or np.float32)
        signals_out, mask_out = self._allocate_batch_output(
            len(indices),
            lengths,
            pad_to=pad_to,
            dtype=out_dtype,
            mask=mask,
        )

        for out_idx, rec_idx in enumerate(indices):
            rec = self.records[int(rec_idx)]
            start, end = self._resolve_window_bounds(
                int(self._event_lengths[rec_idx]),
                sample_start=sample_start,
                sample_end=sample_end,
            )
            if start == end:
                continue
            wave = self._record_wave(int(rec_idx))[start:end]
            signal = self._normalize_polarity_wave(rec, wave, out_dtype)
            signals_out[out_idx, : len(signal)] = signal
            if mask_out is not None:
                mask_out[out_idx, : len(signal)] = True

        if mask_out is not None:
            return signals_out, mask_out
        return signals_out

    def waves(
        self,
        record_ids: int | Iterable[int] | np.ndarray,
        pad_to: int | None = None,
        mask: bool = False,
        baseline_correct: bool = False,
        dtype: np.dtype | None = None,
        sample_start: int = 0,
        sample_end: int | None = None,
    ) -> np.ndarray | tuple[np.ndarray, np.ndarray]:
        if np.isscalar(record_ids):
            return self._wave_one(
                int(record_ids),
                sample_start=sample_start,
                sample_end=sample_end,
                baseline_correct=baseline_correct,
                dtype=dtype,
            )
        return self._waves_many(
            record_ids,
            pad_to=pad_to,
            mask=mask,
            baseline_correct=baseline_correct,
            dtype=dtype,
            sample_start=sample_start,
            sample_end=sample_end,
        )

    def signals(
        self,
        record_ids: int | Iterable[int] | np.ndarray,
        pad_to: int | None = None,
        mask: bool = False,
        dtype: np.dtype | None = None,
        baseline: float | None = None,
        sample_start: int = 0,
        sample_end: int | None = None,
    ) -> np.ndarray | tuple[np.ndarray, np.ndarray]:
        if np.isscalar(record_ids):
            return self._signal_one(
                int(record_ids),
                sample_start=sample_start,
                sample_end=sample_end,
                dtype=dtype,
                baseline=baseline,
            )
        if baseline is not None:
            raise ValueError("baseline override is only supported for scalar signal access")
        return self._signals_many(
            record_ids,
            pad_to=pad_to,
            mask=mask,
            dtype=dtype,
            sample_start=sample_start,
            sample_end=sample_end,
        )

    def query_time_window(
        self,
        t_min: int | None = None,
        t_max: int | None = None,
    ) -> np.ndarray:
        timestamps = self._timestamps
        if t_min is None:
            start = 0
        else:
            start = int(np.searchsorted(timestamps, t_min, side="left"))

        if t_max is None:
            end = len(timestamps)
        else:
            end = int(np.searchsorted(timestamps, t_max, side="right"))

        return self.records[start:end]


@export
def records_view(
    source: Any,
    run_id: str,
    records_name: str = "records",
    wave_pool_name: str = "wave_pool",
) -> RecordsView:
    """
    Factory function to create a RecordsView from a Context-like source.
    """
    records = source.get_data(run_id, records_name)
    wave_pool = source.get_data(run_id, wave_pool_name)

    if not isinstance(records, np.ndarray):
        raise ValueError(f"records_view requires formal '{records_name}' plugin output")
    if not isinstance(wave_pool, np.ndarray):
        raise ValueError(f"records_view requires formal '{wave_pool_name}' plugin output")

    return RecordsView(records, wave_pool)
