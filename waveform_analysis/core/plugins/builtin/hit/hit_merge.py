"""Hit Merge Plugin - 合并临近 hit（同通道，允许跨波形/跨文件）"""

from collections.abc import Iterator
from typing import Any, NamedTuple

import numpy as np

try:
    from numba import njit

    _NUMBA_AVAILABLE = True
except ImportError:
    _NUMBA_AVAILABLE = False
    njit = None

from waveform_analysis.core.hardware.channel import group_indices_by_hardware_channel
from waveform_analysis.core.plugins.builtin.cpu._dt_compat import (
    require_dt_array,
    resolve_dt_config,
)
from waveform_analysis.core.plugins.builtin.hit.hit_finder import THRESHOLD_HIT_DTYPE
from waveform_analysis.core.plugins.core.base import Option, Plugin
from waveform_analysis.core.plugins.core.batch_processing import BatchProcessingPlugin

HIT_MERGED_DTYPE = np.dtype(
    [
        ("merged_id", "i8"),
        ("position", "i8"),
        ("time_start", "i8"),
        ("time_end", "i8"),
        ("sample_start", "i4"),
        ("sample_end", "i4"),
        ("width", "f4"),
        ("dt", "i4"),
        ("timestamp", "i8"),
        ("board", "i2"),
        ("channel", "i2"),
        ("record_id", "i8"),
        ("component_offset", "i8"),
        ("component_count", "i4"),
        ("is_single_record", "?"),
    ]
)

HIT_MERGED_COMPONENTS_DTYPE = np.dtype(
    [
        ("merged_index", "i8"),
        ("hit_index", "i8"),
    ]
)

HIT_MERGE_CLUSTERS_DTYPE = np.dtype(
    [
        ("cluster_index", "i8"),
        ("hit_index", "i8"),
    ]
)


def _get_field_safe(arr: np.ndarray, *candidates: str) -> np.ndarray:
    """Safely get field from array (supports multiple candidate names).

    This replaces the hot _pick function which was called 895k times.
    """
    for name in candidates:
        if name in arr.dtype.names:
            return arr[name]
    raise ValueError(f"None of {candidates} found in array with fields {arr.dtype.names}")


def _resolve_sample_fields(dtype: np.dtype) -> tuple[str, str] | tuple[None, None]:
    names = set(dtype.names or ())
    if {"sample_start", "sample_end"}.issubset(names):
        return "sample_start", "sample_end"
    if {"edge_start", "edge_end"}.issubset(names):
        return "edge_start", "edge_end"
    return None, None


def _materialize_array(data: Any, data_name: str, output_dtype: np.dtype) -> np.ndarray:
    if isinstance(data, np.ndarray):
        return data

    if not isinstance(data, Iterator) and not hasattr(data, "__next__"):
        raise ValueError(f"{data_name} expects a structured array or chunk stream")

    arrays: list[np.ndarray] = []
    total = 0
    for item in data:
        chunk_data = item if isinstance(item, np.ndarray) else getattr(item, "data", item)
        if not isinstance(chunk_data, np.ndarray):
            raise ValueError(f"{data_name} stream items must provide ndarray data")
        if len(chunk_data) > 0:
            arrays.append(chunk_data)
            total += len(chunk_data)

    if not arrays:
        return np.zeros(0, dtype=output_dtype)

    out = np.empty(total, dtype=arrays[0].dtype)
    cursor = 0
    for arr in arrays:
        n = len(arr)
        out[cursor : cursor + n] = arr
        cursor += n
    return out


# Numba-accelerated cluster merging
if _NUMBA_AVAILABLE:

    @njit(cache=True, nogil=True)  # type: ignore[misc]
    def _merge_clusters_numba(
        abs_starts: np.ndarray,
        abs_ends: np.ndarray,
        dt_ps: np.ndarray,
        merge_gap_ps: int,
        max_total_width_ps: int,
    ) -> tuple:
        """Numba JIT-compiled cluster merging.

        Returns (cluster_starts, cluster_ends) as index arrays.
        ~10-20x faster than Python loop.
        """
        n = len(abs_starts)
        if n == 0:
            return (np.empty(0, dtype=np.int32), np.empty(0, dtype=np.int32))

        # Pre-allocate for worst case (no merging)
        starts = np.empty(n, dtype=np.int32)
        ends = np.empty(n, dtype=np.int32)
        n_clusters = 0

        cluster_start_idx = 0
        cluster_start_ps = abs_starts[0]
        cluster_end_ps = abs_ends[0]
        cluster_dt = dt_ps[0]

        for i in range(1, n):
            gap = abs_starts[i] - cluster_end_ps
            next_end = max(cluster_end_ps, abs_ends[i])
            total_width = next_end - cluster_start_ps
            same_dt = dt_ps[i] == cluster_dt

            if (
                merge_gap_ps > 0
                and same_dt
                and gap <= merge_gap_ps
                and total_width <= max_total_width_ps
            ):
                # Merge into current cluster
                cluster_end_ps = next_end
            else:
                # Save current cluster
                starts[n_clusters] = cluster_start_idx
                ends[n_clusters] = i
                n_clusters += 1
                # Start new cluster
                cluster_start_idx = i
                cluster_start_ps = abs_starts[i]
                cluster_end_ps = abs_ends[i]
                cluster_dt = dt_ps[i]

        # Save last cluster
        starts[n_clusters] = cluster_start_idx
        ends[n_clusters] = n
        n_clusters += 1

        return (starts[:n_clusters].copy(), ends[:n_clusters].copy())

