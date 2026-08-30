"""Peak-channel NumPy index construction."""

import numpy as np


def build_feature_indices(self):
    components = self._peaklet_components
    unique_peaks, inverse, counts = np.unique(
        components["peak_id"], return_inverse=True, return_counts=True
    )
    sort_order = np.argsort(inverse)
    self._peak_to_merged_idx = {}
    offset = 0
    for index, peak_id in enumerate(unique_peaks):
        count = counts[index]
        group = sort_order[offset : offset + count]
        self._peak_to_merged_idx[int(peak_id)] = components["merged_index"][group].tolist()
        offset += count
    self._peak_to_channel_rows = {}
    channels = self._peaklet_channels
    if not len(channels):
        return
    unique_peaks, inverse, counts = np.unique(
        channels["peaklet_id"], return_inverse=True, return_counts=True
    )
    sort_order = np.argsort(inverse)
    offset = 0
    for index, peak_id in enumerate(unique_peaks):
        count = counts[index]
        group = sort_order[offset : offset + count]
        self._peak_to_channel_rows[int(peak_id)] = channels[group]
        offset += count


def build_waveform_indices(self):
    self._record_id_to_idx = {
        int(record["record_id"]): index for index, record in enumerate(self._records)
    }
    components = self._hit_merged_components
    unique_merged, inverse, counts = np.unique(
        components["merged_index"], return_inverse=True, return_counts=True
    )
    sort_order = np.argsort(inverse)
    self._merged_to_hit_idx = {}
    offset = 0
    for index, merged_index in enumerate(unique_merged):
        count = counts[index]
        group = sort_order[offset : offset + count]
        self._merged_to_hit_idx[int(merged_index)] = components["hit_index"][group].tolist()
        offset += count


__all__ = ["build_feature_indices", "build_waveform_indices"]
