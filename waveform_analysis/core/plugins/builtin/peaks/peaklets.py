"""Peaklet clustering, ragged waveforms, features, and final peaks."""

import logging
from multiprocessing import Pool, cpu_count
import time
from typing import Any
import warnings

import numpy as np

try:
    from numba import njit

    HAS_NUMBA = True
except ImportError:
    HAS_NUMBA = False

    def njit(*args, **kwargs):
        if len(args) == 1 and callable(args[0]):
            return args[0]
        return lambda f: f


from waveform_analysis.core.plugins.builtin.cpu._dt_compat import resolve_dt_config
from waveform_analysis.core.plugins.builtin.cpu._record_utils import RecordLookup
from waveform_analysis.core.plugins.core.base import Option, Plugin
from waveform_analysis.core.plugins.core.batch_processing import BatchProcessingPlugin
from waveform_analysis.core.processing.chunk import Chunk

logger = logging.getLogger(__name__)
HAS_MULTIPROCESSING = True

PEAKLET_DTYPE = np.dtype(
    [
        ("time_start", "i8"),
        ("time_end", "i8"),
        ("center_time", "i8"),
        ("n_hits", "i4"),
        ("n_channels", "i4"),
        ("component_offset", "i8"),
        ("component_count", "i4"),
    ]
)

PEAKLET_COMPONENTS_DTYPE = np.dtype(
    [
        ("peak_id", "i8"),
        ("merged_index", "i8"),
    ]
)

PEAKLET_WAVEFORMS_DTYPE = np.dtype(
    [
        ("peak_id", "i8"),
        ("time_start", "i8"),
        ("time_end", "i8"),
        ("dt", "i4"),
        ("wave_offset", "i8"),
        ("wave_length", "i4"),
    ]
)

PEAKLET_FEATURES_DTYPE = np.dtype(
    [
        ("peak_id", "i8"),
        ("time_start", "i8"),
        ("time_end", "i8"),
        ("time_peak", "i8"),
        ("center_time", "i8"),
        ("rise_time", "f4"),
        ("fall_time", "f4"),
        ("width_25_75", "f4"),
        ("rise_time_10_50", "f4"),
        ("range_90p_area", "f4"),
        ("area", "f4"),
        ("height", "f4"),
        ("width", "f4"),
    ]
)

PEAKS_DTYPE = np.dtype(
    [
        ("peak_id", "i8"),
        ("time_start", "i8"),
        ("time_end", "i8"),
        ("time_peak", "i8"),
        ("center_time", "i8"),
        ("rise_time", "f4"),
        ("fall_time", "f4"),
        ("width_25_75", "f4"),
        ("rise_time_10_50", "f4"),
        ("range_90p_area", "f4"),
        ("area", "f4"),
        ("height", "f4"),
        ("width", "f4"),
        ("n_hits", "i4"),
        ("n_channels", "i4"),
    ]
)

_AREA_QUANTILES = np.asarray((0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95), dtype=np.float64)


def _empty_peaklets() -> np.ndarray:
    return np.zeros(0, dtype=PEAKLET_DTYPE)


def _empty_components() -> np.ndarray:
    return np.zeros(0, dtype=PEAKLET_COMPONENTS_DTYPE)


def _empty_waveforms() -> np.ndarray:
    return np.zeros(0, dtype=PEAKLET_WAVEFORMS_DTYPE)


def _empty_waveform_pool() -> np.ndarray:
    return np.zeros(0, dtype=np.float32)


def _empty_features() -> np.ndarray:
    return np.zeros(0, dtype=PEAKLET_FEATURES_DTYPE)


def _empty_peaks() -> np.ndarray:
    return np.zeros(0, dtype=PEAKS_DTYPE)


def _compute_area_quantile_times(
    wave: np.ndarray,
    time_start: int,
    dt_ns: int,
    quantiles: np.ndarray = _AREA_QUANTILES,
) -> np.ndarray:
    """Return cumulative-area quantile times in ps for a baseline-corrected waveform."""
    n = len(wave)
    if n == 0:
        return np.full(len(quantiles), int(time_start), dtype=np.int64)

    total_area = float(np.sum(wave, dtype=np.float64))
    if total_area <= 0:
        return np.full(len(quantiles), int(time_start), dtype=np.int64)

    cumsum = np.cumsum(wave, dtype=np.float64)
    targets = quantiles * total_area
    dt_ps = int(dt_ns) * 1000

    idx = np.searchsorted(cumsum, targets, side="left")
    sample_pos = np.empty(len(quantiles), dtype=np.float64)

    mask_hi = idx >= n
    mask_0 = idx == 0
    mask_mid = (~mask_hi) & (~mask_0)

    sample_pos[mask_hi] = float(n - 1)
    sample_pos[mask_0] = 0.0

    if np.any(mask_mid):
        idx_mid = idx[mask_mid]
        targets_mid = targets[mask_mid]
        c0 = cumsum[idx_mid - 1]
        c1 = cumsum[idx_mid]

        exact = c1 == targets_mid
        valid = (~exact) & (c1 > c0)
        values = np.empty_like(targets_mid, dtype=np.float64)

        values[exact] = idx_mid[exact].astype(np.float64)
        values[valid] = (idx_mid[valid] - 1).astype(np.float64) + (
            targets_mid[valid] - c0[valid]
        ) / (c1[valid] - c0[valid])
        values[(~exact) & (~valid)] = idx_mid[(~exact) & (~valid)].astype(np.float64)

        sample_pos[mask_mid] = values

    return (int(time_start) + sample_pos * dt_ps).astype(np.int64)


@njit(cache=True, nogil=True)
def _compute_features_numba(
    pool,
    peaklet_indices,
    offsets,
    lengths,
    time_starts,
    time_ends,
    dt_ns_arr,
    out,
):
    """Numba-accelerated feature computation for peaklet waveforms."""
    n = len(out)
    quantiles = np.array([0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95], dtype=np.float64)

    for i in range(n):
        peaklet_id = peaklet_indices[i]
        offset = offsets[i]
        length = lengths[i]
        time_start = time_starts[i]
        time_end = time_ends[i]
        dt_ns = dt_ns_arr[i]

        out[i]["peak_id"] = peaklet_id
        out[i]["time_start"] = time_start
        out[i]["time_end"] = time_end

        if length <= 0:
            out[i]["time_peak"] = time_start
            out[i]["center_time"] = time_start
            continue

        wave = pool[offset : offset + length]
        total_area = np.sum(wave)

        if total_area <= 0:
            out[i]["time_peak"] = time_start
            out[i]["center_time"] = time_start
            out[i]["area"] = 0.0
            out[i]["height"] = 0.0
            out[i]["width"] = (time_end - time_start) / 1000.0
            continue

        # Cumulative area quantiles
        cumsum = np.cumsum(wave)
        dt_ps = dt_ns * 1000
        quantile_times = np.empty(7, dtype=np.int64)

        for q_idx in range(7):
            target = quantiles[q_idx] * total_area
            idx = np.searchsorted(cumsum, target)

            if idx >= length:
                sample_pos = float(length - 1)
            elif idx == 0:
                sample_pos = 0.0
            else:
                c0 = cumsum[idx - 1]
                c1 = cumsum[idx]
                if c1 == target:
                    sample_pos = float(idx)
                elif c1 > c0:
                    sample_pos = float(idx - 1) + (target - c0) / (c1 - c0)
                else:
                    sample_pos = float(idx)

            quantile_times[q_idx] = int(time_start + sample_pos * dt_ps)

        t05, t10, t25, t50, t75, t90, t95 = quantile_times

        # Peak time
        max_idx = np.argmax(wave)
        time_peak = int(time_start + max_idx * dt_ps)

        # Features
        out[i]["time_peak"] = time_peak
        out[i]["center_time"] = t50
        out[i]["rise_time"] = (time_peak - t10) / 1000.0
        out[i]["fall_time"] = (t90 - time_peak) / 1000.0
        out[i]["width_25_75"] = (t75 - t25) / 1000.0
        out[i]["rise_time_10_50"] = (t50 - t10) / 1000.0
        out[i]["range_90p_area"] = (t95 - t05) / 1000.0
        out[i]["area"] = total_area
        out[i]["height"] = wave[max_idx]
        out[i]["width"] = (time_end - time_start) / 1000.0


def _record_array(obj: Any) -> np.ndarray:
    if isinstance(obj, np.ndarray):
        return obj
    if hasattr(obj, "records"):
        return np.asarray(obj.records)
    raise ValueError("peaklet waveform plugins expect records as a structured array")


def _wave_pool_array(obj: Any) -> np.ndarray:
    if obj is None:
        raise ValueError("peaklet waveform plugins require wave_pool or wave_pool_filtered")
    return np.asarray(obj)


def _field_or_default(row: np.void, name: str, default: int) -> int:
    return int(row[name]) if name in (row.dtype.names or ()) else int(default)


def _record_polarity(record: np.void) -> str:
    names = record.dtype.names or ()
    if "polarity" not in names:
        return "negative"
    value = record["polarity"]
    if isinstance(value, bytes):
        value = value.decode(errors="ignore")
    else:
        value = str(value)
    return value if value in {"positive", "negative"} else "negative"


def _hit_sample_window(row: np.void) -> tuple[int, int]:
    names = row.dtype.names or ()
    if {"sample_start", "sample_end"}.issubset(names):
        return int(row["sample_start"]), int(row["sample_end"])
    if {"edge_start", "edge_end"}.issubset(names):
        return int(row["edge_start"]), int(row["edge_end"])
    raise KeyError("peaklet inputs require sample_start/sample_end or edge_start/edge_end")


def _hit_abs_window(row: np.void) -> tuple[int, int]:
    sample_start, sample_end = _hit_sample_window(row)
    dt_ps = int(row["dt"]) * 1000
    timestamp = _field_or_default(row, "timestamp", 0)
    position = _field_or_default(row, "position", 0)
    return (
        timestamp + (sample_start - position) * dt_ps,
        timestamp + (sample_end - position) * dt_ps,
    )