else:
    # Fallback when Numba is not available
    def _merge_clusters_numba(
        abs_starts: np.ndarray,
        abs_ends: np.ndarray,
        dt_ps: np.ndarray,
        merge_gap_ps: int,
        max_total_width_ps: int,
    ) -> tuple:
        """Python fallback when Numba unavailable."""
        raise RuntimeError("Numba not available")


def _pick(hit: np.void, *candidates: str) -> Any:
    """Legacy compatibility function - prefer _get_field_safe for arrays."""
    for name in candidates:
        if hit.dtype.names and name in hit.dtype.names:
            return hit[name]
    raise KeyError(f"Missing fields {candidates} in HIT_DTYPE")


def _resolve_merge_config(context: Any, plugin: Plugin) -> tuple[float, float, int | None]:
    merge_gap_ns = float(context.get_config(plugin, "merge_gap_ns"))
    max_total_width_ns = float(context.get_config(plugin, "max_total_width_ns"))
    explicit_dt = resolve_dt_config(
        context, plugin, deprecated_keys=("sampling_interval_ns", "dt_ns")
    )
    return merge_gap_ns, max_total_width_ns, explicit_dt


class _EnrichedArrays(NamedTuple):
    source_indices: np.ndarray
    abs_start_ps: np.ndarray
    abs_end_ps: np.ndarray
    dt_ns: np.ndarray
    dt_ps: np.ndarray


def _build_enriched_arrays(
    hits: np.ndarray,
    dt_values: np.ndarray,
    source_indices: np.ndarray,
    pre_trigger_ps: int = 0,
) -> _EnrichedArrays:
    n = len(hits)
    if n == 0:
        return _EnrichedArrays(
            source_indices=np.zeros(0, dtype=np.int64),
            abs_start_ps=np.zeros(0, dtype=np.int64),
            abs_end_ps=np.zeros(0, dtype=np.int64),
            dt_ns=np.zeros(0, dtype=np.int64),
            dt_ps=np.zeros(0, dtype=np.int64),
        )

    timestamps = _get_field_safe(hits, "timestamp", "hit_timestamp_ps").astype(np.int64)
    positions = _get_field_safe(hits, "position", "hit_sample_idx").astype(np.int64)
    edge_starts = _get_field_safe(hits, "edge_start", "sample_start", "hit_left_sample_idx").astype(
        np.int64
    )
    edge_ends = _get_field_safe(hits, "edge_end", "sample_end", "hit_right_sample_idx").astype(
        np.int64
    )

    dt_ns = dt_values.astype(np.int64)
    dt_ps = dt_values.astype(np.int64) * np.int64(1000)

    # 修正 timestamp：如果配置了 pre_trigger，则从触发点时间修正到 sample 0 时间
    corrected_timestamps = timestamps - np.int64(pre_trigger_ps)
    abs_start_ps = corrected_timestamps + (edge_starts - positions) * dt_ps
    abs_end_ps = corrected_timestamps + (edge_ends - positions) * dt_ps

    return _EnrichedArrays(
        source_indices=source_indices.astype(np.int64, copy=False),
        abs_start_ps=abs_start_ps,
        abs_end_ps=abs_end_ps,
        dt_ns=dt_ns,
        dt_ps=dt_ps,
    )


def _same_record_window(
    hits: np.ndarray,
    hit_indices: np.ndarray,
    start_name: str,
    end_name: str,
) -> tuple[int, int]:
    record_ids = hits["record_id"][hit_indices]
    if len(record_ids) == 0:
        return -1, -1

    first_record_id = record_ids[0]
    if not np.all(record_ids == first_record_id):
        return -1, -1

    sample_start = int(np.min(hits[start_name][hit_indices]))
    sample_end = int(np.max(hits[end_name][hit_indices]))
    return sample_start, sample_end


