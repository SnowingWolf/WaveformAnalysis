"""Peak summed-waveform loading, indexing, and slicing."""

import numpy as np


def load_sum_waveform_layer(self) -> bool:
    if self._sum_waveform_layer_loaded:
        return True
    try:
        waveforms = self.context.get_data(self.run_id, "peaklet_waveforms")
        pool = self.context.get_data(self.run_id, "peaklet_waveform_pool")
    except Exception:
        return False
    if not isinstance(waveforms, np.ndarray) or not isinstance(pool, np.ndarray):
        return False
    if "peak_id" not in (waveforms.dtype.names or ()):
        return False
    self._peaklet_waveforms = waveforms
    self._peaklet_waveform_pool = pool
    peak_ids = waveforms["peak_id"]
    if len(peak_ids) < 2 or np.all(peak_ids[1:] >= peak_ids[:-1]):
        self._sorted_sum_waveform_peak_ids = peak_ids
        self._sum_waveform_sort_order = None
    else:
        self._sum_waveform_sort_order = np.argsort(peak_ids, kind="stable")
        self._sorted_sum_waveform_peak_ids = peak_ids[self._sum_waveform_sort_order]
    self._sum_waveform_layer_loaded = True
    return True


def get_sum_waveform(self, peak_id: int) -> dict | None:
    if not self._load_sum_waveform_layer():
        return None
    peak_id = int(peak_id)
    sorted_index = int(np.searchsorted(self._sorted_sum_waveform_peak_ids, peak_id, side="left"))
    if (
        sorted_index >= len(self._sorted_sum_waveform_peak_ids)
        or int(self._sorted_sum_waveform_peak_ids[sorted_index]) != peak_id
    ):
        return None
    waveform_index = (
        sorted_index
        if self._sum_waveform_sort_order is None
        else int(self._sum_waveform_sort_order[sorted_index])
    )
    row = self._peaklet_waveforms[waveform_index]
    offset = int(row["wave_offset"])
    length = int(row["wave_length"])
    dt = int(row["dt"])
    return {
        "peak_id": peak_id,
        "waveform": self._peaklet_waveform_pool[offset : offset + length],
        "time_start": int(row["time_start"]),
        "time_end": int(row["time_end"]),
        "dt": dt,
        "time_ns": np.arange(length) * dt,
    }


__all__ = ["load_sum_waveform_layer", "get_sum_waveform"]
