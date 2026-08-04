"""peaklet_features bundle - provides 'peaklet_features'。"""

from typing import Any

import numpy as np

from waveform_analysis.core.plugins.core.base import Plugin

try:
    from numba import njit

    HAS_NUMBA = True
except ImportError:
    HAS_NUMBA = False

    def njit(*args, **kwargs):
        if len(args) == 1 and callable(args[0]):
            return args[0]
        return lambda f: f


from waveform_analysis.core.plugins.builtin.peaklets._compute import (
    PEAKLET_FEATURES_DTYPE,
    _compute_area_quantile_times,
    _compute_features_numba,
    _empty_features,
)


class PeakletFeaturesPlugin(Plugin):
    """Compute waveform-derived features from ragged peaklet waveforms."""

    provides = "peaklet_features"
    lineage_virtual = True
    depends_on = ["peaklet_waveforms", "peaklet_waveform_pool", "peaklets"]
    description = "Compute peaklet waveform features from ragged signal pools."
    version = "4.1.0"
    output_dtype = PEAKLET_FEATURES_DTYPE
    save_when = "always"

    def compute(self, context: Any, run_id: str, **_kwargs) -> np.ndarray:
        waveforms = context.get_data(run_id, "peaklet_waveforms")
        if not isinstance(waveforms, np.ndarray):
            raise ValueError("peaklet_features expects peaklet_waveforms as a structured array")
        if len(waveforms) == 0:
            return _empty_features()
        pool = context.get_data(run_id, "peaklet_waveform_pool")
        if not isinstance(pool, np.ndarray):
            raise ValueError("peaklet_features expects peaklet_waveform_pool as a numpy array")
        peaklets = context.get_data(run_id, "peaklets")
        if not isinstance(peaklets, np.ndarray):
            raise ValueError("peaklet_features expects peaklets as a structured array")

        # Extract arrays for Numba
        if HAS_NUMBA and len(waveforms) > 10:
            peaklet_indices = waveforms["peak_id"].astype(np.int64, copy=False)
            offsets = waveforms["wave_offset"].astype(np.int64, copy=False)
            lengths = waveforms["wave_length"].astype(np.int64, copy=False)
            time_starts = waveforms["time_start"].astype(np.int64, copy=False)
            time_ends = waveforms["time_end"].astype(np.int64, copy=False)
            dt_ns_arr = waveforms["dt"].astype(np.int64, copy=False)

            out = np.zeros(len(waveforms), dtype=PEAKLET_FEATURES_DTYPE)
            _compute_features_numba(
                pool,
                peaklet_indices,
                offsets,
                lengths,
                time_starts,
                time_ends,
                dt_ns_arr,
                out,
            )
            return out

        # Fallback: Python loop
        rows: list[
            tuple[int, int, int, int, int, float, float, float, float, float, float, float, float]
        ] = []
        for row in waveforms:
            peaklet_id = int(row["peak_id"])
            offset = int(row["wave_offset"])
            length = int(row["wave_length"])
            time_left = int(row["time_start"])
            time_right = int(row["time_end"])
            dt_ns = int(row["dt"])

            if length <= 0:
                rows.append(
                    (
                        peaklet_id,
                        time_left,
                        time_right,
                        time_left,
                        time_left,
                        0.0,  # rise_time
                        0.0,  # fall_time
                        0.0,  # width_25_75
                        0.0,  # rise_time_10_50
                        0.0,  # range_90p_area
                        0.0,  # area
                        0.0,  # height
                        0.0,  # width
                    )
                )
                continue

            wave = pool[offset : offset + length].astype(np.float32, copy=False)
            if len(wave) != length:
                raise ValueError("peaklet_features found out-of-bounds waveform slice")

            t05, t10, t25, t50, t75, t90, t95 = _compute_area_quantile_times(wave, time_left, dt_ns)

            max_idx = int(np.argmax(wave))
            time_peak = int(time_left + max_idx * dt_ns * 1000)

            rise_time = float((time_peak - t10) / 1000.0)
            fall_time = float((t90 - time_peak) / 1000.0)
            width_25_75 = float((t75 - t25) / 1000.0)
            rise_time_10_50 = float((t50 - t10) / 1000.0)
            range_90p_area = float((t95 - t05) / 1000.0)

            area = float(np.sum(wave, dtype=np.float64))
            height = float(wave[max_idx])
            width = float((time_right - time_left) / 1000.0)

            rows.append(
                (
                    peaklet_id,
                    time_left,
                    time_right,
                    time_peak,
                    t50,
                    rise_time,
                    fall_time,
                    width_25_75,
                    rise_time_10_50,
                    range_90p_area,
                    area,
                    height,
                    width,
                )
            )

        return np.array(rows, dtype=PEAKLET_FEATURES_DTYPE) if rows else _empty_features()


__all__ = ["PeakletFeaturesPlugin"]