def _cluster_bounds_python(
    abs_starts: np.ndarray,
    abs_ends: np.ndarray,
    dt_ps: np.ndarray,
    merge_gap_ps: int,
    max_total_width_ps: int,
) -> tuple[np.ndarray, np.ndarray]:
    starts: list[int] = []
    ends: list[int] = []

    cluster_start_idx = 0
    cluster_start_ps = int(abs_starts[0])
    cluster_end_ps = int(abs_ends[0])
    cluster_dt = int(dt_ps[0])

    for idx in range(1, len(abs_starts)):
        gap_ps = int(abs_starts[idx]) - cluster_end_ps
        next_end = max(cluster_end_ps, int(abs_ends[idx]))
        total_width_ps = next_end - cluster_start_ps
        same_dt = int(dt_ps[idx]) == cluster_dt

        if (
            merge_gap_ps > 0
            and same_dt
            and gap_ps <= merge_gap_ps
            and total_width_ps <= max_total_width_ps
        ):
            cluster_end_ps = next_end
        else:
            starts.append(cluster_start_idx)
            ends.append(idx)
            cluster_start_idx = idx
            cluster_start_ps = int(abs_starts[idx])
            cluster_end_ps = int(abs_ends[idx])
            cluster_dt = int(dt_ps[idx])

    starts.append(cluster_start_idx)
    ends.append(len(abs_starts))
    return np.asarray(starts, dtype=np.int32), np.asarray(ends, dtype=np.int32)


def _build_cluster_rows_from_bounds(
    sorted_source_indices: np.ndarray,
    cluster_starts: np.ndarray,
    cluster_ends: np.ndarray,
    cluster_offset: int,
) -> np.ndarray:
    n_clusters = len(cluster_starts)
    if n_clusters == 0:
        return np.zeros(0, dtype=HIT_MERGE_CLUSTERS_DTYPE)

    counts = (cluster_ends - cluster_starts).astype(np.int64, copy=False)
    rows = np.empty(len(sorted_source_indices), dtype=HIT_MERGE_CLUSTERS_DTYPE)
    rows["cluster_index"] = np.repeat(
        np.arange(cluster_offset, cluster_offset + n_clusters, dtype=np.int64),
        counts,
    )
    rows["hit_index"] = sorted_source_indices
    return rows


def _compute_cluster_rows(
    hits: np.ndarray,
    merge_gap_ns: float,
    max_total_width_ns: float,
    explicit_dt: int | None,
    plugin_name: str,
    pre_trigger_ps: int = 0,
) -> np.ndarray:
    if len(hits) == 0:
        return np.zeros(0, dtype=HIT_MERGE_CLUSTERS_DTYPE)

    if "board" in hits.dtype.names:
        boards = hits["board"]
    else:
        boards = np.zeros(len(hits), dtype=np.int16)
    if "channel" not in hits.dtype.names:
        raise ValueError(f"{plugin_name} requires hit data with a 'channel' field")
    channels = hits["channel"]

    cluster_rows: list[np.ndarray] = []
    cluster_offset = 0
    merge_gap_ps = int(round(merge_gap_ns * 1e3))
    max_total_width_ps = int(round(max_total_width_ns * 1e3))

    for _hw_channel, indices in group_indices_by_hardware_channel(boards, channels).items():
        ch_hits = hits[indices]
        if len(ch_hits) == 0:
            continue

        channel_dt = require_dt_array(
            ch_hits,
            explicit_dt=explicit_dt,
            plugin_name=plugin_name,
            data_name="hit_threshold[channel]",
        )
        enriched = _build_enriched_arrays(
            ch_hits, channel_dt, indices.astype(np.int64, copy=False), pre_trigger_ps=pre_trigger_ps
        )
        order = np.argsort(enriched.abs_start_ps, kind="mergesort")
        abs_starts = enriched.abs_start_ps[order]
        abs_ends = enriched.abs_end_ps[order]
        dts = enriched.dt_ps[order]
        sorted_source_indices = enriched.source_indices[order]

        if _NUMBA_AVAILABLE and len(abs_starts) > 50:
            cluster_starts, cluster_ends = _merge_clusters_numba(
                abs_starts, abs_ends, dts, merge_gap_ps, max_total_width_ps
            )
        else:
            # Numba 不可用时直接报错
            if not _NUMBA_AVAILABLE:
                raise RuntimeError("Numba is required for hit merging")
            cluster_starts, cluster_ends = _cluster_bounds_python(
                abs_starts, abs_ends, dts, merge_gap_ps, max_total_width_ps
            )

        rows = _build_cluster_rows_from_bounds(
            sorted_source_indices,
            cluster_starts,
            cluster_ends,
            cluster_offset,
        )
        if len(rows) > 0:
            cluster_rows.append(rows)
            cluster_offset += len(cluster_starts)

    if cluster_rows:
        return np.concatenate(cluster_rows)
    return np.zeros(0, dtype=HIT_MERGE_CLUSTERS_DTYPE)


