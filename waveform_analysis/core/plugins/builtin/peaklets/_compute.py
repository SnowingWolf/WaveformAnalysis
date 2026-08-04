"""Peaklet 家族共享计算 - 属主 bundle peaklets。供 peaklets / peaklet_components / peaklet_waveforms / peaklet_waveform_pool / peaklet_features / peaks 复用。"""

from typing import Any

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


from waveform_analysis.core.plugins.builtin.cpu._record_utils import RecordLookup
from waveform_analysis.core.plugins.core.base import Plugin

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
        # 懒导入避免 _compute <-> plugin 循环依赖
        from waveform_analysis.core.plugins.builtin.peaklets.plugin import PeakletPlugin

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