def _abs_window(rows: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    names = rows.dtype.names or ()
    if {"time_start", "time_end"}.issubset(names):
        return (
            rows["time_start"].astype(np.float64, copy=False),
            rows["time_end"].astype(np.float64, copy=False),
        )

    if {"sample_start", "sample_end"}.issubset(names):
        sample_starts = rows["sample_start"].astype(np.float64, copy=False)
        sample_ends = rows["sample_end"].astype(np.float64, copy=False)
    elif {"edge_start", "edge_end"}.issubset(names):
        sample_starts = rows["edge_start"].astype(np.float64, copy=False)
        sample_ends = rows["edge_end"].astype(np.float64, copy=False)
    else:
        raise KeyError("peaklet inputs require sample_start/sample_end or edge_start/edge_end")

    dt_ps = rows["dt"].astype(np.float64, copy=False) * 1000.0
    timestamps = (
        rows["timestamp"].astype(np.float64, copy=False)
        if "timestamp" in names
        else np.zeros(len(rows), dtype=np.float64)
    )
    positions = (
        rows["position"].astype(np.float64, copy=False)
        if "position" in names
        else np.zeros(len(rows), dtype=np.float64)
    )
    return (
        timestamps + (sample_starts - positions) * dt_ps,
        timestamps + (sample_ends - positions) * dt_ps,
    )


@njit(cache=True, nogil=True)
def _cluster_peaklets_numba(
    abs_starts: np.ndarray,
    abs_ends: np.ndarray,
    order: np.ndarray,
    gap_ps: float,
    max_width_ps: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Numba-accelerated peaklet clustering.

    Returns (cluster_starts, cluster_ends) as index arrays into the order array.
    Each cluster spans order[starts[i]:ends[i]].
    """
    n = len(order)
    if n == 0:
        return (np.empty(0, dtype=np.int32), np.empty(0, dtype=np.int32))

    # Pre-allocate for worst case (no merging)
    starts = np.empty(n, dtype=np.int32)
    ends = np.empty(n, dtype=np.int32)
    n_clusters = 0

    cluster_start_idx = 0
    first_idx = int(order[0])
    cluster_start_ps = abs_starts[first_idx]
    cluster_end_ps = abs_ends[first_idx]

    for i in range(1, n):
        idx = int(order[i])
        next_start = abs_starts[idx]
        next_end = abs_ends[idx]

        # 计算合并后的边界
        merged_end = max(cluster_end_ps, next_end)
        total_width = merged_end - cluster_start_ps
        gap = next_start - cluster_end_ps

        if gap <= gap_ps and total_width <= max_width_ps:
            # 合并到当前 cluster
            cluster_end_ps = merged_end
        else:
            # 保存当前 cluster
            starts[n_clusters] = cluster_start_idx
            ends[n_clusters] = i
            n_clusters += 1
            # 开始新 cluster
            cluster_start_idx = i
            cluster_start_ps = next_start
            cluster_end_ps = next_end

    # 保存最后一个 cluster
    starts[n_clusters] = cluster_start_idx
    ends[n_clusters] = n
    n_clusters += 1

    return (starts[:n_clusters].copy(), ends[:n_clusters].copy())


def _cluster_merged_hit_boundaries(
    merged: np.ndarray,
    time_window_ns: float,
    max_total_width_ns: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    if len(merged) == 0:
        return (
            np.empty(0, dtype=np.int64),
            np.empty(0, dtype=np.int32),
            np.empty(0, dtype=np.int32),
        )
    if time_window_ns < 0:
        raise ValueError("peaklets.time_window_ns must be >= 0")
    if max_total_width_ns <= 0:
        raise ValueError("peaklets.max_total_width_ns must be > 0")

    abs_starts, abs_ends = _abs_window(merged)
    order = np.argsort(abs_starts, kind="mergesort")
    gap_ps = time_window_ns * 1000.0
    max_width_ps = max_total_width_ns * 1000.0

    # 直接调用 Numba 版本（无 fallback）
    if not HAS_NUMBA:
        raise RuntimeError("Numba is required for peaklet clustering")

    cluster_starts, cluster_ends = _cluster_peaklets_numba(
        abs_starts, abs_ends, order, gap_ps, max_width_ps
    )
    return order.astype(np.int64, copy=False), cluster_starts, cluster_ends


def _cluster_merged_hits(
    merged: np.ndarray,
    time_window_ns: float,
    max_total_width_ns: float,
) -> list[list[int]]:
    order, cluster_starts, cluster_ends = _cluster_merged_hit_boundaries(
        merged,
        time_window_ns=time_window_ns,
        max_total_width_ns=max_total_width_ns,
    )

    # 将 Numba 结果转换为原始格式
    clusters: list[list[int]] = []
    for i in range(len(cluster_starts)):
        start = int(cluster_starts[i])
        end = int(cluster_ends[i])
        cluster = [int(order[j]) for j in range(start, end)]
        clusters.append(cluster)

    return clusters


@njit(cache=True, nogil=True)
def _fill_peaklet_components_numba(
    order: np.ndarray,
    cluster_starts: np.ndarray,
    cluster_ends: np.ndarray,
    out_peak_ids: np.ndarray,
    out_merged_indices: np.ndarray,
) -> None:
    out_i = 0
    for peaklet_id in range(len(cluster_starts)):
        start = cluster_starts[peaklet_id]
        end = cluster_ends[peaklet_id]
        for member_i in range(start, end):
            out_peak_ids[out_i] = peaklet_id
            out_merged_indices[out_i] = order[member_i]
            out_i += 1


def _components_by_peaklet(components: np.ndarray, n_peaklets: int) -> list[np.ndarray]:
    out: list[list[int]] = [[] for _ in range(n_peaklets)]
    for row in components:
        peaklet_id = int(row["peak_id"])
        if 0 <= peaklet_id < n_peaklets:
            out[peaklet_id].append(int(row["merged_index"]))
    return [np.asarray(rows, dtype=np.int64) for rows in out]


def _has_explicit_plugin_config(context: Any, plugin_name: str, name: str) -> bool:
    config = getattr(context, "config", {})
    if not isinstance(config, dict):
        return False
    plugin_config = config.get(plugin_name)
    if isinstance(plugin_config, dict) and name in plugin_config:
        return True
    return f"{plugin_name}.{name}" in config


def _resolve_peaklet_component_config(context: Any, plugin: Plugin, name: str) -> Any:
    if not _has_explicit_plugin_config(
        context, plugin.provides, name
    ) and _has_explicit_plugin_config(context, "peaklets", name):
        return context.get_config(PeakletPlugin(), name)
    return context.get_config(plugin, name)


def _store_context_memory(context: Any, run_id: str, name: str, value: Any) -> None:
    set_data = getattr(context, "_set_data", None)
    if callable(set_data):
        set_data(run_id, name, value)
        return
    data = getattr(context, "_data", None)
    if isinstance(data, dict):
        data[name] = value


def _get_context_memory(context: Any, run_id: str, name: str) -> Any:
    get_data = getattr(context, "_get_data_from_memory", None)
    if callable(get_data):
        return get_data(run_id, name)
    results = getattr(context, "_results", None)
    if isinstance(results, dict) and (run_id, name) in results:
        return results[(run_id, name)]
    data = getattr(context, "_data", None)
    if isinstance(data, dict):
        return data.get(name)
    return None


def _prepare_component_groups(
    components: np.ndarray, n_peaklets: int
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Pre-group components by peak_id for efficient iteration.

    Returns
    -------
    grouped_merged_indices : np.ndarray
        Sorted merged_index array
    group_starts : np.ndarray (n_peaklets,)
        Start index in grouped_merged_indices for each peaklet (-1 if empty)
    group_ends : np.ndarray (n_peaklets,)
        End index in grouped_merged_indices for each peaklet (-1 if empty)
    """
    if len(components) == 0:
        return (
            np.array([], dtype=np.int64),
            np.full(n_peaklets, -1, dtype=np.int64),
            np.full(n_peaklets, -1, dtype=np.int64),
        )

    peak_ids = components["peak_id"].astype(np.int64, copy=False)
    valid = (peak_ids >= 0) & (peak_ids < n_peaklets)
    if not np.any(valid):
        return (
            np.array([], dtype=np.int64),
            np.full(n_peaklets, -1, dtype=np.int64),
            np.full(n_peaklets, -1, dtype=np.int64),
        )

    valid_peak_ids = peak_ids[valid]
    is_grouped = bool(np.all(valid)) and bool(np.all(peak_ids[1:] >= peak_ids[:-1]))
    if is_grouped:
        sorted_peak_ids = peak_ids
        merged_indices = components["merged_index"].astype(np.int64, copy=False)
    else:
        valid_rows = np.flatnonzero(valid)
        order = np.argsort(valid_peak_ids, kind="mergesort")
        sorted_rows = valid_rows[order]
        sorted_peak_ids = peak_ids[sorted_rows]
        merged_indices = components["merged_index"][sorted_rows].astype(np.int64, copy=False)

    # Find group boundaries
    starts = np.full(n_peaklets, -1, dtype=np.int64)
    ends = np.full(n_peaklets, -1, dtype=np.int64)

    change = np.r_[True, sorted_peak_ids[1:] != sorted_peak_ids[:-1]]
    group_starts_idx = np.flatnonzero(change)
    group_ends_idx = np.r_[group_starts_idx[1:], len(sorted_peak_ids)]
    group_peak_ids = sorted_peak_ids[group_starts_idx]
    starts[group_peak_ids] = group_starts_idx
    ends[group_peak_ids] = group_ends_idx

    return merged_indices, starts, ends


@njit(cache=True, nogil=True)
def _summarize_peaklets_numba(
    grouped_merged_indices: np.ndarray,
    group_starts: np.ndarray,
    group_ends: np.ndarray,
    abs_starts: np.ndarray,
    abs_ends: np.ndarray,
    boards: np.ndarray,
    channels: np.ndarray,
    component_counts: np.ndarray,
    has_component_counts: bool,
    out: np.ndarray,
) -> None:
    component_offset = 0
    for peaklet_id in range(len(out)):
        start = group_starts[peaklet_id]
        end = group_ends[peaklet_id]
        out[peaklet_id]["component_offset"] = component_offset
        if start < 0 or end <= start:
            continue

        first_merged_index = grouped_merged_indices[start]
        time_start = abs_starts[first_merged_index]
        time_end = abs_ends[first_merged_index]
        n_hits = 0
        n_channels = 0

        for member_i in range(start, end):
            merged_index = grouped_merged_indices[member_i]
            if abs_starts[merged_index] < time_start:
                time_start = abs_starts[merged_index]
            if abs_ends[merged_index] > time_end:
                time_end = abs_ends[merged_index]

            if has_component_counts:
                n_hits += component_counts[merged_index]
            else:
                n_hits += 1

            seen = False
            board = boards[merged_index]
            channel = channels[merged_index]
            for previous_i in range(start, member_i):
                previous_index = grouped_merged_indices[previous_i]
                if boards[previous_index] == board and channels[previous_index] == channel:
                    seen = True
                    break
            if not seen:
                n_channels += 1

        out[peaklet_id]["time_start"] = int(time_start)
        out[peaklet_id]["time_end"] = int(time_end)
        out[peaklet_id]["center_time"] = int((time_start + time_end) // 2)
        out[peaklet_id]["n_hits"] = n_hits
        out[peaklet_id]["n_channels"] = n_channels
        out[peaklet_id]["component_count"] = end - start
        component_offset += end - start


def _build_peaklet_component_csr(
    components: np.ndarray, n_peaklets: int
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Return CSR-like peaklet_id -> merged_index membership arrays.

    For peaklet_id, grouped_merged_indices[starts[peaklet_id]:ends[peaklet_id]]
    contains the merged indices belonging to that peaklet. Empty groups use
    starts=-1 and ends=-1.
    """
    return _prepare_component_groups(components, n_peaklets)


def _build_hmc_csr(
    hit_merged_components: np.ndarray, n_merged: int
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Return CSR-like merged_index -> hit_threshold index membership arrays.

    For merged_index, grouped_hit_indices[starts[merged_index]:ends[merged_index]]
    contains the hit_threshold indices belonging to that merged hit. Empty
    groups use starts=-1 and ends=-1.
    """
    if len(hit_merged_components) == 0:
        return (
            np.array([], dtype=np.int64),
            np.full(n_merged, -1, dtype=np.int64),
            np.full(n_merged, -1, dtype=np.int64),
        )

    order = np.argsort(hit_merged_components["merged_index"], kind="mergesort")
    merged_indices = hit_merged_components["merged_index"][order].astype(np.int64, copy=False)
    hit_indices = hit_merged_components["hit_index"][order].astype(np.int64, copy=False)

    starts = np.full(n_merged, -1, dtype=np.int64)
    ends = np.full(n_merged, -1, dtype=np.int64)
    change = np.r_[True, merged_indices[1:] != merged_indices[:-1]]
    group_starts_idx = np.flatnonzero(change)
    group_ends_idx = np.r_[group_starts_idx[1:], len(merged_indices)]

    for s, e in zip(group_starts_idx, group_ends_idx, strict=False):
        merged_index = int(merged_indices[s])
        if 0 <= merged_index < n_merged:
            starts[merged_index] = s
            ends[merged_index] = e

    return hit_indices, starts, ends


def _build_hit_merged_components_index(
    hit_merged_components: np.ndarray,
) -> dict[int, np.ndarray]:
    """
    Build index mapping merged_index -> hit_indices for fast lookup.

    Returns
    -------
    dict[int, np.ndarray]
        Map from merged_index to array of hit_threshold indices
    """
    out: dict[int, list[int]] = {}
    for row in hit_merged_components:
        merged_idx = int(row["merged_index"])
        hit_idx = int(row["hit_index"])
        out.setdefault(merged_idx, []).append(hit_idx)
    return {k: np.asarray(v, dtype=np.int64) for k, v in out.items()}


def _validate_peaklet_components(
    *,
    peaklets: np.ndarray,
    components: np.ndarray,
    consumer: str,
) -> None:
    if "component_count" not in (peaklets.dtype.names or ()):
        return
    if len(components) == 0 and len(peaklets) == 0:
        return

    counts = np.zeros(len(peaklets), dtype=np.int64)
    for row in components:
        peaklet_id = int(row["peak_id"])
        if not 0 <= peaklet_id < len(peaklets):
            raise ValueError(
                f"{consumer} found peaklet_components row with out-of-range "
                f"peak_id={peaklet_id}"
            )
        counts[peaklet_id] += 1

    expected = peaklets["component_count"].astype(np.int64, copy=False)
    if not np.array_equal(counts, expected):
        raise ValueError(f"{consumer} found peaklet_components inconsistent with peaklets")


def _extract_polarity_signs(records: np.ndarray) -> np.ndarray:
    """批量提取 record 的 polarity 符号数组（用于 Numba）"""
    names = records.dtype.names or ()
    if "polarity" not in names:
        return np.full(len(records), -1.0, dtype=np.float32)

    pol = records["polarity"]
    sign_arr = np.full(len(records), -1.0, dtype=np.float32)

    if pol.dtype.kind == "S":
        sign_arr[pol == b"positive"] = 1.0
    elif pol.dtype.kind == "U":
        sign_arr[pol == "positive"] = 1.0
    else:
        for i, p in enumerate(pol):
            p_str = p.decode("utf-8") if isinstance(p, bytes) else str(p)
            if p_str == "positive":
                sign_arr[i] = 1.0

    return sign_arr


@njit(cache=True, nogil=True)
def _build_waveforms_numba(
    component_peak_ids,
    component_merged_indices,
    merged_record_ids,
    merged_sample_starts,
    merged_sample_ends,
    merged_dt,
    record_indices,
    record_dt,
    record_baseline,
    record_wave_offset,
    record_event_length,
    record_timestamp,
    record_sign,
    wave_pool,
    clip_negative_signal,
):
    """Numba 加速的波形构建核心"""
    n_peaklets = int(np.max(component_peak_ids)) + 1 if len(component_peak_ids) > 0 else 0

    # 预分配输出（最坏情况：每个 peaklet 都有数据）
    waveform_rows = np.zeros((n_peaklets, 6), dtype=np.int64)
    pool_pieces = []
    pool_lengths = np.zeros(n_peaklets, dtype=np.int64)
    wave_offset_total = 0

    for peaklet_id in range(n_peaklets):
        # 获取该 peaklet 的 component
        comp_mask = component_peak_ids == peaklet_id
        merged_idxs = component_merged_indices[comp_mask]

        if len(merged_idxs) == 0:
            waveform_rows[peaklet_id] = np.array(
                [peaklet_id, 0, 0, 0, wave_offset_total, 0], dtype=np.int64
            )
            continue

        # 收集所有 pieces 的时间范围和信号
        n_pieces = len(merged_idxs)
        piece_time_starts = np.empty(n_pieces, dtype=np.int64)
        piece_time_ends = np.empty(n_pieces, dtype=np.int64)
        piece_signals = []
        piece_dt_ns = -1

        valid_pieces = 0
        for i in range(n_pieces):
            merged_idx = merged_idxs[i]
            rec_idx = record_indices[merged_idx]

            sample_start = merged_sample_starts[merged_idx]
            sample_end = merged_sample_ends[merged_idx]

            rec_dt = record_dt[rec_idx]
            rec_length = record_event_length[rec_idx]

            # 检查 dt 一致性
            if piece_dt_ns == -1:
                piece_dt_ns = rec_dt
            elif rec_dt != piece_dt_ns:
                # 混合 dt，返回错误标记
                waveform_rows[peaklet_id] = np.array(
                    [peaklet_id, -1, -1, -1, wave_offset_total, 0], dtype=np.int64
                )
                valid_pieces = -1
                break

            # 裁剪边界
            start = max(0, sample_start)
            end = min(rec_length, sample_end)

            if end <= start:
                continue

            # 计算时间范围
            dt_ps = rec_dt * 1000
            timestamp = record_timestamp[rec_idx]
            time_start = timestamp + start * dt_ps
            time_end = timestamp + end * dt_ps

            # 提取信号
            wave_off = record_wave_offset[rec_idx]
            baseline = record_baseline[rec_idx]
            sign = record_sign[rec_idx]

            raw = wave_pool[wave_off + start : wave_off + end].astype(np.float32)
            signal = sign * (raw - np.float32(baseline))
            if clip_negative_signal:
                signal = np.maximum(signal, 0.0)

            piece_time_starts[valid_pieces] = time_start
            piece_time_ends[valid_pieces] = time_end
            piece_signals.append(signal)
            valid_pieces += 1

        if valid_pieces == -1:
            # 混合 dt 错误
            continue

        if valid_pieces == 0 or piece_dt_ns == -1:
            waveform_rows[peaklet_id] = np.array(
                [peaklet_id, 0, 0, 0, wave_offset_total, 0], dtype=np.int64
            )
            continue

        # 对齐和求和
        piece_time_starts = piece_time_starts[:valid_pieces]
        piece_time_ends = piece_time_ends[:valid_pieces]

        global_time_start = np.min(piece_time_starts)
        global_time_end = np.max(piece_time_ends)
        dt_ps = piece_dt_ns * 1000
        wave_length = int((global_time_end - global_time_start) // dt_ps)

        summed = np.zeros(wave_length, dtype=np.float32)
        for i in range(valid_pieces):
            start_offset = int((piece_time_starts[i] - global_time_start) // dt_ps)
            signal = piece_signals[i]
            summed[start_offset : start_offset + len(signal)] += signal

        waveform_rows[peaklet_id] = np.array(
            [
                peaklet_id,
                global_time_start,
                global_time_end,
                piece_dt_ns,
                wave_offset_total,
                wave_length,
            ],
            dtype=np.int64,
        )
        pool_pieces.append(summed)
        pool_lengths[peaklet_id] = wave_length
        wave_offset_total += wave_length

    # 拼接 pool
    if len(pool_pieces) > 0:
        pool = np.concatenate(pool_pieces)
    else:
        pool = np.zeros(0, dtype=np.float32)

    return waveform_rows, pool


@njit(cache=True, nogil=True)
def _first_pass_cross_record_numba(
    grouped_merged_indices,
    peaklet_comp_starts,
    peaklet_comp_ends,
    direct_merged,
    merged_record_indices,
    merged_sample_starts,
    merged_sample_ends,
    grouped_hit_indices,
    merged_hit_starts,
    merged_hit_ends,
    hit_record_indices,
    hit_sample_starts,
    hit_sample_ends,
    record_dt,
    record_event_length,
    record_timestamp,
):
    n_peaklets = len(peaklet_comp_starts)
    waveform_rows = np.zeros((n_peaklets, 6), dtype=np.int64)
    total_wave_length = 0

    for peaklet_id in range(n_peaklets):
        comp_start = peaklet_comp_starts[peaklet_id]
        comp_end = peaklet_comp_ends[peaklet_id]
        if comp_start < 0 or comp_end <= comp_start:
            waveform_rows[peaklet_id, 0] = peaklet_id
            waveform_rows[peaklet_id, 4] = total_wave_length
            continue

        dt_ns = -1
        time_start = 0
        time_end = 0
        has_piece = False

        for comp_i in range(comp_start, comp_end):
            merged_index = grouped_merged_indices[comp_i]
            if merged_index < 0 or merged_index >= len(direct_merged):
                continue
            if direct_merged[merged_index]:
                rec_idx = merged_record_indices[merged_index]
                if rec_idx < 0 or rec_idx >= len(record_dt):
                    continue
                piece_dt = record_dt[rec_idx]
                if dt_ns == -1:
                    dt_ns = piece_dt
                elif piece_dt != dt_ns:
                    waveform_rows[peaklet_id, 0] = peaklet_id
                    waveform_rows[peaklet_id, 1] = -1
                    waveform_rows[peaklet_id, 2] = -1
                    waveform_rows[peaklet_id, 3] = -1
                    waveform_rows[peaklet_id, 4] = total_wave_length
                    waveform_rows[peaklet_id, 5] = 0
                    has_piece = False
                    dt_ns = -2
                    break

                start = merged_sample_starts[merged_index]
                end = merged_sample_ends[merged_index]
                if start < 0:
                    start = 0
                rec_length = record_event_length[rec_idx]
                if end > rec_length:
                    end = rec_length
                if end <= start:
                    continue
                dt_ps = piece_dt * 1000
                abs_start = record_timestamp[rec_idx] + start * dt_ps
                abs_end = record_timestamp[rec_idx] + end * dt_ps
                if not has_piece:
                    time_start = abs_start
                    time_end = abs_end
                    has_piece = True
                else:
                    if abs_start < time_start:
                        time_start = abs_start
                    if abs_end > time_end:
                        time_end = abs_end
                continue

            hit_start = merged_hit_starts[merged_index]
            hit_end = merged_hit_ends[merged_index]
            if hit_start < 0 or hit_end <= hit_start:
                continue

            for hmc_i in range(hit_start, hit_end):
                hit_index = grouped_hit_indices[hmc_i]
                if hit_index < 0 or hit_index >= len(hit_record_indices):
                    continue
                rec_idx = hit_record_indices[hit_index]
                if rec_idx < 0 or rec_idx >= len(record_dt):
                    continue

                piece_dt = record_dt[rec_idx]
                if dt_ns == -1:
                    dt_ns = piece_dt
                elif piece_dt != dt_ns:
                    waveform_rows[peaklet_id, 0] = peaklet_id
                    waveform_rows[peaklet_id, 1] = -1
                    waveform_rows[peaklet_id, 2] = -1
                    waveform_rows[peaklet_id, 3] = -1
                    waveform_rows[peaklet_id, 4] = total_wave_length
                    waveform_rows[peaklet_id, 5] = 0
                    has_piece = False
                    dt_ns = -2
                    break

                start = hit_sample_starts[hit_index]
                end = hit_sample_ends[hit_index]
                if start < 0:
                    start = 0
                rec_length = record_event_length[rec_idx]
                if end > rec_length:
                    end = rec_length
                if end <= start:
                    continue

                dt_ps = piece_dt * 1000
                abs_start = record_timestamp[rec_idx] + start * dt_ps
                abs_end = record_timestamp[rec_idx] + end * dt_ps
                if not has_piece:
                    time_start = abs_start
                    time_end = abs_end
                    has_piece = True
                else:
                    if abs_start < time_start:
                        time_start = abs_start
                    if abs_end > time_end:
                        time_end = abs_end
            if dt_ns == -2:
                break

        if dt_ns == -2:
            continue
        if not has_piece or dt_ns < 0:
            waveform_rows[peaklet_id, 0] = peaklet_id
            waveform_rows[peaklet_id, 4] = total_wave_length
            continue

        dt_ps = dt_ns * 1000
        wave_length = 0
        for comp_i in range(comp_start, comp_end):
            merged_index = grouped_merged_indices[comp_i]
            if merged_index < 0 or merged_index >= len(direct_merged):
                continue
            if direct_merged[merged_index]:
                rec_idx = merged_record_indices[merged_index]
                if rec_idx < 0 or rec_idx >= len(record_dt):
                    continue
                start = merged_sample_starts[merged_index]
                end = merged_sample_ends[merged_index]
                if start < 0:
                    start = 0
                rec_length = record_event_length[rec_idx]
                if end > rec_length:
                    end = rec_length
                if end <= start:
                    continue
                abs_start = record_timestamp[rec_idx] + start * dt_ps
                local_i0 = (abs_start - time_start) // dt_ps
                piece_end = local_i0 + (end - start)
                if piece_end > wave_length:
                    wave_length = piece_end
                continue

            hit_start = merged_hit_starts[merged_index]
            hit_end = merged_hit_ends[merged_index]
            if hit_start < 0 or hit_end <= hit_start:
                continue

            for hmc_i in range(hit_start, hit_end):
                hit_index = grouped_hit_indices[hmc_i]
                if hit_index < 0 or hit_index >= len(hit_record_indices):
                    continue
                rec_idx = hit_record_indices[hit_index]
                if rec_idx < 0 or rec_idx >= len(record_dt):
                    continue

                start = hit_sample_starts[hit_index]
                end = hit_sample_ends[hit_index]
                if start < 0:
                    start = 0
                rec_length = record_event_length[rec_idx]
                if end > rec_length:
                    end = rec_length
                if end <= start:
                    continue

                abs_start = record_timestamp[rec_idx] + start * dt_ps
                local_i0 = (abs_start - time_start) // dt_ps
                sample_length = end - start
                piece_end = local_i0 + sample_length
                if piece_end > wave_length:
                    wave_length = piece_end

        waveform_rows[peaklet_id, 0] = peaklet_id
        waveform_rows[peaklet_id, 1] = time_start
        waveform_rows[peaklet_id, 2] = time_end
        waveform_rows[peaklet_id, 3] = dt_ns
        waveform_rows[peaklet_id, 4] = total_wave_length
        waveform_rows[peaklet_id, 5] = wave_length
        total_wave_length += wave_length

    return waveform_rows, total_wave_length


@njit(cache=True, nogil=True)
def _fill_cross_record_pool_numba(
    pool,
    waveform_rows,
    grouped_merged_indices,
    peaklet_comp_starts,
    peaklet_comp_ends,
    direct_merged,
    merged_record_indices,
    merged_sample_starts,
    merged_sample_ends,
    grouped_hit_indices,
    merged_hit_starts,
    merged_hit_ends,
    hit_record_indices,
    hit_sample_starts,
    hit_sample_ends,
    record_dt,
    record_event_length,
    record_timestamp,
    record_wave_offset,
    record_baseline,
    record_sign,
    wave_pool,
    clip_negative_signal,
):
    n_peaklets = len(peaklet_comp_starts)
    for peaklet_id in range(n_peaklets):
        wave_length = waveform_rows[peaklet_id, 5]
        if wave_length <= 0:
            continue

        comp_start = peaklet_comp_starts[peaklet_id]
        comp_end = peaklet_comp_ends[peaklet_id]
        if comp_start < 0 or comp_end <= comp_start:
            continue

        wave_offset = waveform_rows[peaklet_id, 4]
        peaklet_time_start = waveform_rows[peaklet_id, 1]
        dt_ns = waveform_rows[peaklet_id, 3]
        dt_ps = dt_ns * 1000

        for comp_i in range(comp_start, comp_end):
            merged_index = grouped_merged_indices[comp_i]
            if merged_index < 0 or merged_index >= len(direct_merged):
                continue
            if direct_merged[merged_index]:
                rec_idx = merged_record_indices[merged_index]
                if rec_idx < 0 or rec_idx >= len(record_dt):
                    continue
                start = merged_sample_starts[merged_index]
                end = merged_sample_ends[merged_index]
                if start < 0:
                    start = 0
                rec_length = record_event_length[rec_idx]
                if end > rec_length:
                    end = rec_length
                if end <= start:
                    continue

                abs_start = record_timestamp[rec_idx] + start * dt_ps
                local_i0 = (abs_start - peaklet_time_start) // dt_ps
                src_offset = record_wave_offset[rec_idx] + start
                dst_offset = wave_offset + local_i0
                baseline = record_baseline[rec_idx]
                sign = record_sign[rec_idx]
                for sample_i in range(end - start):
                    signal = sign * (np.float32(wave_pool[src_offset + sample_i]) - baseline)
                    if (not clip_negative_signal) or signal > 0.0:
                        pool[dst_offset + sample_i] += signal
                continue

            hit_start = merged_hit_starts[merged_index]
            hit_end = merged_hit_ends[merged_index]
            if hit_start < 0 or hit_end <= hit_start:
                continue

            for hmc_i in range(hit_start, hit_end):
                hit_index = grouped_hit_indices[hmc_i]
                if hit_index < 0 or hit_index >= len(hit_record_indices):
                    continue
                rec_idx = hit_record_indices[hit_index]
                if rec_idx < 0 or rec_idx >= len(record_dt):
                    continue

                start = hit_sample_starts[hit_index]
                end = hit_sample_ends[hit_index]
                if start < 0:
                    start = 0
                rec_length = record_event_length[rec_idx]
                if end > rec_length:
                    end = rec_length
                if end <= start:
                    continue

                abs_start = record_timestamp[rec_idx] + start * dt_ps
                local_i0 = (abs_start - peaklet_time_start) // dt_ps
                src_offset = record_wave_offset[rec_idx] + start
                dst_offset = wave_offset + local_i0
                baseline = record_baseline[rec_idx]
                sign = record_sign[rec_idx]

                for sample_i in range(end - start):
                    signal = sign * (np.float32(wave_pool[src_offset + sample_i]) - baseline)
                    if (not clip_negative_signal) or signal > 0.0:
                        pool[dst_offset + sample_i] += signal


def _merged_wave_pieces_multirecord(
    *,
    hit: np.void,
    hit_merged_components_index: dict[int, np.ndarray],
    hit_threshold: np.ndarray,
    records: np.ndarray,
    record_lookup: RecordLookup,
    wave_pool: np.ndarray,
    merged_index: int,
    clip_negative_signal: bool,
) -> list[tuple[int, int, int, np.ndarray]]:
    """
    Extract multiple waveform pieces from a cross-record hit_merged.

    When a hit_merged spans multiple records (is_single_record=False, sample_start=-1),
    this function expands it into its component hits and extracts waveform from each.

    Parameters
    ----------
    hit : np.void
        The hit_merged record (cross-record case)
    hit_merged_components_index : dict[int, np.ndarray]
        Pre-built index mapping merged_index -> hit_indices
    hit_threshold : np.ndarray
        Original threshold hits
    records : np.ndarray
        Record metadata
    record_lookup : RecordLookup
        Fast record_id lookup
    wave_pool : np.ndarray
        Raw waveform pool
    merged_index : int
        The merged_index to expand

    Returns
    -------
    list of tuple
        List of (time_start_ps, time_end_ps, dt_ns, signal) tuples
    """
    # Get component hit indices from pre-built index
    hit_indices = hit_merged_components_index.get(merged_index)
    if hit_indices is None or len(hit_indices) == 0:
        return []

    component_hits = hit_threshold[hit_indices]
    pieces = []

    for component_hit in component_hits:
        record = record_lookup.get(int(component_hit["record_id"]))
        if record is None:
            continue

        names = record.dtype.names or ()

        # Get sample window from component hit (not from merged hit)
        hit_names = component_hit.dtype.names or ()
        if "edge_start" in hit_names and "edge_end" in hit_names:
            start = int(component_hit["edge_start"])
            end = int(component_hit["edge_end"])
        elif "sample_start" in hit_names and "sample_end" in hit_names:
            start = int(component_hit["sample_start"])
            end = int(component_hit["sample_end"])
        else:
            continue

        length = int(record["event_length"])
        start = max(0, start)
        end = min(length, end)

        if end <= start:
            continue

        dt_ns = int(record["dt"]) if "dt" in names else int(component_hit["dt"])
        dt_ps = dt_ns * 1000
        timestamp = (
            int(record["timestamp"])
            if "timestamp" in names
            else _field_or_default(component_hit, "timestamp", 0)
        )

        time_start = timestamp + start * dt_ps
        time_end = timestamp + end * dt_ps

        offset = int(record["wave_offset"])
        baseline = float(record["baseline"]) if "baseline" in names else 0.0
        raw = wave_pool[offset + start : offset + end].astype(np.float32, copy=False)

        if _record_polarity(record) == "positive":
            signal = raw - np.float32(baseline)
        else:
            signal = np.float32(baseline) - raw

        if clip_negative_signal:
            signal = np.maximum(signal, 0.0)
        signal = signal.astype(np.float32, copy=False)

        pieces.append((time_start, time_end, dt_ns, signal))

    return pieces


def _merged_wave_piece(
    *,
    hit: np.void,
    records: np.ndarray,
    record_lookup: RecordLookup,
    wave_pool: np.ndarray,
    clip_negative_signal: bool,
) -> tuple[int, int, int, np.ndarray]:
    """
    Extract waveform from a single-record hit_merged.

    Note: This function does not handle cross-record hit_merged (sample_start=-1).
    Caller should detect is_single_record and use _merged_wave_pieces_multirecord for cross-record cases.
    """
    start, end = _hit_sample_window(hit)

    # Detect cross-record marker
    if start < 0 or end < 0:
        # Cross-record case - return empty (caller should use multirecord path)
        dt_ns = int(hit["dt"]) if "dt" in hit.dtype.names else 2
        return (0, 0, dt_ns, np.zeros(0, dtype=np.float32))

    record = record_lookup.get(int(hit["record_id"]))
    names = record.dtype.names or ()
    length = int(record["event_length"])
    start = max(0, start)
    end = min(length, end)
    if end <= start:
        return (
            0,
            0,
            int(record["dt"]) if "dt" in names else int(hit["dt"]),
            np.zeros(0, dtype=np.float32),
        )

    dt_ns = int(record["dt"]) if "dt" in names else int(hit["dt"])
    dt_ps = dt_ns * 1000
    timestamp = (
        int(record["timestamp"]) if "timestamp" in names else _field_or_default(hit, "timestamp", 0)
    )
    time_start = timestamp + start * dt_ps
    time_end = timestamp + end * dt_ps

    offset = int(record["wave_offset"])
    baseline = float(record["baseline"]) if "baseline" in names else 0.0
    raw = wave_pool[offset + start : offset + end].astype(np.float32, copy=False)
    if _record_polarity(record) == "positive":
        signal = raw - np.float32(baseline)
    else:
        signal = np.float32(baseline) - raw
    if clip_negative_signal:
        signal = np.maximum(signal, 0.0)
    return time_start, time_end, dt_ns, signal.astype(np.float32, copy=False)


class PeakletPlugin(BatchProcessingPlugin):
    """Build lightweight cross-channel peaklet candidates from hit_merged rows."""

    provides = "peaklets"
    depends_on = ["hit_merged", "peaklet_components"]
    description = "Build lightweight cross-channel peaklets from hit_merged intervals."
    version = "1.2.0"
    output_dtype = PEAKLET_DTYPE
    save_when = "always"
    parallel = False
    agent_doc = {
        "overview": (
            "PeakletPlugin 负责在 hit_merged 与 peaklet_components 之上构建轻量级的跨通道 "
            "peaklet 候选对象。它本身不检测峰形，而是按 peaklet_components 提供的成员关系，"
            "把同一逻辑事件（可能横跨多个 (board, channel) 的 hit_merged 行）聚合为一条 "
            "peaklet 记录，并汇总出绝对时间范围、参与 hit 数与去重后的通道数。\n\n"
            "该插件是 hit 层与 peak 层之间的桥梁：下游的 peaklet_features 特征计算、"
            "peaklet_waveforms / peaklet_waveform_pool 波形还原以及最终的 peaks 表都以 "
            "peaklets 的行索引作为 peak_id，因此本插件的行序与 peak_id 约定是后续所有 "
            "peaklet 消费插件对齐的基础。\n\n"
            "实现上先按 peak_id 建立分组成员表并校验组件引用的合法性，再调用 Numba 聚合内核 "
            "`_summarize_peaklets_numba` 单次遍历完成时间范围、n_hits 与 n_channels 的汇总，"
            "输出为按行对齐的 PEAKLET_DTYPE 结构化数组。"
        ),
        "workflow_steps": [
            "读取输入：从 context 获取 `hit_merged` 与 `peaklet_components` 结构化数组；任一为空时直接返回空 peaklets 数组。",
            "推导 peaklet 数量：以 `peaklet_components['peak_id']` 的最大值加 1 作为 n_peaklets，不依赖外部计数状态。",
            "校验组件引用：调用 `_prepare_component_groups` 按 peak_id 建立分组成员表，并确保每个 `merged_index` 都落在 `hit_merged` 的行范围内，越界即抛错。",
            "计算绝对时间窗口：由 `hit_merged` 的时间戳与采样窗口推导每条记录的绝对起止时间（`_abs_window`），供跨通道聚合使用。",
            "聚合摘要：通过 Numba 内核 `_summarize_peaklets_numba` 对每组组件汇总最小/最大绝对时间、`n_hits` 与去重后的 `n_channels`，并连续记录成员在 `peaklet_components` 中的 `component_offset` 与 `component_count`。",
            "写回输出：返回按 `peak_id`（行序）排序的 `PEAKLET_DTYPE` 结构化数组。",
        ],
        "behavior_notes": [
            "Only `peaklet_components` row membership matters; per-channel hit details are not preserved here and are re-derived downstream via `peaklet_channels`.",
            "`time_start`/`time_end` are the min/max of member absolute windows and `center_time` is their midpoint `(time_start + time_end) // 2`.",
            "`n_hits` sums `hit_merged['component_count']` when present, otherwise counts members one by one; `n_channels` counts distinct `(board, channel)` pairs among members.",
            "`component_offset` accumulates contiguously across peaklets, so it points exactly into `peaklet_components`.",
            "Empty `peaklet_components` or non-positive peak-id range produce an empty `PEAKLET_DTYPE` array rather than an error.",
            "`dt` config is a compatibility fallback resolved via `resolve_dt_config`; the effective sample interval is taken from `hit_merged` when available.",
        ],
        "field_notes": {
            "time_start": "The earliest absolute start time (ps) across all member components.",
            "time_end": "The latest absolute end time (ps) across all member components.",
            "center_time": "Midpoint of `time_start` and `time_end` (ps).",
            "n_hits": "Total hit count aggregated over members (from `hit_merged['component_count']` when present).",
            "n_channels": "Count of distinct `(board, channel)` pairs among members.",
            "component_offset": "Start row in `peaklet_components` for this peaklet's contiguous membership rows.",
            "component_count": "Number of contiguous `peaklet_components` membership rows for this peaklet.",
        },
        "config_notes": {
            "time_window_ns": "跨通道 peaklet 合并时间窗口（ns）。由上游 peaklet_components 消费并判定成员关系；本插件只消费其分组结果。",
            "max_total_width_ns": "peaklet 最大总宽度（ns），限制链式合并总时长；同样由 peaklet_components 消费。",
            "dt": "兼容性采样间隔（ns）回退配置，仅在输入缺少 dt 时使用；优先采用 `hit_merged` 的 dt。",
        },
        "failure_modes": [
            "`hit_merged` 不是结构化数组时抛出 `ValueError`。",
            "`peaklet_components` 不是结构化数组时抛出 `ValueError`。",
            "存在 `peaklet_components` 行的 `merged_index` 越界（超出 `hit_merged` 行范围）时抛出 `ValueError`。",
            "`peaklet_id` 分组不连续或成员索引错乱时，`component_offset`/`component_count` 指向的成员切片会失真，下游 `peaklet_channels` 的一致性校验将失败。",
        ],
        "downstream_consumers": [
            "peaklet_channels",
            "peaklet_features",
            "peaklet_waveforms",
            "peaks",
        ],
        "downstream_notes": [
            "`peaks` 直接以 peaklets 的行序作为 `peak_id`，任何行序或 `component_offset`/`component_count` 变更都会传播到最终 peaks 表。",
            "`peaklet_channels` 会校验成员数与 `peaklet_components` 的一致性，因此本插件的成员关系语义必须与 peaklet_components 保持同步。",
        ],
        "agent_change_notes": [
            "聚合字段语义或 `component_offset`/`component_count` 的变化会级联影响 `peaklet_channels`、`peaklet_features`、`peaklet_waveforms` 与 `peaks` 的消费逻辑。",
            "修改后请运行 peaklets 相关定向测试（test_peaklets_plugin 等）并重新生成 agent 文档。",
        ],
    }

    options = {
        "time_window_ns": Option(default=100.0, type=float, help="跨通道 peaklet 合并时间窗口"),
        "max_total_width_ns": Option(default=10000.0, type=float, help="peaklet 最大总宽度"),
        "dt": Option(default=None, type=int, help="保留兼容配置；优先使用输入 hit_merged 的 dt"),
    }

    def compute(self, context: Any, run_id: str, **kwargs) -> np.ndarray:
        return self.compute_array(context, run_id, **kwargs)

    def compute_array(self, context: Any, run_id: str, **_kwargs) -> np.ndarray:
        merged = context.get_data(run_id, "hit_merged")
        if not isinstance(merged, np.ndarray):
            raise ValueError("peaklets expects hit_merged as a structured array")
        if len(merged) == 0:
            return _empty_peaklets()
        components = context.get_data(run_id, "peaklet_components")
        if not isinstance(components, np.ndarray):
            raise ValueError("peaklets expects peaklet_components as a structured array")

        return self._compute_peaklets(merged=merged, components=components, context=context)

    def compute_chunk(self, chunk: Chunk, context: Any, run_id: str, **kwargs) -> Chunk:
        components = context.get_data(run_id, "peaklet_components")
        if not isinstance(components, np.ndarray):
            raise ValueError("peaklets expects peaklet_components as a structured array")
        peaklets = self._compute_peaklets(merged=chunk.data, components=components, context=context)
        return Chunk(
            data=peaklets,
            start=chunk.start,
            end=chunk.end,
            run_id=run_id,
            data_type=self.provides,
        )

    def _compute_peaklets(
        self, *, merged: np.ndarray, components: np.ndarray, context: Any
    ) -> np.ndarray:
        resolve_dt_config(context, self, deprecated_keys=("sampling_interval_ns", "dt_ns"))
        if len(components) == 0:
            return _empty_peaklets()

        n_peaklets = int(np.max(components["peak_id"])) + 1
        if n_peaklets <= 0:
            return _empty_peaklets()

        grouped_merged_indices, group_starts, group_ends = _prepare_component_groups(
            components, n_peaklets
        )
        if np.any(grouped_merged_indices < 0) or np.any(grouped_merged_indices >= len(merged)):
            raise ValueError("peaklets found peaklet_components row with out-of-range merged_index")

        abs_starts, abs_ends = _abs_window(merged)
        merged_names = merged.dtype.names or ()
        boards = (
            merged["board"].astype(np.int64, copy=False)
            if "board" in merged_names
            else np.zeros(len(merged), dtype=np.int64)
        )
        channels = merged["channel"].astype(np.int64, copy=False)
        has_component_counts = "component_count" in merged_names
        component_counts = (
            merged["component_count"].astype(np.int64, copy=False)
            if has_component_counts
            else np.empty(0, dtype=np.int64)
        )

        out = np.zeros(n_peaklets, dtype=PEAKLET_DTYPE)
        _summarize_peaklets_numba(
            grouped_merged_indices,
            group_starts,
            group_ends,
            abs_starts,
            abs_ends,
            boards,
            channels,
            component_counts,
            has_component_counts,
            out,
        )
        return out


class PeakletComponentsPlugin(BatchProcessingPlugin):
    """Return flat peaklet-to-hit_merged membership rows."""

    provides = "peaklet_components"
    lineage_virtual = True
    depends_on = ["hit_merged"]
    description = "Return per-peaklet component hit_merged indices."
    version = "1.4.0"
    output_dtype = PEAKLET_COMPONENTS_DTYPE
    save_when = "always"
    parallel = False

    options = {
        "time_window_ns": Option(default=100.0, type=float, help="跨通道 peaklet 合并时间窗口"),
        "max_total_width_ns": Option(default=10000.0, type=float, help="peaklet 最大总宽度"),
        "dt": Option(default=None, type=int, help="保留兼容配置；优先使用输入 hit_merged 的 dt"),
    }

    def compute(self, context: Any, run_id: str, **kwargs) -> np.ndarray:
        return self.compute_array(context, run_id, **kwargs)

    def compute_array(self, context: Any, run_id: str, **_kwargs) -> np.ndarray:
        merged = context.get_data(run_id, "hit_merged")
        if not isinstance(merged, np.ndarray):
            raise ValueError("peaklet_components expects hit_merged as a structured array")
        if len(merged) == 0:
            return _empty_components()

        time_window_ns = float(_resolve_peaklet_component_config(context, self, "time_window_ns"))
        max_total_width_ns = float(
            _resolve_peaklet_component_config(context, self, "max_total_width_ns")
        )
        resolve_dt_config(context, self, deprecated_keys=("sampling_interval_ns", "dt_ns"))
        order, cluster_starts, cluster_ends = _cluster_merged_hit_boundaries(
            merged,
            time_window_ns=time_window_ns,
            max_total_width_ns=max_total_width_ns,
        )
        out = np.empty(len(order), dtype=PEAKLET_COMPONENTS_DTYPE)
        _fill_peaklet_components_numba(
            order,
            cluster_starts,
            cluster_ends,
            out["peak_id"],
            out["merged_index"],
        )
        return out

    def get_lineage(self, context: Any) -> dict[str, Any]:
        config = {
            "time_window_ns": _resolve_peaklet_component_config(context, self, "time_window_ns"),
            "max_total_width_ns": _resolve_peaklet_component_config(
                context, self, "max_total_width_ns"
            ),
            "dt": _resolve_peaklet_component_config(context, self, "dt"),
        }
        return {
            "plugin_class": self.__class__.__name__,
            "plugin_version": self.version,
            "description": self.description,
            "config": config,
            "depends_on": {"hit_merged": context.get_lineage("hit_merged")},
        }

    def compute_chunk(self, chunk: Chunk, context: Any, run_id: str, **kwargs) -> Chunk:
        components = self.compute_array(context, run_id, **kwargs)
        return Chunk(
            data=components,
            start=chunk.start,
            end=chunk.end,
            run_id=run_id,
            data_type=self.provides,
        )


def _process_peaklet_batch(batch_data: dict) -> tuple[np.ndarray, np.ndarray]:
    """
    Process a batch of peaklets in a separate process.

    This function is called by multiprocessing Pool.map() and must be
    at module level (not a method).

    Parameters
    ----------
    batch_data : dict
        Contains: peaklets, components, merged, records, wave_pool,
                  hit_merged_components, hit_threshold

    Returns
    -------
    waveforms : np.ndarray
        Waveform index rows for this batch
    pool : np.ndarray
        Concatenated waveform pool for this batch
    """
    peaklets = batch_data["peaklets"]
    components = batch_data["components"]
    merged = batch_data["merged"]
    records = batch_data["records"]
    wave_pool = batch_data["wave_pool"]
    hit_merged_components = batch_data["hit_merged_components"]
    hit_threshold = batch_data["hit_threshold"]
    clip_negative_signal = bool(batch_data.get("clip_negative_signal", False))

    # Build hit_merged_components index if available
    if hit_merged_components is not None and len(hit_merged_components) > 0:
        hit_merged_components_index = _build_hit_merged_components_index(hit_merged_components)
    else:
        hit_merged_components_index = {}

    # Store in batch_data for access in nested function
    batch_data["hit_merged_components_index"] = hit_merged_components_index

    # Process using the same logic as _build_python
    record_lookup = RecordLookup(records)
    component_groups = _components_by_peaklet(components, len(peaklets))
    rows: list[tuple[int, int, int, int, int, int]] = []
    pools: list[np.ndarray] = []
    wave_offset = 0

    for peaklet_id, merged_indices in enumerate(component_groups):
        if len(merged_indices) == 0:
            rows.append((peaklet_id, 0, 0, 0, wave_offset, 0))
            continue

        pieces: list[tuple[int, int, np.ndarray]] = []
        dt_ns: int | None = None
        time_start: int | None = None
        time_end: int | None = None

        for merged_index in merged_indices:
            hit = merged[int(merged_index)]

            # Detect cross-record hit
            is_single_record = (
                bool(hit["is_single_record"])
                if "is_single_record" in hit.dtype.names
                else (int(hit["sample_start"]) >= 0 and int(hit["sample_end"]) >= 0)
            )

            if (
                not is_single_record
                and hit_merged_components is not None
                and hit_threshold is not None
            ):
                # Cross-record path
                multi_pieces = _merged_wave_pieces_multirecord(
                    hit=hit,
                    hit_merged_components_index=batch_data["hit_merged_components_index"],
                    hit_threshold=hit_threshold,
                    records=records,
                    record_lookup=record_lookup,
                    wave_pool=wave_pool,
                    merged_index=int(merged_index),
                    clip_negative_signal=clip_negative_signal,
                )

                for start_ps, end_ps, piece_dt_ns, signal in multi_pieces:
                    if len(signal) == 0:
                        continue
                    if dt_ns is None:
                        dt_ns = piece_dt_ns
                    elif piece_dt_ns != dt_ns:
                        raise ValueError(
                            f"peaklet_waveforms does not support mixed dt in peaklet_id={peaklet_id}"
                        )
                    pieces.append((start_ps, end_ps, signal))
                    time_start = start_ps if time_start is None else min(time_start, start_ps)
                    time_end = end_ps if time_end is None else max(time_end, end_ps)
            else:
                # Single-record path
                start_ps, end_ps, piece_dt_ns, signal = _merged_wave_piece(
                    hit=hit,
                    records=records,
                    record_lookup=record_lookup,
                    wave_pool=wave_pool,
                    clip_negative_signal=clip_negative_signal,
                )
                if len(signal) == 0:
                    continue
                if dt_ns is None:
                    dt_ns = piece_dt_ns
                elif piece_dt_ns != dt_ns:
                    raise ValueError(
                        f"peaklet_waveforms does not support mixed dt in peaklet_id={peaklet_id}"
                    )
                pieces.append((start_ps, end_ps, signal))
                time_start = start_ps if time_start is None else min(time_start, start_ps)
                time_end = end_ps if time_end is None else max(time_end, end_ps)

        if not pieces or dt_ns is None or time_start is None or time_end is None:
            rows.append((peaklet_id, 0, 0, 0, wave_offset, 0))
            continue

        dt_ps = dt_ns * 1000
        wave_length = int((time_end - time_start) // dt_ps)
        summed = np.zeros(wave_length, dtype=np.float32)

        for start_ps, _end_ps, signal in pieces:
            i0 = int((start_ps - time_start) // dt_ps)
            summed[i0 : i0 + len(signal)] += signal

        rows.append((peaklet_id, time_start, time_end, dt_ns, wave_offset, wave_length))
        pools.append(summed)
        wave_offset += wave_length

    pool = np.concatenate(pools).astype(np.float32, copy=False) if pools else _empty_waveform_pool()
    waveforms = np.array(rows, dtype=PEAKLET_WAVEFORMS_DTYPE) if rows else _empty_waveforms()

    return waveforms, pool


class PeakletWaveformPlugin(Plugin):
    """Build ragged waveform index rows for peaklets and cache the signal pool."""

    provides = "peaklet_waveforms"
    depends_on = []  # 使用 resolve_depends_on() 动态解析
    description = "Build peaklet waveform index rows from records-backed hit_merged samples. Supports cross-record hits via component expansion."
    version = "1.4.0"
    output_dtype = PEAKLET_WAVEFORMS_DTYPE
    save_when = "always"

    options = {
        "use_filtered": Option(
            default=False, type=bool, help="是否使用 wave_pool_filtered 构建 peaklet 波形"
        ),
        "clip_negative_signal": Option(
            default=False,
            type=bool,
            help="是否将 baseline/polarity 转换后的负信号裁剪为 0。默认保留负值。",
        ),
        "debug_numba": Option(
            default=False,
            type=bool,
            help="调试 peaklet waveform Numba 路径；启用后 Numba 异常直接抛出。",
        ),
        "log_waveform_diagnostics": Option(
            default=False,
            type=bool,
            help="记录 peaklet waveform 构建统计和耗时诊断信息。",
        ),
        "n_workers": Option(
            default=1,
            type=int,
            help="并行处理的进程数。1=单进程，0=自动（使用 CPU 核心数-1），>1=指定进程数",
        ),
        "parallel_threshold": Option(
            default=5000,
            type=int,
            help="启用并行化的最小 peaklet 数量。少于此数量时使用单进程",
        ),
    }

    def resolve_depends_on(self, context: Any, run_id: str | None = None) -> list[str]:
        deps = [
            "peaklets",
            "peaklet_components",
            "hit_merged",
            "hit_merged_components",
            "hit_threshold",
            "records",
        ]
        deps.append(
            "wave_pool_filtered" if bool(context.get_config(self, "use_filtered")) else "wave_pool"
        )
        return deps

    def compute(self, context: Any, run_id: str, **_kwargs) -> np.ndarray:
        cached_waveforms = _get_context_memory(context, run_id, "peaklet_waveforms")
        if isinstance(cached_waveforms, np.ndarray):
            return cached_waveforms

        waveforms, pool = self.build_pair(context, run_id)
        self._store_waveform_pair(context, run_id, waveforms, pool)
        return waveforms

    def _configure_build(self, context: Any) -> None:
        """Resolve the canonical configuration used by both waveform outputs."""
        n_workers = int(context.get_config(self, "n_workers"))
        if n_workers == 0 and HAS_MULTIPROCESSING:
            n_workers = max(1, cpu_count() - 1)

        self._n_workers = n_workers
        self._parallel_threshold = int(context.get_config(self, "parallel_threshold"))
        self._debug_numba = bool(context.get_config(self, "debug_numba"))
        self._log_waveform_diagnostics = bool(context.get_config(self, "log_waveform_diagnostics"))
        self._clip_negative_signal = bool(context.get_config(self, "clip_negative_signal"))

    def build_pair(self, context: Any, run_id: str) -> tuple[np.ndarray, np.ndarray]:
        """Build index rows and the flattened pool from one canonical configuration."""
        self._configure_build(context)
        return self._compute_waveforms_and_pool(context, run_id)

    def _store_waveform_pair(
        self, context: Any, run_id: str, waveforms: np.ndarray, pool: np.ndarray
    ) -> None:
        _store_context_memory(context, run_id, "peaklet_waveforms", waveforms)
        _store_context_memory(context, run_id, "peaklet_waveform_pool", pool)

    def _compute_waveforms_and_pool(
        self, context: Any, run_id: str
    ) -> tuple[np.ndarray, np.ndarray]:
        peaklets = context.get_data(run_id, "peaklets")
        if not isinstance(peaklets, np.ndarray):
            raise ValueError("peaklet_waveforms expects peaklets as a structured array")
        if len(peaklets) == 0:
            return _empty_waveforms(), _empty_waveform_pool()

        components = context.get_data(run_id, "peaklet_components")
        if not isinstance(components, np.ndarray):
            raise ValueError("peaklet_waveforms expects peaklet_components as a structured array")
        _validate_peaklet_components(
            peaklets=peaklets,
            components=components,
            consumer="peaklet_waveforms",
        )
        merged = context.get_data(run_id, "hit_merged")
        if not isinstance(merged, np.ndarray):
            raise ValueError("peaklet_waveforms expects hit_merged as a structured array")

        # Get cross-record dependencies
        hit_merged_components = context.get_data(run_id, "hit_merged_components")
        hit_threshold = context.get_data(run_id, "hit_threshold")

        records = _record_array(context.get_data(run_id, "records"))
        wave_pool_name = (
            "wave_pool_filtered" if bool(context.get_config(self, "use_filtered")) else "wave_pool"
        )
        wave_pool = _wave_pool_array(context.get_data(run_id, wave_pool_name))

        # Store context and run_id for Python fallback path
        self._context = context
        self._run_id = run_id
        self._hit_merged_components = hit_merged_components
        self._hit_threshold = hit_threshold
        self._hit_merged_components_index = None

        return self._build(
            peaklets=peaklets,
            components=components,
            merged=merged,
            records=records,
            wave_pool=wave_pool,
        )

    def _build(
        self,
        *,
        peaklets: np.ndarray,
        components: np.ndarray,
        merged: np.ndarray,
        records: np.ndarray,
        wave_pool: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray]:
        if len(peaklets) == 0:
            return _empty_waveforms(), _empty_waveform_pool()

        if "is_single_record" in merged.dtype.names:
            is_single_record = merged["is_single_record"]
        elif "sample_start" in merged.dtype.names:
            is_single_record = merged["sample_start"] >= 0
        else:
            is_single_record = np.ones(len(merged), dtype=bool)
        has_cross_record = not np.all(is_single_record)

        # If no cross-record hits, use pure Numba path
        if not has_cross_record and HAS_NUMBA and len(peaklets) > 5:
            try:
                return self._build_numba(
                    peaklets=peaklets,
                    components=components,
                    merged=merged,
                    records=records,
                    wave_pool=wave_pool,
                )
            except Exception as e:
                if getattr(self, "_debug_numba", False):
                    raise
                logger.warning(
                    f"Numba path failed for peaklet_waveforms (all single-record), "
                    f"falling back to Python: {e}"
                )

        if has_cross_record and HAS_NUMBA:
            try:
                return self._build_cross_record_numba(
                    peaklets=peaklets,
                    components=components,
                    merged=merged,
                    is_single_record=np.asarray(is_single_record, dtype=bool),
                    records=records,
                    wave_pool=wave_pool,
                )
            except Exception as e:
                if getattr(self, "_debug_numba", False):
                    raise
                logger.warning(
                    f"Cross-record Numba path failed for peaklet_waveforms, "
                    f"falling back to pure Python: {e}"
                )

        # Python fallback for all cases
        return self._build_python(
            peaklets=peaklets,
            components=components,
            merged=merged,
            records=records,
            wave_pool=wave_pool,
        )

    def _build_cross_record_numba(
        self,
        *,
        peaklets: np.ndarray,
        components: np.ndarray,
        merged: np.ndarray,
        is_single_record: np.ndarray,
        records: np.ndarray,
        wave_pool: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray]:
        hit_merged_components = getattr(self, "_hit_merged_components", None)
        hit_threshold = getattr(self, "_hit_threshold", None)
        if not isinstance(hit_merged_components, np.ndarray) or not isinstance(
            hit_threshold, np.ndarray
        ):
            raise ValueError(
                "peaklet_waveforms cross-record path requires hit_merged_components "
                "and hit_threshold arrays"
            )

        t0 = time.perf_counter()
        grouped_merged_indices, peaklet_comp_starts, peaklet_comp_ends = (
            _build_peaklet_component_csr(components, len(peaklets))
        )
        merged_names = merged.dtype.names or ()
        if {"component_offset", "component_count"}.issubset(merged_names):
            grouped_hit_indices = hit_merged_components["hit_index"].astype(np.int64, copy=False)
            merged_hit_starts = merged["component_offset"].astype(np.int64, copy=False)
            merged_hit_ends = merged_hit_starts + merged["component_count"].astype(
                np.int64, copy=False
            )
            if (
                np.any(merged_hit_starts < 0)
                or np.any(merged_hit_ends < merged_hit_starts)
                or np.any(merged_hit_ends > len(grouped_hit_indices))
            ):
                raise ValueError("peaklet_waveforms found invalid hit_merged component offsets")
        else:
            grouped_hit_indices, merged_hit_starts, merged_hit_ends = _build_hmc_csr(
                hit_merged_components, len(merged)
            )

        if {"sample_start", "sample_end"}.issubset(merged_names):
            merged_sample_starts = merged["sample_start"]
            merged_sample_ends = merged["sample_end"]
        elif {"edge_start", "edge_end"}.issubset(merged_names):
            merged_sample_starts = merged["edge_start"]
            merged_sample_ends = merged["edge_end"]
        else:
            raise KeyError(
                "peaklet_waveforms requires hit_merged sample_start/sample_end "
                "or edge_start/edge_end"
            )
        if "record_id" not in merged_names:
            raise KeyError("peaklet_waveforms requires hit_merged record_id")

        merged_component_counts = (
            merged["component_count"].astype(np.int64, copy=False)
            if "component_count" in merged_names
            else np.zeros(len(merged), dtype=np.int64)
        )
        direct_merged = np.asarray(is_single_record, dtype=bool) & (merged_component_counts == 1)

        hit_names = hit_threshold.dtype.names or ()
        if {"sample_start", "sample_end"}.issubset(hit_names):
            hit_sample_starts = hit_threshold["sample_start"].astype(np.int64, copy=False)
            hit_sample_ends = hit_threshold["sample_end"].astype(np.int64, copy=False)
        elif {"edge_start", "edge_end"}.issubset(hit_names):
            hit_sample_starts = hit_threshold["edge_start"].astype(np.int64, copy=False)
            hit_sample_ends = hit_threshold["edge_end"].astype(np.int64, copy=False)
        else:
            raise KeyError(
                "peaklet_waveforms requires hit_threshold sample_start/sample_end "
                "or edge_start/edge_end"
            )

        if "record_id" not in hit_names:
            raise KeyError("peaklet_waveforms requires hit_threshold record_id")
        record_lookup = RecordLookup(records)
        hit_record_ids = hit_threshold["record_id"].astype(np.int64, copy=False)
        hit_record_indices = record_lookup.get_indices(hit_record_ids).astype(np.int64, copy=False)
        merged_record_indices = record_lookup.get_indices(
            merged["record_id"].astype(np.int64, copy=False)
        ).astype(np.int64, copy=False)

        record_names = records.dtype.names or ()
        if "dt" not in record_names:
            raise KeyError("peaklet_waveforms cross-record path requires records dt")
        for required in ("event_length", "wave_offset"):
            if required not in record_names:
                raise KeyError(f"peaklet_waveforms cross-record path requires records {required}")

        record_dt = records["dt"].astype(np.int64, copy=False)
        record_event_length = records["event_length"].astype(np.int64, copy=False)
        record_timestamp = (
            records["timestamp"].astype(np.int64, copy=False)
            if "timestamp" in record_names
            else np.zeros(len(records), dtype=np.int64)
        )
        record_wave_offset = records["wave_offset"].astype(np.int64, copy=False)
        record_baseline = (
            records["baseline"].astype(np.float32, copy=False)
            if "baseline" in record_names
            else np.zeros(len(records), dtype=np.float32)
        )
        record_sign = _extract_polarity_signs(records)
        time_prepare_csr = time.perf_counter() - t0

        t_first = time.perf_counter()
        waveform_rows, total_wave_length = _first_pass_cross_record_numba(
            grouped_merged_indices,
            peaklet_comp_starts,
            peaklet_comp_ends,
            direct_merged,
            merged_record_indices,
            merged_sample_starts,
            merged_sample_ends,
            grouped_hit_indices,
            merged_hit_starts,
            merged_hit_ends,
            hit_record_indices,
            hit_sample_starts,
            hit_sample_ends,
            record_dt,
            record_event_length,
            record_timestamp,
        )
        time_first_pass = time.perf_counter() - t_first

        for peaklet_id in range(len(waveform_rows)):
            if waveform_rows[peaklet_id, 1] == -1:
                raise ValueError(
                    f"peaklet_waveforms does not support mixed dt in peaklet_id={peaklet_id}"
                )

        t_second = time.perf_counter()
        pool = np.zeros(int(total_wave_length), dtype=np.float32)
        _fill_cross_record_pool_numba(
            pool,
            waveform_rows,
            grouped_merged_indices,
            peaklet_comp_starts,
            peaklet_comp_ends,
            direct_merged,
            merged_record_indices,
            merged_sample_starts,
            merged_sample_ends,
            grouped_hit_indices,
            merged_hit_starts,
            merged_hit_ends,
            hit_record_indices,
            hit_sample_starts,
            hit_sample_ends,
            record_dt,
            record_event_length,
            record_timestamp,
            record_wave_offset,
            record_baseline,
            record_sign,
            wave_pool,
            bool(getattr(self, "_clip_negative_signal", False)),
        )
        time_second_pass = time.perf_counter() - t_second

        waveforms = np.zeros(len(waveform_rows), dtype=PEAKLET_WAVEFORMS_DTYPE)
        waveforms["peak_id"] = waveform_rows[:, 0]
        waveforms["time_start"] = waveform_rows[:, 1]
        waveforms["time_end"] = waveform_rows[:, 2]
        waveforms["dt"] = waveform_rows[:, 3]
        waveforms["wave_offset"] = waveform_rows[:, 4]
        waveforms["wave_length"] = waveform_rows[:, 5]

        if getattr(self, "_log_waveform_diagnostics", False):
            component_peak_ids = components["peak_id"].astype(np.int64, copy=False)
            component_merged_indices = components["merged_index"].astype(np.int64, copy=False)
            component_is_cross = ~is_single_record[component_merged_indices]
            if len(component_peak_ids) > 0:
                cross_counts = np.bincount(
                    component_peak_ids[component_is_cross], minlength=len(peaklets)
                )
                fraction_peaklet_with_cross_record = float(np.mean(cross_counts > 0))
            else:
                fraction_peaklet_with_cross_record = 0.0
            logger.info(
                "peaklet_waveforms diagnostics: "
                "n_peaklets=%s n_merged=%s n_hit_threshold=%s "
                "fraction_cross_record_merged=%.6f "
                "fraction_direct_merged=%.6f "
                "fraction_peaklet_with_cross_record=%.6f "
                "total_waveform_pool_length=%s "
                "time_prepare_csr=%.6fs time_first_pass=%.6fs "
                "time_second_pass=%.6fs time_total=%.6fs",
                len(peaklets),
                len(merged),
                len(hit_threshold),
                float(np.mean(~is_single_record)) if len(is_single_record) else 0.0,
                float(np.mean(direct_merged)) if len(direct_merged) else 0.0,
                fraction_peaklet_with_cross_record,
                int(total_wave_length),
                time_prepare_csr,
                time_first_pass,
                time_second_pass,
                time.perf_counter() - t0,
            )

        return waveforms, pool

    def _build_hybrid(
        self,
        *,
        peaklets: np.ndarray,
        components: np.ndarray,
        merged: np.ndarray,
        is_single_record: np.ndarray,
        records: np.ndarray,
        wave_pool: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray]:
        """
        Hybrid strategy: use Numba for single-record peaklets, Python for cross-record.

        This significantly improves performance when only a small fraction of peaklets
        contain cross-record hits.
        """
        # Build mapping: which merged indices belong to which peaklet
        component_peak_ids = components["peak_id"]
        component_merged_indices = components["merged_index"]

        # Vectorized check: for each peaklet, does it contain any cross-record hit?
        # This is faster than looping through each peaklet
        peaklet_has_cross_record = np.zeros(len(peaklets), dtype=bool)

        # Create mapping: component index -> is_cross_record
        component_is_cross = ~is_single_record[component_merged_indices]

        # Use bincount to check if any component in each peaklet is cross-record
        # bincount counts True (1) values per peaklet_id
        cross_counts = np.bincount(component_peak_ids[component_is_cross], minlength=len(peaklets))
        peaklet_has_cross_record = cross_counts > 0

        # Split into two groups
        single_record_mask = ~peaklet_has_cross_record
        cross_record_mask = peaklet_has_cross_record

        n_single = np.sum(single_record_mask)
        n_cross = np.sum(cross_record_mask)

        # Process single-record peaklets with Numba
        if n_single > 0:
            single_peaklet_ids = np.flatnonzero(single_record_mask)
            single_component_mask = np.isin(component_peak_ids, single_peaklet_ids)
            single_components = components[single_component_mask]

            # Remap peak_id to 0-based for the subset
            peak_id_map = np.full(len(peaklets), -1, dtype=np.int64)
            peak_id_map[single_peaklet_ids] = np.arange(n_single)
            single_components_remapped = single_components.copy()
            single_components_remapped["peak_id"] = peak_id_map[single_components["peak_id"]]

            # Create subset peaklets array
            single_peaklets = peaklets[single_peaklet_ids]

            # Use Numba for this subset
            single_waveforms, single_pool = self._build_numba(
                peaklets=single_peaklets,
                components=single_components_remapped,
                merged=merged,
                records=records,
                wave_pool=wave_pool,
            )
        else:
            single_waveforms = _empty_waveforms()
            single_pool = _empty_waveform_pool()

        # Process cross-record peaklets with Python
        if n_cross > 0:
            cross_peaklet_ids = np.flatnonzero(cross_record_mask)
            cross_component_mask = np.isin(component_peak_ids, cross_peaklet_ids)
            cross_components = components[cross_component_mask]

            # Remap peak_id
            peak_id_map = np.full(len(peaklets), -1, dtype=np.int64)
            peak_id_map[cross_peaklet_ids] = np.arange(n_cross)
            cross_components_remapped = cross_components.copy()
            cross_components_remapped["peak_id"] = peak_id_map[cross_components["peak_id"]]

            cross_peaklets = peaklets[cross_peaklet_ids]

            # Determine if we should use parallel processing
            n_workers = getattr(self, "_n_workers", 1)
            parallel_threshold = getattr(self, "_parallel_threshold", 5000)

            use_parallel = HAS_MULTIPROCESSING and n_workers != 1 and n_cross >= parallel_threshold

            if use_parallel:
                # Parallel processing for cross-record peaklets
                cross_waveforms, cross_pool = self._build_python_parallel(
                    peaklets=cross_peaklets,
                    components=cross_components_remapped,
                    merged=merged,
                    records=records,
                    wave_pool=wave_pool,
                    n_workers=n_workers,
                )
            else:
                # Use Python for this subset
                cross_waveforms, cross_pool = self._build_python(
                    peaklets=cross_peaklets,
                    components=cross_components_remapped,
                    merged=merged,
                    records=records,
                    wave_pool=wave_pool,
                )
        else:
            cross_waveforms = _empty_waveforms()
            cross_pool = _empty_waveform_pool()

        # Merge results
        # Concatenate pools
        merged_pool = np.concatenate([single_pool, cross_pool]).astype(np.float32, copy=False)

        # Merge waveform rows and adjust offsets
        merged_waveforms = np.zeros(len(peaklets), dtype=PEAKLET_WAVEFORMS_DTYPE)

        # Copy single-record results
        if n_single > 0:
            single_peaklet_ids = np.flatnonzero(single_record_mask)
            for i, peaklet_id in enumerate(single_peaklet_ids):
                merged_waveforms[peaklet_id] = single_waveforms[i]

        # Copy cross-record results and adjust wave_offset
        if n_cross > 0:
            cross_peaklet_ids = np.flatnonzero(cross_record_mask)
            single_pool_size = len(single_pool)
            for i, peaklet_id in enumerate(cross_peaklet_ids):
                merged_waveforms[peaklet_id] = cross_waveforms[i]
                merged_waveforms[peaklet_id]["wave_offset"] += single_pool_size

        return merged_waveforms, merged_pool

    def _build_numba(
        self,
        *,
        peaklets: np.ndarray,
        components: np.ndarray,
        merged: np.ndarray,
        records: np.ndarray,
        wave_pool: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Numba 加速路径 - 仅处理单 record 的 hit_merged"""
        # Note: Caller (_build_hybrid) ensures all merged hits are single-record
        # No need to check for cross-record here

        # 批量解析 record_id
        record_lookup = RecordLookup(records)
        record_ids = merged["record_id"]
        record_indices = record_lookup.get_indices(record_ids)

        # 提取 merged 字段
        merged_names = merged.dtype.names or ()
        if {"sample_start", "sample_end"}.issubset(merged_names):
            merged_sample_starts = merged["sample_start"].astype(np.int64)
            merged_sample_ends = merged["sample_end"].astype(np.int64)
        elif {"edge_start", "edge_end"}.issubset(merged_names):
            merged_sample_starts = merged["edge_start"].astype(np.int64)
            merged_sample_ends = merged["edge_end"].astype(np.int64)
        else:
            raise KeyError(
                "peaklet_waveforms requires sample_start/sample_end or edge_start/edge_end"
            )

        merged_dt = merged["dt"].astype(np.int64)

        # 提取 record 字段
        record_names = records.dtype.names or ()
        record_dt = records["dt"].astype(np.int64) if "dt" in record_names else merged_dt
        record_baseline = (
            records["baseline"].astype(np.float32)
            if "baseline" in record_names
            else np.zeros(len(records), dtype=np.float32)
        )
        record_wave_offset = records["wave_offset"].astype(np.int64)
        record_event_length = records["event_length"].astype(np.int64)
        record_timestamp = (
            records["timestamp"].astype(np.int64)
            if "timestamp" in record_names
            else np.zeros(len(records), dtype=np.int64)
        )
        record_sign = _extract_polarity_signs(records)

        # 调用 Numba 核心
        waveform_rows, pool = _build_waveforms_numba(
            components["peak_id"].astype(np.int64),
            components["merged_index"].astype(np.int64),
            record_ids.astype(np.int64),
            merged_sample_starts,
            merged_sample_ends,
            merged_dt,
            record_indices,
            record_dt,
            record_baseline,
            record_wave_offset,
            record_event_length,
            record_timestamp,
            record_sign,
            wave_pool,
            bool(getattr(self, "_clip_negative_signal", False)),
        )

        # 检查混合 dt 错误
        for i in range(len(waveform_rows)):
            if waveform_rows[i, 1] == -1:
                raise ValueError(f"peaklet_waveforms does not support mixed dt in peaklet_id={i}")

        # 转换为结构化数组
        waveforms = np.zeros(len(waveform_rows), dtype=PEAKLET_WAVEFORMS_DTYPE)
        waveforms["peak_id"] = waveform_rows[:, 0]
        waveforms["time_start"] = waveform_rows[:, 1]
        waveforms["time_end"] = waveform_rows[:, 2]
        waveforms["dt"] = waveform_rows[:, 3]
        waveforms["wave_offset"] = waveform_rows[:, 4]
        waveforms["wave_length"] = waveform_rows[:, 5]

        return waveforms, pool

    def _build_python_parallel(
        self,
        *,
        peaklets: np.ndarray,
        components: np.ndarray,
        merged: np.ndarray,
        records: np.ndarray,
        wave_pool: np.ndarray,
        n_workers: int,
    ) -> tuple[np.ndarray, np.ndarray]:
        """
        Parallel processing of cross-record peaklets.

        Split peaklets into batches and process them in parallel using multiprocessing.
        """
        n_peaklets = len(peaklets)

        # Split peaklets into batches
        batch_size = max(1, n_peaklets // n_workers)
        batches = []

        for i in range(0, n_peaklets, batch_size):
            end_idx = min(i + batch_size, n_peaklets)
            batch_peaklet_ids = np.arange(i, end_idx)

            # Filter components for this batch
            batch_component_mask = np.isin(components["peak_id"], batch_peaklet_ids)
            batch_components = components[batch_component_mask].copy()

            # Remap peak_id to be 0-based within this batch
            old_to_new = np.full(n_peaklets, -1, dtype=np.int64)
            old_to_new[batch_peaklet_ids] = np.arange(len(batch_peaklet_ids))
            batch_components["peak_id"] = old_to_new[batch_components["peak_id"]]

            batches.append(
                {
                    "peaklets": peaklets[batch_peaklet_ids],
                    "components": batch_components,
                    "merged": merged,
                    "records": records,
                    "wave_pool": wave_pool,
                    "hit_merged_components": getattr(self, "_hit_merged_components", None),
                    "hit_threshold": getattr(self, "_hit_threshold", None),
                    "clip_negative_signal": bool(getattr(self, "_clip_negative_signal", False)),
                    "peaklet_id_offset": i,
                }
            )

        # Process batches in parallel
        with Pool(n_workers) as pool:
            results = pool.map(_process_peaklet_batch, batches)

        # Merge results from all batches
        all_waveforms = []
        all_pools = []
        cumulative_offset = 0

        for batch, (batch_waveforms, batch_pool) in zip(batches, results, strict=False):
            # Adjust wave_offset
            if len(batch_waveforms) > 0:
                batch_waveforms["wave_offset"] += cumulative_offset
                batch_waveforms["peak_id"] += int(batch["peaklet_id_offset"])
            all_waveforms.append(batch_waveforms)
            all_pools.append(batch_pool)
            cumulative_offset += len(batch_pool)

        # Concatenate all results
        if all_waveforms:
            final_waveforms = np.concatenate(all_waveforms)
        else:
            final_waveforms = _empty_waveforms()

        if all_pools:
            final_pool = np.concatenate(all_pools).astype(np.float32, copy=False)
        else:
            final_pool = _empty_waveform_pool()

        return final_waveforms, final_pool

    def _build_python(
        self,
        *,
        peaklets: np.ndarray,
        components: np.ndarray,
        merged: np.ndarray,
        records: np.ndarray,
        wave_pool: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Python fallback 路径，支持跨 record 的 hit_merged"""
        record_lookup = RecordLookup(records)

        # Get cross-record dependencies (from _compute_waveforms_and_pool)
        hit_merged_components = getattr(self, "_hit_merged_components", None)
        hit_threshold = getattr(self, "_hit_threshold", None)
        if (
            hit_merged_components is not None
            and len(hit_merged_components) > 0
            and getattr(self, "_hit_merged_components_index", None) is None
        ):
            self._hit_merged_components_index = _build_hit_merged_components_index(
                hit_merged_components
            )

        component_groups = _components_by_peaklet(components, len(peaklets))
        rows: list[tuple[int, int, int, int, int, int]] = []
        pools: list[np.ndarray] = []
        wave_offset = 0

        for peaklet_id, merged_indices in enumerate(component_groups):
            if len(merged_indices) == 0:
                rows.append((peaklet_id, 0, 0, 0, wave_offset, 0))
                continue

            pieces: list[tuple[int, int, np.ndarray]] = []
            dt_ns: int | None = None
            time_start: int | None = None
            time_end: int | None = None

            for merged_index in merged_indices:
                hit = merged[int(merged_index)]

                # Detect cross-record hit
                is_single_record = (
                    bool(hit["is_single_record"])
                    if "is_single_record" in hit.dtype.names
                    else (int(hit["sample_start"]) >= 0 and int(hit["sample_end"]) >= 0)
                )

                if (
                    not is_single_record
                    and hit_merged_components is not None
                    and hit_threshold is not None
                ):
                    # Cross-record path: expand into multiple pieces
                    multi_pieces = _merged_wave_pieces_multirecord(
                        hit=hit,
                        hit_merged_components_index=getattr(
                            self, "_hit_merged_components_index", {}
                        ),
                        hit_threshold=hit_threshold,
                        records=records,
                        record_lookup=record_lookup,
                        wave_pool=wave_pool,
                        merged_index=int(merged_index),
                        clip_negative_signal=bool(getattr(self, "_clip_negative_signal", False)),
                    )

                    for start_ps, end_ps, piece_dt_ns, signal in multi_pieces:
                        if len(signal) == 0:
                            continue
                        if dt_ns is None:
                            dt_ns = piece_dt_ns
                        elif piece_dt_ns != dt_ns:
                            raise ValueError(
                                f"peaklet_waveforms does not support mixed dt in peaklet_id={peaklet_id}"
                            )
                        pieces.append((start_ps, end_ps, signal))
                        time_start = start_ps if time_start is None else min(time_start, start_ps)
                        time_end = end_ps if time_end is None else max(time_end, end_ps)
                else:
                    # Single-record path
                    start_ps, end_ps, piece_dt_ns, signal = _merged_wave_piece(
                        hit=hit,
                        records=records,
                        record_lookup=record_lookup,
                        wave_pool=wave_pool,
                        clip_negative_signal=bool(getattr(self, "_clip_negative_signal", False)),
                    )
                    if len(signal) == 0:
                        continue
                    if dt_ns is None:
                        dt_ns = piece_dt_ns
                    elif piece_dt_ns != dt_ns:
                        raise ValueError(
                            f"peaklet_waveforms does not support mixed dt in peaklet_id={peaklet_id}"
                        )
                    pieces.append((start_ps, end_ps, signal))
                    time_start = start_ps if time_start is None else min(time_start, start_ps)
                    time_end = end_ps if time_end is None else max(time_end, end_ps)

            if not pieces or dt_ns is None or time_start is None or time_end is None:
                rows.append((peaklet_id, 0, 0, 0, wave_offset, 0))
                continue

            dt_ps = dt_ns * 1000
            wave_length = int((time_end - time_start) // dt_ps)
            summed = np.zeros(wave_length, dtype=np.float32)

            for start_ps, _end_ps, signal in pieces:
                i0 = int((start_ps - time_start) // dt_ps)
                summed[i0 : i0 + len(signal)] += signal

            rows.append((peaklet_id, time_start, time_end, dt_ns, wave_offset, wave_length))
            pools.append(summed)
            wave_offset += wave_length

        pool = (
            np.concatenate(pools).astype(np.float32, copy=False)
            if pools
            else _empty_waveform_pool()
        )
        return np.array(rows, dtype=PEAKLET_WAVEFORMS_DTYPE) if rows else _empty_waveforms(), pool


class PeakletWaveformPoolPlugin(Plugin):
    """Return the pool produced alongside the canonical peaklet waveform index."""

    provides = "peaklet_waveform_pool"
    lineage_virtual = True
    depends_on = ["peaklet_waveforms"]
    description = (
        "Return the flattened float32 signal pool paired with peaklet_waveforms. "
        "Configure waveform construction on peaklet_waveforms."
    )
    version = "2.0.0"
    output_dtype = np.dtype("f4")
    save_when = "always"
    agent_doc = {
        "behavior_notes": [
            "Waveform construction options are owned by `peaklet_waveforms`; `peaklet_waveform_pool` has no independent configuration.",
            "Custom `peaklet_waveforms` providers must implement `build_pair(context, run_id)` so a missing pool can be rebuilt after a waveform cache hit.",
        ],
        "failure_modes": [
            "A custom `peaklet_waveforms` provider does not implement `build_pair(context, run_id)`.",
            "Legacy configuration remains under `peaklet_waveform_pool.*` instead of the canonical `peaklet_waveforms.*` namespace.",
        ],
        "agent_change_notes": [
            "v2.0.0: `peaklet_waveform_pool` now depends on `peaklet_waveforms`, so waveform version, config, dtype, and upstream lineage invalidate the paired pool cache.",
            "v2.0.0: Move all former `peaklet_waveform_pool.*` settings to `peaklet_waveforms.*`; the old namespace is ignored with a migration warning.",
            "Keep `peaklet_waveforms` index offsets and `peaklet_waveform_pool` values generated by the same `build_pair` implementation.",
        ],
    }
    doc_usage_example = """
    from waveform_analysis.core.context import Context
    from waveform_analysis.core.plugins.plugin_sets import (
        plugins_hit,
        plugins_io,
        plugins_waveform,
    )

    ctx = Context(config={"data_root": "DAQ"})
    ctx.register(*plugins_io(), *plugins_waveform(), *plugins_hit())

    # Construction options belong to the canonical waveform producer.
    ctx.set_config(
        {"use_filtered": False, "clip_negative_signal": False},
        plugin_name="peaklet_waveforms",
    )
    pool = ctx.get_data("run_001", "peaklet_waveform_pool")
    """

    options = {}
    _LEGACY_CONFIG_KEYS = tuple(PeakletWaveformPlugin.options)

    def _warn_legacy_config(self, context: Any) -> None:
        config = getattr(context, "config", {})
        config = config if isinstance(config, dict) else {}
        nested = config.get(self.provides, {})
        dotted_prefix = f"{self.provides}."
        has_legacy_config = isinstance(nested, dict) and any(
            name in nested for name in self._LEGACY_CONFIG_KEYS
        )
        has_legacy_config = has_legacy_config or any(
            isinstance(key, str) and key.startswith(dotted_prefix) for key in config
        )
        if has_legacy_config:
            warnings.warn(
                "Configuration under 'peaklet_waveform_pool' is ignored; configure "
                "the canonical 'peaklet_waveforms' plugin instead.",
                FutureWarning,
                stacklevel=2,
            )

    def compute(self, context: Any, run_id: str, **_kwargs) -> np.ndarray:
        self._warn_legacy_config(context)
        cached_pool = _get_context_memory(context, run_id, "peaklet_waveform_pool")
        if isinstance(cached_pool, np.ndarray):
            return np.asarray(cached_pool, dtype=np.float32)

        plugins = getattr(context, "_plugins", {})
        waveform_plugin = plugins.get("peaklet_waveforms")
        if waveform_plugin is None:
            waveform_plugin = PeakletWaveformPlugin()
        if not hasattr(waveform_plugin, "build_pair"):
            raise TypeError(
                "peaklet_waveform_pool requires the registered peaklet_waveforms provider "
                "to implement build_pair(context, run_id)"
            )

        waveforms, pool = waveform_plugin.build_pair(context, run_id)
        _store_context_memory(context, run_id, "peaklet_waveforms", waveforms)
        _store_context_memory(context, run_id, "peaklet_waveform_pool", pool)
        return pool


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


class PeaksPlugin(Plugin):
    """Build the final user-facing peaks table from peaklet metadata and features."""

    provides = "peaks"
    depends_on = ["peaklets", "peaklet_features", "peaklet_channels"]
    description = "Build final peaks table from peaklets and waveform-derived features."
    version = "4.0.1"
    output_dtype = PEAKS_DTYPE
    save_when = "always"
    agent_doc = {
        "overview": (
            "PeaksPlugin 是分析链末端的用户级插件，把 peaklet 层面的元数据与 peaklet_features "
            "导出的波形派生特征合并为最终的用户可见 peaks 表。它不重新计算任何物理量，只负责把 "
            "特征按 `peak_id` 稳定地对齐到 `peaklets` 的行序，并以其行索引作为 `peak_id`。\n\n"
            "由于 `peaklet_features` 的特征行是按 peak_id 解析的，PeaksPlugin 采用稳定排序 + "
            "`searchsorted` 的方式将每个 peaklet 精确匹配到其特征行：任何 peaklet 缺失对应特征都"
            "会被认定为数据不一致并抛出异常，从而保证 peaks 表总是完整、且与 peaklets 一一对齐。\n\n"
            "peaks 表同时携带峰形时序字段（rise_time、fall_time、width_25_75、area、height 等）"
            "与聚合规模字段（n_hits、n_channels），是上游 S1/S2 分类与物理筛选（peak_classification、"
            "s1_s2_pair_candidates）的唯一输入入口。"
        ),
        "workflow_steps": [
            "读取输入：从 context 获取 `peaklets` 与 `peaklet_features` 结构化数组；`peaklets` 为空时返回空 peaks 数组。",
            "排序特征行：以 `peaklet_features['peak_id']` 作稳定排序（mergesort），得到按 peak_id 递增的特征序列。",
            "对齐 peaklet：对每个 `peak_id`（即 peaklet 行号）用 `searchsorted` 定位特征行，并校验特征行的 peak_id 与 peaklet 一致；任一 peaklet 找不到特征则抛错。",
            "复制波形特征：将 time_start、time_end、time_peak、center_time、rise_time、fall_time、width_25_75、rise_time_10_50、range_90p_area、area、height、width 从对齐后的特征行复制到输出。",
            "填入峰规模信息：从 `peaklets` 复制 `n_hits` 与 `n_channels`。",
            "返回结果：输出 `PEAKS_DTYPE` 结构化数组，行序与 `peaklets` 完全一致，`peak_id` 即行索引。",
        ],
        "behavior_notes": [
            "`peaks` and `peaklets` are strictly 1:1: every peaklet row must have a matching `peaklet_features` row or compute raises.",
            "`peak_id` equals the row index in the output array and matches the corresponding `peaklets` row.",
            "Extra `peaklet_features` rows whose `peak_id` is not present in `peaklets` are simply not selected; they do not fail the plugin.",
            "The plugin performs no physics computation; all waveform quantities originate from `peaklet_features`.",
        ],
        "field_notes": {
            "peak_id": "Unique peak identifier, equal to the row index in `peaks` and aligned to the `peaklets` row of the same index.",
            "time_start": "Absolute start time (ps) of the peak window, copied from `peaklet_features`.",
            "time_end": "Absolute end time (ps) of the peak window, copied from `peaklet_features`.",
            "time_peak": "Absolute time (ps) of the peak maximum, copied from `peaklet_features`.",
            "center_time": "Center time (ps), copied from `peaklet_features`.",
            "rise_time": "Rise time (ns) from 10% to peak, copied from `peaklet_features`.",
            "fall_time": "Fall time (ns) from peak to 90%, copied from `peaklet_features`.",
            "width_25_75": "Width (ns) between the 25% and 75% area quantiles.",
            "rise_time_10_50": "Rise time (ns) between the 10% and 50% area quantiles.",
            "range_90p_area": "Time span (ns) covering the central 90% of the pulse area (5%-95%).",
            "area": "Integrated pulse area (sum of samples).",
            "height": "Peak height (maximum sample value).",
            "width": "Width (ns) of the peak window.",
            "n_hits": "Number of hit_merged rows aggregating to this peak, copied from `peaklets`.",
            "n_channels": "Channel aggregation scale of this peak (distinct (board, channel) pairs), copied from `peaklets`.",
        },
        "failure_modes": [
            "`peaklets` 或 `peaklet_features` 不是结构化数组时抛出 `ValueError`。",
            "存在某个 peaklet 在 `peaklet_features` 中找不到相同 `peak_id` 的特征行时抛出 `ValueError`，通常意味着上游缓存或成员关系错位。",
            "上游 `peaklet_features` 与 `peaklets` 的 `peak_id` 语义不一致（如特征缺失整段 peaklet）会触发上述异常而使 peaks 无法物化。",
        ],
        "downstream_consumers": [
            "peak_classification",
            "s1_s2_pair_candidates",
        ],
        "downstream_notes": [
            "`peak_classification` 直接以 peaks 特征做 S1/S2 分类，任何特征字段语义变化都会改变分类结果。",
            "`s1_s2_pair_candidates` 以 peaks（尤其经过分类后的 peak）生成物理候选配对，依赖 peaks 的时序与规模字段。",
        ],
        "agent_change_notes": [
            "输出字段或对齐规则的变动会影响 `peak_classification` 与 `s1_s2_pair_candidates`，请同步运行对应定向测试并重新生成文档。",
        ],
    }

    def compute(self, context: Any, run_id: str, **_kwargs) -> np.ndarray:
        peaklets = context.get_data(run_id, "peaklets")
        if not isinstance(peaklets, np.ndarray):
            raise ValueError("peaks expects peaklets as a structured array")
        if len(peaklets) == 0:
            return _empty_peaks()
        features = context.get_data(run_id, "peaklet_features")
        if not isinstance(features, np.ndarray):
            raise ValueError("peaks expects peaklet_features as a structured array")

        feature_peaklet_ids = features["peak_id"].astype(np.int64, copy=False)
        feature_order = np.argsort(feature_peaklet_ids, kind="mergesort")
        sorted_peaklet_ids = feature_peaklet_ids[feature_order]

        peaklet_ids = np.arange(len(peaklets), dtype=np.int64)
        matched_pos = np.searchsorted(sorted_peaklet_ids, peaklet_ids, side="right") - 1
        matched = matched_pos >= 0
        matched[matched] &= sorted_peaklet_ids[matched_pos[matched]] == peaklet_ids[matched]
        if not np.all(matched):
            missing_peaklet_id = int(peaklet_ids[~matched][0])
            raise ValueError(
                f"peaks could not resolve peaklet_features for peaklet_id={missing_peaklet_id}"
            )

        aligned_features = features[feature_order[matched_pos]]
        out = np.zeros(len(peaklets), dtype=PEAKS_DTYPE)
        out["peak_id"] = peaklet_ids
        for field in (
            "time_start",
            "time_end",
            "time_peak",
            "center_time",
            "rise_time",
            "fall_time",
            "width_25_75",
            "rise_time_10_50",
            "range_90p_area",
            "area",
            "height",
            "width",
        ):
            out[field] = aligned_features[field]
        out["n_hits"] = peaklets["n_hits"]
        out["n_channels"] = peaklets["n_channels"]
        return out


__all__ = [
    "PEAKLET_COMPONENTS_DTYPE",
    "PEAKLET_DTYPE",
    "PEAKLET_FEATURES_DTYPE",
    "PEAKLET_WAVEFORMS_DTYPE",
    "PEAKS_DTYPE",
    "PeakletComponentsPlugin",
    "PeakletFeaturesPlugin",
    "PeakletPlugin",
    "PeakletWaveformPlugin",
    "PeakletWaveformPoolPlugin",
    "PeaksPlugin",
    "_cluster_merged_hits",
    "_compute_area_quantile_times",
]
