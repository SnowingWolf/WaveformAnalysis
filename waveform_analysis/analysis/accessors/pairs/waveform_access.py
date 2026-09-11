"""S1-S2 summed-waveform loading and access."""

import numpy as np


def load_waveform_layer(self) -> None:
    if self._waveform_layer_loaded:
        return
    self._peaklet_waveforms = self.context.get_data(self.run_id, "peaklet_waveforms")
    self._peaklet_waveform_pool = self.context.get_data(self.run_id, "peaklet_waveform_pool")
    self._peak_id_to_wf_idx = {
        int(row["peak_id"]): index for index, row in enumerate(self._peaklet_waveforms)
    }
    self._waveform_layer_loaded = True


def normalize_waveform_time(self, wf_row: np.void) -> tuple[float, float, np.ndarray]:
    names = wf_row.dtype.names
    if "dt_ps" in names:
        dt_ns = float(wf_row["dt_ps"]) / 1000.0
    elif "dt" in names:
        dt_ns = float(wf_row["dt"])
    else:
        raise ValueError("wf_row 缺少 dt 或 dt_ps 字段")
    length = int(wf_row["wave_length"])
    return int(wf_row["time_start"]) / 1000.0, dt_ns, np.arange(length) * dt_ns


def waveform(self, peak_id: int, copy: bool = False) -> dict | None:
    if not self._waveform_layer_loaded:
        self._load_waveform_layer()
    if peak_id in self._waveform_cache:
        cached = self._waveform_cache[peak_id]
        return {**cached, "waveform": cached["waveform"].copy()} if copy else cached
    index = self._peak_id_to_wf_idx.get(peak_id)
    if index is None:
        return None
    row = self._peaklet_waveforms[index]
    offset = int(row["wave_offset"])
    length = int(row["wave_length"])
    values = self._peaklet_waveform_pool[offset : offset + length]
    time_start_ns, dt_ns, time_rel_ns = self._normalize_waveform_time(row)
    result = {
        "peak_id": peak_id,
        "waveform": values.copy() if copy else values,
        "time_start_ns": time_start_ns,
        "time_rel_ns": time_rel_ns,
        "dt_ns": dt_ns,
    }
    if not copy:
        self._waveform_cache[peak_id] = result
    return result


def pair_waveforms(
    self, pair_or_id: int | np.void, copy: bool = False, missing: str = "raise"
) -> tuple[dict, dict] | None:
    from ...s1_s2_pair_accessor import WaveformNotFoundError

    pair = self._resolve_pair(pair_or_id, missing=missing)
    if pair is None:
        return None
    s1_peak_id = int(pair["s1_peak_id"])
    s2_peak_id = int(pair["s2_peak_id"])
    s1_waveform = self.waveform(s1_peak_id, copy=copy)
    s2_waveform = self.waveform(s2_peak_id, copy=copy)
    if s1_waveform is None:
        if missing == "raise":
            raise WaveformNotFoundError(f"Missing waveform for s1_peak_id={s1_peak_id}")
        return None
    if s2_waveform is None:
        if missing == "raise":
            raise WaveformNotFoundError(f"Missing waveform for s2_peak_id={s2_peak_id}")
        return None
    return s1_waveform, s2_waveform


__all__ = ["load_waveform_layer", "normalize_waveform_time", "waveform", "pair_waveforms"]
