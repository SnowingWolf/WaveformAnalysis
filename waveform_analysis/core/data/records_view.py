"""
RecordsView provides read-only access to records with an internal wave_pool.
"""

from typing import Any, Iterable, Optional, Tuple, Union

import numpy as np

from waveform_analysis.core.foundation.utils import exporter

export, __all__ = exporter()


@export
class RecordsView:
    def __init__(self, records: np.ndarray, wave_pool: np.ndarray):
        if records.dtype.names is None:
            raise ValueError("records must be a structured array")
        required = ("wave_offset", "event_length", "timestamp", "baseline")
        missing = [name for name in required if name not in records.dtype.names]
        if missing:
            raise ValueError(f"records missing required fields: {missing}")
        self.records = records
        self.wave_pool = wave_pool

    def __len__(self) -> int:
        return len(self.records)

    def wave(
        self,
        index: int,
        baseline_correct: bool = False,
        dtype: Optional[np.dtype] = None,
    ) -> np.ndarray:
        rec = self.records[index]
        offset = int(rec["wave_offset"])
        length = int(rec["event_length"])
        wave = self.wave_pool[offset : offset + length]

        if baseline_correct:
            out_dtype = dtype or np.float32
            wave = wave.astype(out_dtype, copy=False)
            baseline = np.asarray(rec["baseline"], dtype=out_dtype)
            return wave - baseline

        if dtype is not None and wave.dtype != dtype:
            return wave.astype(dtype, copy=False)
        return wave

    def waves(
        self,
        indices: Union[Iterable[int], np.ndarray],
        pad_to: Optional[int] = None,
        mask: bool = False,
        baseline_correct: bool = False,
        dtype: Optional[np.dtype] = None,
    ) -> Union[np.ndarray, Tuple[np.ndarray, np.ndarray]]:
        idx = np.asarray(list(indices), dtype=np.int64)
        if idx.size == 0:
            empty = np.zeros((0, 0), dtype=dtype or np.float32)
            return (empty, empty.astype(bool)) if mask else empty

        lengths = self.records["event_length"][idx].astype(np.int64, copy=False)
        max_len = int(lengths.max()) if lengths.size else 0
        if pad_to is None:
            pad_len = max_len
        else:
            if pad_to < max_len:
                raise ValueError(f"pad_to ({pad_to}) < max length ({max_len})")
            pad_len = pad_to

        if baseline_correct:
            out_dtype = dtype or np.float32
        else:
            out_dtype = dtype or self.wave_pool.dtype

        waves_out = np.zeros((len(idx), pad_len), dtype=out_dtype)
        mask_out = np.zeros((len(idx), pad_len), dtype=bool) if mask else None

        for i, rec_idx in enumerate(idx):
            rec = self.records[rec_idx]
            length = int(rec["event_length"])
            if length <= 0:
                continue
            offset = int(rec["wave_offset"])
            wave = self.wave_pool[offset : offset + length]
            if baseline_correct:
                wave = wave.astype(out_dtype, copy=False)
                baseline = np.asarray(rec["baseline"], dtype=out_dtype)
                wave = wave - baseline
            elif wave.dtype != out_dtype:
                wave = wave.astype(out_dtype, copy=False)
            waves_out[i, :length] = wave
            if mask_out is not None:
                mask_out[i, :length] = True

        if mask_out is not None:
            return waves_out, mask_out
        return waves_out

    def query_time_window(
        self,
        t_min: Optional[int] = None,
        t_max: Optional[int] = None,
    ) -> np.ndarray:
        timestamps = self.records["timestamp"]
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
def records_view(source: Any, run_id: str) -> RecordsView:
    """
    Factory function to create a RecordsView from a Context-like source.
    """
    provided = []
    if hasattr(source, "list_provided_data"):
        try:
            provided = source.list_provided_data()
        except Exception:
            provided = []

    if "events" in provided:
        from waveform_analysis.core.plugins.builtin.cpu.events import get_events_bundle

        bundle = get_events_bundle(source, run_id)
    else:
        from waveform_analysis.core.plugins.builtin.cpu.records import get_records_bundle

        bundle = get_records_bundle(source, run_id)
    return RecordsView(bundle.records, bundle.wave_pool)
