"""Records-backed waveform asymmetry mask plugin."""

from __future__ import annotations

import logging
from typing import Any

import numba
from numba import njit, prange
import numpy as np

from waveform_analysis.core.plugins.core.base import Option, Plugin

logger = logging.getLogger(__name__)


@njit(cache=True, nogil=True, fastmath=True, inline="always")
def _record_passes_asymmetry(
    wave_pool,
    offset,
    length,
    baseline_f,
    cut_min_f,
):
    if length <= 0:
        return False

    end = offset + length
    w_min = wave_pool[offset]
    w_max = wave_pool[offset]

    for sample_i in range(offset + 1, end):
        value = wave_pool[sample_i]
        if value < w_min:
            w_min = value
        elif value > w_max:
            w_max = value

    w_min_f = float(w_min)
    w_max_f = float(w_max)
    peak_to_peak = w_max_f - w_min_f
    negative_height = baseline_f - w_min_f

    if peak_to_peak <= 0.0:
        return False
    if negative_height <= 0.0:
        return False
    if negative_height > peak_to_peak:
        return False

    return negative_height >= cut_min_f * peak_to_peak


@njit(cache=True, nogil=True, fastmath=True)
def fill_asymmetry_mask_numba_serial(
    wave_pool,
    wave_offsets,
    record_lengths,
    baselines,
    cut_min,
    start,
    stop,
    keep,
):
    cut_min_f = float(cut_min)

    for record_i in range(start, stop):
        offset = int(wave_offsets[record_i])
        length = int(record_lengths[record_i])
        keep[record_i] = _record_passes_asymmetry(
            wave_pool,
            offset,
            length,
            float(baselines[record_i]),
            cut_min_f,
        )


@njit(cache=True, nogil=True, parallel=True, fastmath=True)
def fill_asymmetry_mask_numba_parallel(
    wave_pool,
    wave_offsets,
    record_lengths,
    baselines,
    cut_min,
    start,
    stop,
    keep,
):
    cut_min_f = float(cut_min)

    for record_i in prange(start, stop):
        offset = int(wave_offsets[record_i])
        length = int(record_lengths[record_i])
        keep[record_i] = _record_passes_asymmetry(
            wave_pool,
            offset,
            length,
            float(baselines[record_i]),
            cut_min_f,
        )


class RecordsAsymmetryMaskPlugin(Plugin):
    """Return a bool mask aligned with the original records array."""

    provides = "records_asymmetry_mask"
    depends_on = ["records", "wave_pool"]
    description = "Bool mask for waveform asymmetry selection."
    version = "0.1.0"
    save_when = "always"
    output_dtype = np.dtype(np.bool_)

    options = {
        "asymmetry_cut_min": Option(
            default=0.7,
            type=float,
            help="Keep records with asymmetry >= this value.",
        ),
        "asymmetry_parallel": Option(
            default=True,
            type=bool,
            track=False,
            help="Use Numba prange parallel loop.",
        ),
        "asymmetry_chunk_size": Option(
            default=200_000,
            type=int,
            track=False,
            help="Number of records processed per Numba call.",
        ),
        "asymmetry_num_threads": Option(
            default=0,
            type=int,
            track=False,
            help="Numba thread count. <=0 keeps current Numba default.",
        ),
    }

    def compute(self, context: Any, run_id: str, **_kwargs) -> np.ndarray:
        records = context.get_data(run_id, "records")
        wave_pool = np.asarray(context.get_data(run_id, "wave_pool"))

        n_records = len(records)
        keep = np.zeros(n_records, dtype=np.bool_)
        if n_records == 0:
            return keep

        cut_min = float(context.get_config(self, "asymmetry_cut_min"))
        use_parallel = bool(context.get_config(self, "asymmetry_parallel"))
        chunk_size = int(context.get_config(self, "asymmetry_chunk_size"))
        num_threads = int(context.get_config(self, "asymmetry_num_threads"))

        if cut_min > 1.0:
            logger.info(
                "records_asymmetry_mask kept 0/%s records because " "asymmetry_cut_min=%s > 1.0",
                n_records,
                cut_min,
            )
            return keep
        if chunk_size <= 0:
            raise ValueError("asymmetry_chunk_size must be positive.")

        record_names = records.dtype.names or ()
        required = ("wave_offset", "event_length", "baseline")
        missing = [name for name in required if name not in record_names]
        if missing:
            raise ValueError(f"records_asymmetry_mask records input missing fields: {missing}")

        wave_offsets = records["wave_offset"]
        record_lengths = records["event_length"]
        baselines = records["baseline"]

        if not wave_pool.flags.c_contiguous:
            logger.warning(
                "wave_pool is not C-contiguous; making a contiguous copy. "
                "Consider fixing wave_pool construction upstream."
            )
            wave_pool = np.ascontiguousarray(wave_pool)

        old_num_threads = numba.get_num_threads()
        try:
            if use_parallel and num_threads > 0 and num_threads != old_num_threads:
                numba.set_num_threads(num_threads)

            kernel = (
                fill_asymmetry_mask_numba_parallel
                if use_parallel
                else fill_asymmetry_mask_numba_serial
            )
            for start in range(0, n_records, chunk_size):
                stop = min(start + chunk_size, n_records)
                kernel(
                    wave_pool,
                    wave_offsets,
                    record_lengths,
                    baselines,
                    cut_min,
                    start,
                    stop,
                    keep,
                )
        finally:
            if use_parallel and num_threads > 0 and num_threads != old_num_threads:
                numba.set_num_threads(old_num_threads)

        kept = int(np.count_nonzero(keep))
        logger.info(
            "records_asymmetry_mask kept %s/%s records with asymmetry >= %s using %s kernel",
            kept,
            n_records,
            cut_min,
            "parallel" if use_parallel else "serial",
        )
        return keep


__all__ = [
    "RecordsAsymmetryMaskPlugin",
]
