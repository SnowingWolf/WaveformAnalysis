"""Shared nopython primitives for canonical single-channel waveform merging."""

from __future__ import annotations

import numba as nb
import numpy as np

MAX_CANONICAL_DENSE_SAMPLES_PER_GROUP = 262_144
MAX_CANONICAL_DENSE_SAMPLES_PER_BATCH = 8_000_000


@nb.njit(cache=True, inline="always")
def float32_bits(value):
    """Return the exact IEEE-754 representation used for duplicate checks."""
    return np.float32(value).view(np.uint32)


@nb.njit(cache=True, nogil=True, parallel=True)
def classify_dense_canonical_groups(
    group_component_offsets,
    component_times,
    component_ends,
    component_dts,
    component_boards,
    component_channels,
    component_baselines,
    group_time_starts,
    group_spans,
    group_status,
):
    """Classify one dense canonical time axis per independent group.

    Status 0 is safe. Non-zero status deliberately re-enters the Python
    canonical oracle, which owns public validation and conflict provenance.
    """
    n_groups = len(group_component_offsets) - 1
    for group_index in nb.prange(n_groups):
        start = group_component_offsets[group_index]
        end = group_component_offsets[group_index + 1]
        if end <= start:
            group_status[group_index] = 1
            continue

        first_time = component_times[start]
        first_dt = component_dts[start]
        first_board = component_boards[start]
        first_channel = component_channels[start]
        if first_dt <= 0 or not np.isfinite(component_baselines[start]):
            group_status[group_index] = 1
            continue

        dt_ps = first_dt * 1000
        minimum_time = first_time
        maximum_end = component_ends[start]
        status = 0
        for component_index in range(start, end):
            if (
                component_dts[component_index] != first_dt
                or component_boards[component_index] != first_board
                or component_channels[component_index] != first_channel
                or not np.isfinite(component_baselines[component_index])
            ):
                status = 1
                break
            sample_time = component_times[component_index]
            if (sample_time - first_time) % dt_ps != 0:
                status = 2
                break
            if sample_time < minimum_time:
                minimum_time = sample_time
            if component_ends[component_index] > maximum_end:
                maximum_end = component_ends[component_index]

        if status == 0:
            span = (maximum_end - minimum_time) // dt_ps
            if span <= 0 or span > MAX_CANONICAL_DENSE_SAMPLES_PER_GROUP:
                status = 3
            else:
                group_time_starts[group_index] = minimum_time
                group_spans[group_index] = span
        group_status[group_index] = status


@nb.njit(cache=True, nogil=True)
def materialize_dense_canonical_groups(
    wave_pool,
    group_indices,
    group_component_offsets,
    group_pool_offsets,
    group_time_starts,
    ordered_record_indices,
    ordered_clipped_starts,
    ordered_clipped_ends,
    ordered_time_starts,
    ordered_dts,
    rec_wave_offset,
    rec_baseline,
    rec_polarity_sign,
    clip_negative_signal,
    values_out,
    values_bits_out,
    occupied_out,
    conflicts_out,
):
    """Write independent canonical axes into caller-owned dense buffers."""
    # This remains serial within a group batch: occupancy and bit-pattern
    # ownership make a parallel writer unsafe, while still keeping the loop
    # fully nopython and avoiding Python segment construction.
    for local_group_index in range(len(group_indices)):
        group_index = group_indices[local_group_index]
        component_start = group_component_offsets[group_index]
        component_end = group_component_offsets[group_index + 1]
        pool_start = group_pool_offsets[local_group_index]
        time_start = group_time_starts[local_group_index]
        has_conflict = 0

        for component_index in range(component_start, component_end):
            record_index = ordered_record_indices[component_index]
            clipped_start = ordered_clipped_starts[component_index]
            clipped_end = ordered_clipped_ends[component_index]
            dt_ps = ordered_dts[component_index] * 1000
            sample_offset = (ordered_time_starts[component_index] - time_start) // dt_ps
            wave_offset = rec_wave_offset[record_index]
            baseline = rec_baseline[record_index]
            polarity_sign = rec_polarity_sign[record_index]

            for sample_index in range(clipped_end - clipped_start):
                pool_index = pool_start + sample_offset + sample_index
                raw = np.float32(wave_pool[wave_offset + clipped_start + sample_index])
                value = polarity_sign * (raw - baseline)
                if clip_negative_signal and value < np.float32(0.0):
                    value = np.float32(0.0)
                value_bits = float32_bits(value)
                if occupied_out[pool_index] == 0:
                    values_out[pool_index] = value
                    values_bits_out[pool_index] = value_bits
                    occupied_out[pool_index] = 1
                elif values_bits_out[pool_index] != value_bits:
                    has_conflict = 1
        conflicts_out[local_group_index] = has_conflict


__all__ = [
    "MAX_CANONICAL_DENSE_SAMPLES_PER_BATCH",
    "MAX_CANONICAL_DENSE_SAMPLES_PER_GROUP",
    "classify_dense_canonical_groups",
    "materialize_dense_canonical_groups",
]