def _build_enriched_for_hits(
    hits: np.ndarray,
    explicit_dt: int | None,
    plugin_name: str,
    pre_trigger_ps: int = 0,
) -> _EnrichedArrays:
    dt_values = require_dt_array(
        hits,
        explicit_dt=explicit_dt,
        plugin_name=plugin_name,
        data_name="hit_threshold",
    )
    return _build_enriched_arrays(
        hits, dt_values, np.arange(len(hits), dtype=np.int64), pre_trigger_ps=pre_trigger_ps
    )


def _cluster_bounds(cluster_rows: np.ndarray) -> list[tuple[int, int, int]]:
    if len(cluster_rows) == 0:
        return []

    cluster_indices = np.asarray(cluster_rows["cluster_index"], dtype=np.int64)
    boundaries = np.flatnonzero(np.diff(cluster_indices) != 0) + 1
    starts = np.concatenate(([0], boundaries))
    ends = np.concatenate((boundaries, [len(cluster_rows)]))
    return [
        (int(cluster_indices[start]), int(start), int(end))
        for start, end in zip(starts, ends, strict=False)
    ]


def _cluster_bounds_arrays(cluster_rows: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    cluster_index = cluster_rows["cluster_index"]
    boundaries = np.flatnonzero(np.diff(cluster_index) != 0) + 1

    starts = np.empty(len(boundaries) + 1, dtype=np.int64)
    starts[0] = 0
    starts[1:] = boundaries

    ends = np.empty_like(starts)
    ends[:-1] = boundaries
    ends[-1] = len(cluster_rows)

    counts = ends - starts
    return starts, ends, counts


def _hits_to_merged_fast(hits: np.ndarray, explicit_dt: int | None, plugin_name: str) -> np.ndarray:
    dt_values = require_dt_array(
        hits,
        explicit_dt=explicit_dt,
        plugin_name=plugin_name,
        data_name="hit_threshold",
    )
    start_name, end_name = _resolve_sample_fields(hits.dtype)
    if start_name is None or end_name is None:
        raise ValueError(f"{plugin_name} requires hit data with sample start/end fields")

    out = np.zeros(len(hits), dtype=HIT_MERGED_DTYPE)
    out["merged_id"] = np.arange(len(hits), dtype=np.int64)
    out["position"] = _get_field_safe(hits, "position", "hit_sample_idx")
    out["sample_start"] = hits[start_name]
    out["sample_end"] = hits[end_name]
    out["width"] = _get_field_safe(hits, "width")
    out["dt"] = dt_values
    out["timestamp"] = _get_field_safe(hits, "timestamp", "hit_timestamp_ps")
    out["board"] = hits["board"] if "board" in hits.dtype.names else 0
    out["channel"] = hits["channel"]
    out["record_id"] = hits["record_id"]
    out["component_offset"] = np.arange(len(hits), dtype=np.int64)
    out["component_count"] = 1
    out["is_single_record"] = True

    # 计算绝对时间
    positions = out["position"]
    timestamps = out["timestamp"]
    sample_starts = out["sample_start"]
    sample_ends = out["sample_end"]
    dt_ps = dt_values.astype(np.int64) * 1000

    out["time_start"] = timestamps + (sample_starts - positions) * dt_ps
    out["time_end"] = timestamps + (sample_ends - positions) * dt_ps

    return out


def _hits_to_cluster_rows_fast(hits: np.ndarray) -> np.ndarray:
    rows = np.zeros(len(hits), dtype=HIT_MERGE_CLUSTERS_DTYPE)
    rows["cluster_index"] = np.arange(len(hits), dtype=np.int64)
    rows["hit_index"] = np.arange(len(hits), dtype=np.int64)
    return rows


def _compute_canonical_cluster_rows(
    hits: np.ndarray,
    context: Any,
    merge_plugin: Plugin,
    pre_trigger_ps: int,
) -> tuple[np.ndarray, int | None, bool]:
    merge_gap_ns, max_total_width_ns, explicit_dt = _resolve_merge_config(context, merge_plugin)
    if merge_gap_ns <= 0:
        return _hits_to_cluster_rows_fast(hits), explicit_dt, True
    return (
        _compute_cluster_rows(
            hits,
            merge_gap_ns=merge_gap_ns,
            max_total_width_ns=max_total_width_ns,
            explicit_dt=explicit_dt,
            plugin_name=merge_plugin.provides,
            pre_trigger_ps=pre_trigger_ps,
        ),
        explicit_dt,
        False,
    )


def _cluster_rows_to_components(cluster_rows: np.ndarray) -> np.ndarray:
    out = np.zeros(len(cluster_rows), dtype=HIT_MERGED_COMPONENTS_DTYPE)
    out["merged_index"] = cluster_rows["cluster_index"]
    out["hit_index"] = cluster_rows["hit_index"]
    return out


def _build_merged_from_cluster_rows(
    hits: np.ndarray,
    cluster_rows: np.ndarray,
    enriched: _EnrichedArrays,
) -> np.ndarray:
    """Build hit_merged output from cluster_rows and enriched arrays.

    Pre-allocates output array and fills in-place, avoiding list append + np.array conversion.
    """
    if len(cluster_rows) == 0:
        return np.zeros(0, dtype=HIT_MERGED_DTYPE)

    start_name, end_name = _resolve_sample_fields(hits.dtype)
    if start_name is None or end_name is None:
        raise ValueError("hit_merged requires sample start/end fields")

    starts, ends, counts = _cluster_bounds_arrays(cluster_rows)
    n_clusters = len(starts)
    if not np.array_equal(cluster_rows["cluster_index"][starts], np.arange(n_clusters)):
        raise ValueError("hit_merge_clusters rows are not ordered by cluster_index without gaps")

    merged = np.empty(n_clusters, dtype=HIT_MERGED_DTYPE)
    merged["merged_id"] = np.arange(n_clusters, dtype=np.int64)
    hit_index_all = cluster_rows["hit_index"]

    single_out = np.flatnonzero(counts == 1)
    if len(single_out) > 0:
        single_hit_idx = hit_index_all[starts[single_out]]

        merged["position"][single_out] = hits["position"][single_hit_idx]
        merged["sample_start"][single_out] = hits[start_name][single_hit_idx]
        merged["sample_end"][single_out] = hits[end_name][single_hit_idx]
        merged["width"][single_out] = hits["width"][single_hit_idx]
        merged["timestamp"][single_out] = hits["timestamp"][single_hit_idx]
        merged["channel"][single_out] = hits["channel"][single_hit_idx]
        merged["record_id"][single_out] = hits["record_id"][single_hit_idx]
        merged["component_offset"][single_out] = starts[single_out]
        merged["component_count"][single_out] = 1
        merged["is_single_record"][single_out] = True
        if "dt" in hits.dtype.names:
            merged["dt"][single_out] = hits["dt"][single_hit_idx]
        else:
            merged["dt"][single_out] = enriched.dt_ns[single_hit_idx]
        if "board" in hits.dtype.names:
            merged["board"][single_out] = hits["board"][single_hit_idx]
        else:
            merged["board"][single_out] = 0

        # 计算绝对时间（单 hit 情况）
        merged["time_start"][single_out] = enriched.abs_start_ps[single_hit_idx]
        merged["time_end"][single_out] = enriched.abs_end_ps[single_hit_idx]

    for out_idx in np.flatnonzero(counts != 1):
        start = int(starts[out_idx])
        end = int(ends[out_idx])
        hit_indices = hit_index_all[start:end]
        abs_starts = enriched.abs_start_ps[hit_indices]
        abs_ends = enriched.abs_end_ps[hit_indices]
        sample_start, sample_end = _same_record_window(hits, hit_indices, start_name, end_name)

        cluster_start_ps = int(np.min(abs_starts))
        cluster_end_ps = int(np.max(abs_ends))
        mid2 = cluster_start_ps + cluster_end_ps
        mids2 = abs_starts + abs_ends
        anchor_local = int(np.argmin(np.abs(mids2 - mid2)))
        anchor_idx = int(hit_indices[anchor_local])

        merged["position"][out_idx] = hits["position"][anchor_idx]
        merged["time_start"][out_idx] = cluster_start_ps
        merged["time_end"][out_idx] = cluster_end_ps
        merged["sample_start"][out_idx] = sample_start
        merged["sample_end"][out_idx] = sample_end
        merged["is_single_record"][out_idx] = sample_start >= 0 and sample_end >= 0
        if sample_start < 0 or sample_end < 0:
            merged["width"][out_idx] = -1.0
        else:
            merged["width"][out_idx] = float(sample_end - sample_start)
        if "dt" in hits.dtype.names:
            merged["dt"][out_idx] = hits["dt"][anchor_idx]
        else:
            merged["dt"][out_idx] = enriched.dt_ns[anchor_idx]
        merged["timestamp"][out_idx] = hits["timestamp"][anchor_idx]
        merged["channel"][out_idx] = hits["channel"][anchor_idx]
        merged["record_id"][out_idx] = hits["record_id"][anchor_idx]
        merged["component_offset"][out_idx] = start
        merged["component_count"][out_idx] = end - start
        if "board" in hits.dtype.names:
            merged["board"][out_idx] = hits["board"][anchor_idx]
        else:
            merged["board"][out_idx] = 0

    return merged


class HitMergePlugin(BatchProcessingPlugin):
    """Merge nearby hits from hit_threshold within the same channel."""

    provides = "hit_merged"
    depends_on = ["hit_threshold"]
    description = "Merge nearby threshold hits per channel with time-gap and max-width constraints."
    version = "2.1.0"
    save_when = "always"
    output_dtype = HIT_MERGED_DTYPE
    agent_doc = {
        "overview": (
            "HitMergePlugin 是波形分析中最核心的后处理插件之一，负责将 hit_threshold "
            "产出的过阈 hit 按时间邻近性合并为统一的 hit_merged 记录。它不直接修改原始 "
            "hit_threshold 数据，而是生成新的结构化输出，同时提供 cluster 级别的成员关系"
            "（hit_merge_clusters）供下游诊断使用。\n\n"
            "该插件由三部分协同工作：HitMergePlugin（主合并逻辑）、HitMergeClustersPlugin"
            "（导出 cluster 成员关系）和 HitMergedComponentsPlugin（验证与展开 component）。"
            '合并策略的核心是"同板同通道、同 dt、邻近链式合并"——即只有相同 (board, channel) '
            "且采样间隔相同的 hit 才能归入同一 cluster，并通过时间 gap 和总宽度限制控制 cluster 的"
            "生长。\n\n"
            "合并窗口的中点 anchor 策略确保上下游一致：多 hit cluster 选取最接近合并时间窗口中心"
            "的 hit 作为 anchor，写入 position、timestamp、channel、record_id 等关键字段。"
            "跨 record 时，sample_start/sample_end/width 标记为 -1，time_start/time_end 始终有效。\n\n"
            "该插件不依赖外部级联状态，所有合并判断完全由配置 merge_gap_ns、max_total_width_ns "
            "和 dt 推导的绝对时间窗口决定。"
        ),
        "workflow_steps": [
            "**识别可合并片段**：`hit_threshold` 每行为过阈片段，判断哪些相邻片段应合并为同一次通道响应。",
            "**保持通道/刻度一致**：仅合并同一 `(board, channel)`、相同 `dt` 的片段，避免混入不同时间刻度。",
            "**按时间连接**：空档 ≤ `merge_gap_ns` 才接入同窗口；`merge_gap_ns` ≤ 0 时关闭合并。",
            "**限制链式总时长**：合并窗口超过 `max_total_width_ns` 时，后续片段另起新的 `hit_merged`。",
            "**选择代表 hit**：取最接近窗口中心的原始 hit，继承其 position、timestamp、channel、record_id。",
            "**记录窗口与成员**：输出时间范围与成员索引；跨 record 时 `sample_start`、`sample_end`、`width` 为 -1。",
        ],
        "behavior_notes": [
            "Only hits with the same `(board, channel)` are eligible for merging; boardless inputs use board `0` as the compatibility value.",
            "`merge_gap_ns <= 0` disables merging and maps each `hit_threshold` row to one `hit_merged` row.",
            "The merge decision uses absolute hit windows derived from `timestamp`, sample window fields, `dt`, and the configured pre-trigger offset.",
            "Hits with different resolved `dt` values are not merged into the same cluster.",
            "`max_total_width_ns` limits the total absolute width of chained merges, so a locally adjacent hit can still start a new cluster when the accumulated window would exceed the limit.",
        ],
        "field_notes": {
            "merged_id": "Unique identifier for this hit_merged record, equal to its row index (0-based) in the output array. Used for tracking and referencing specific merged hits.",
            "position": "Anchor hit position; for multi-hit clusters this is the hit closest to the merged window midpoint.",
            "time_start": "Absolute start time (ps) of the merged window; always valid regardless of whether components span records.",
            "time_end": "Absolute end time (ps) of the merged window; always valid regardless of whether components span records.",
            "sample_start": "Merged sample window start when all components belong to one record; `-1` when the cluster spans records.",
            "sample_end": "Merged sample window end when all components belong to one record; `-1` when the cluster spans records.",
            "width": "Merged sample-window width; `-1.0` when the cluster spans records or otherwise cannot resolve a direct sample window.",
            "dt": "Resolved sampling interval from the anchor hit or compatible `dt` configuration fallback.",
            "timestamp": "Anchor hit timestamp; for multi-hit clusters this follows the same anchor rule as `position`.",
            "board": "Hardware board from the anchor hit; boardless inputs use compatibility value `0`.",
            "channel": "Hardware channel from the anchor hit; merging never crosses channel boundaries.",
            "record_id": "Anchor hit record id, not necessarily a shared record id for every component.",
            "component_offset": "Start row in `hit_merge_clusters` for this cluster's contiguous membership rows.",
            "component_count": "Number of contiguous `hit_merge_clusters` membership rows for this cluster.",
            "is_single_record": "True when all component hits belong to the same record (fast path available); False when spanning records.",
        },
        "config_notes": {
            "merge_gap_ns": "Maximum boundary gap in ns; values `<= 0` disable merging.",
            "max_total_width_ns": "Maximum total absolute cluster width in ns for chained merges.",
            "dt": "Compatibility fallback sampling interval in ns, used only when `hit_threshold` lacks a `dt` field.",
        },
        "cluster_contract": [
            "`hit_merged` computes canonical cluster membership from its own config; `hit_merge_clusters` exports the same membership rows for diagnostics and inspection.",
            "Rows consumed by one `hit_merged` row must be contiguous in the canonical membership order.",
            "`cluster_index` values must be sorted, contiguous, and gap-free from `0` to `len(hit_merged) - 1`.",
            "`component_offset` and `component_count` point back into the exact membership slice used by `hit_merged_components`.",
        ],
        "failure_modes": [
            "`hit_threshold` is missing required `channel` data, so same-channel grouping cannot be resolved.",
            "`hit_threshold` lacks `dt` and no compatible `dt` config fallback is available.",
            "Canonical cluster rows are not ordered by contiguous, gap-free `cluster_index` values.",
            "Cluster rows reference hit indices that are outside the materialized `hit_threshold` array.",
        ],
        "downstream_consumers": [
            "hit_merged_components",
            "hit_merged_features",
            "hit_grouped",
            "peaklets",
            "peaklet_components",
        ],
        "downstream_notes": [
            "Field semantics and row ordering changes propagate to component expansion, waveform feature extraction, cross-channel grouping, and peaklet membership.",
            "Changing `component_offset`/`component_count` requires matching updates to `hit_merge_clusters` ordering and all component consumer tests.",
            "Changing anchor-field semantics affects downstream `position`, `timestamp`, `record_id`, and channel aggregation behavior.",
        ],
        "agent_change_notes": [
            "v2.1.0: Added `merged_id` field as unique identifier equal to row index. This is a backward-compatible addition; downstream plugins auto-adapt via dtype.names checks.",
            "v2.0.0: Added `time_start`, `time_end`, `is_single_record` fields to support cross-record merging.",
            "Changing merge behavior, output field semantics, or dtype requires a `version` bump because cache lineage depends on the plugin contract.",
            "Keep `hit_merged` and `hit_merged_components` in sync; membership ordering is part of the downstream contract.",
            "After contract changes, regenerate agent docs and run targeted tests for `hit_merge`, `hit_merged_components`, `hit_merged_features`, `hit_grouped`, and `peaklets` consumers as appropriate.",
        ],
    }

    options = {
        "merge_gap_ns": Option(
            default=0.0,
            type=float,
            help="最大边界间距（ns），<=0 表示不合并",
        ),
        "max_total_width_ns": Option(
            default=10000.0,
            type=float,
            help="链式合并后的最大总宽度（ns）",
        ),
        "dt": Option(
            default=None,
            type=int,
            help="采样间隔（ns）。仅在输入 hit_threshold 缺少 dt 字段时作为兼容补充。",
        ),
    }

    def compute(self, context: Any, run_id: str, **_kwargs) -> np.ndarray:
        from waveform_analysis.core.processing.time_utils import get_pre_trigger_offset_ps

        hits = _materialize_array(
            context.get_data(run_id, "hit_threshold"),
            "hit_merged hit_threshold input",
            THRESHOLD_HIT_DTYPE,
        )
        if len(hits) == 0:
            return np.zeros(0, dtype=HIT_MERGED_DTYPE)

        pre_trigger_ps = get_pre_trigger_offset_ps(context)
        cluster_rows, explicit_dt, merge_disabled = _compute_canonical_cluster_rows(
            hits, context, self, pre_trigger_ps
        )

        if merge_disabled:
            return _hits_to_merged_fast(hits, explicit_dt=explicit_dt, plugin_name=self.provides)

        enriched = _build_enriched_for_hits(
            hits, explicit_dt=explicit_dt, plugin_name=self.provides, pre_trigger_ps=pre_trigger_ps
        )

        return _build_merged_from_cluster_rows(hits, cluster_rows, enriched)


class HitMergeClustersPlugin(Plugin):
    """Internal flat cluster membership for hit merge outputs."""

    provides = "hit_merge_clusters"
    depends_on = ["hit_merged", "hit_threshold"]
    description = "Export cluster membership rows using the authoritative hit_merged configuration."
    version = "1.1.0"
    save_when = "always"
    output_dtype = HIT_MERGE_CLUSTERS_DTYPE

    def compute(self, context: Any, run_id: str, **_kwargs) -> np.ndarray:
        from waveform_analysis.core.processing.time_utils import get_pre_trigger_offset_ps

        hits = _materialize_array(
            context.get_data(run_id, "hit_threshold"),
            "hit_merge_clusters hit_threshold input",
            THRESHOLD_HIT_DTYPE,
        )
        if len(hits) == 0:
            return np.zeros(0, dtype=HIT_MERGE_CLUSTERS_DTYPE)

        pre_trigger_ps = get_pre_trigger_offset_ps(context)
        merge_plugin = context.get_plugin("hit_merged")
        cluster_rows, _explicit_dt, _merge_disabled = _compute_canonical_cluster_rows(
            hits, context, merge_plugin, pre_trigger_ps
        )
        return cluster_rows


class HitMergedComponentsPlugin(Plugin):
    """Return flat component hit indices for each hit_merged cluster."""

    provides = "hit_merged_components"
    lineage_virtual = True
    depends_on = ["hit_merged", "hit_threshold"]
    description = "Return per-cluster component hit indices for hit_merged rows."
    version = "1.1.0"
    save_when = "always"
    output_dtype = HIT_MERGED_COMPONENTS_DTYPE
    options = {
        "validate_components": Option(
            default=False,
            type=bool,
            help="校验 hit_merged 的 component_offset/component_count 与 cluster rows 是否一致。",
        ),
    }

    def compute(self, context: Any, run_id: str, **_kwargs) -> np.ndarray:
        from waveform_analysis.core.processing.time_utils import get_pre_trigger_offset_ps

        merged = _materialize_array(
            context.get_data(run_id, "hit_merged"),
            "hit_merged_components hit_merged input",
            HIT_MERGED_DTYPE,
        )
        if len(merged) == 0:
            return np.zeros(0, dtype=HIT_MERGED_COMPONENTS_DTYPE)

        pre_trigger_ps = get_pre_trigger_offset_ps(context)
        hits = _materialize_array(
            context.get_data(run_id, "hit_threshold"),
            "hit_merged_components hit_threshold input",
            THRESHOLD_HIT_DTYPE,
        )
        merge_plugin = context.get_plugin("hit_merged")
        cluster_rows, _explicit_dt, _merge_disabled = _compute_canonical_cluster_rows(
            hits, context, merge_plugin, pre_trigger_ps
        )
        if len(cluster_rows) == 0:
            return np.zeros(0, dtype=HIT_MERGED_COMPONENTS_DTYPE)

        validate_components = bool(context.get_config(self, "validate_components"))
        if not validate_components:
            return _cluster_rows_to_components(cluster_rows)

        cluster_bounds = _cluster_bounds(cluster_rows)
        if len(cluster_bounds) != len(merged):
            raise ValueError(
                "hit_merged_components cluster count does not match hit_merged rows: "
                f"clusters={len(cluster_bounds)}, hit_merged={len(merged)}"
            )

        component_rows: list[tuple[int, int]] = []
        for merged_idx, (cluster_index, start, end) in enumerate(cluster_bounds):
            count = end - start
            if (
                "component_offset" in merged.dtype.names
                and int(merged[merged_idx]["component_offset"]) != start
            ):
                raise ValueError(
                    f"hit_merged[{merged_idx}] component_offset mismatch: "
                    f"expected {start}, got {int(merged[merged_idx]['component_offset'])}"
                )
            if (
                "component_count" in merged.dtype.names
                and int(merged[merged_idx]["component_count"]) != count
            ):
                raise ValueError(
                    f"hit_merged[{merged_idx}] component_count mismatch: "
                    f"expected {count}, got {int(merged[merged_idx]['component_count'])}"
                )
            if cluster_index != merged_idx:
                raise ValueError(
                    "hit_merge_clusters rows are not ordered by cluster_index without gaps"
                )
            for hit_index in np.asarray(cluster_rows["hit_index"][start:end], dtype=np.int64):
                component_rows.append((merged_idx, int(hit_index)))

        if component_rows:
            return np.array(component_rows, dtype=HIT_MERGED_COMPONENTS_DTYPE)
        return np.zeros(0, dtype=HIT_MERGED_COMPONENTS_DTYPE)


__all__ = [
    "HIT_MERGE_CLUSTERS_DTYPE",
    "HIT_MERGED_COMPONENTS_DTYPE",
    "HIT_MERGED_DTYPE",
    "HitMergeClustersPlugin",
    "HitMergePlugin",
    "HitMergedComponentsPlugin",
]
