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
from waveform_analysis.core.plugins.builtin.cpu.hit_finder import THRESHOLD_HIT_DTYPE
from waveform_analysis.core.plugins.core.base import Option, Plugin
from waveform_analysis.core.plugins.core.batch_processing import BatchProcessingPlugin

HIT_MERGED_DTYPE = np.dtype(
    [
        ("position", "i8"),
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
    for item in data:
        chunk_data = item if isinstance(item, np.ndarray) else getattr(item, "data", item)
        if not isinstance(chunk_data, np.ndarray):
            raise ValueError(f"{data_name} stream items must provide ndarray data")
        if len(chunk_data) > 0:
            arrays.append(chunk_data)

    if not arrays:
        return np.zeros(0, dtype=output_dtype)

    # Optimized: batch concatenate to reduce memory copies for large chunk counts
    if len(arrays) > 100:
        batch_size = 100
        merged_batches = []
        for i in range(0, len(arrays), batch_size):
            batch = arrays[i : i + batch_size]
            merged_batches.append(np.concatenate(batch))
        return np.concatenate(merged_batches)
    return np.concatenate(arrays)


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


def _resolve_cluster_sample_window(hits: np.ndarray) -> tuple[int, int]:
    if len(np.unique(hits["record_id"])) != 1:
        return -1, -1

    start_name, end_name = _resolve_sample_fields(hits.dtype)
    if start_name is None or end_name is None:
        return -1, -1

    sample_start = int(np.min(hits[start_name]))
    sample_end = int(np.max(hits[end_name]))
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
    if len(cluster_starts) == 0:
        return np.zeros(0, dtype=HIT_MERGE_CLUSTERS_DTYPE)

    counts = (cluster_ends - cluster_starts).astype(np.int64)
    rows = np.zeros(int(np.sum(counts)), dtype=HIT_MERGE_CLUSTERS_DTYPE)
    rows["cluster_index"] = np.repeat(
        np.arange(cluster_offset, cluster_offset + len(cluster_starts), dtype=np.int64),
        counts,
    )

    cursor = 0
    for start, end in zip(cluster_starts, cluster_ends, strict=False):
        count = int(end - start)
        rows["hit_index"][cursor : cursor + count] = sorted_source_indices[int(start) : int(end)]
        cursor += count
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

        if _NUMBA_AVAILABLE and len(abs_starts) > 200:
            cluster_starts, cluster_ends = _merge_clusters_numba(
                abs_starts, abs_ends, dts, merge_gap_ps, max_total_width_ps
            )
        else:
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
    return out


def _hits_to_cluster_rows_fast(hits: np.ndarray) -> np.ndarray:
    rows = np.zeros(len(hits), dtype=HIT_MERGE_CLUSTERS_DTYPE)
    rows["cluster_index"] = np.arange(len(hits), dtype=np.int64)
    rows["hit_index"] = np.arange(len(hits), dtype=np.int64)
    return rows


def _cluster_rows_to_components(cluster_rows: np.ndarray) -> np.ndarray:
    out = np.zeros(len(cluster_rows), dtype=HIT_MERGED_COMPONENTS_DTYPE)
    out["merged_index"] = cluster_rows["cluster_index"]
    out["hit_index"] = cluster_rows["hit_index"]
    return out


def _emit_cluster(
    cluster_hits: np.ndarray,
    abs_starts: np.ndarray,
    abs_ends: np.ndarray,
    dt_ns: np.ndarray,
    component_offset: int,
) -> tuple:
    component_count = len(cluster_hits)
    sample_start_window, sample_end_window = _resolve_cluster_sample_window(cluster_hits)

    if len(cluster_hits) == 1:
        h = cluster_hits[0]
        start_name, end_name = _resolve_sample_fields(h.dtype)
        if start_name is None or end_name is None:
            sample_start = -1
            sample_end = -1
        else:
            sample_start = int(h[start_name])
            sample_end = int(h[end_name])

        return (
            int(h["position"]),
            sample_start,
            sample_end,
            float(h["width"]),
            int(h["dt"]) if "dt" in h.dtype.names else int(dt_ns[0]),
            int(h["timestamp"]),
            int(h["board"]) if "board" in h.dtype.names else 0,
            int(h["channel"]),
            int(h["record_id"]),
            component_offset,
            component_count,
        )

    cluster_start_ps = int(np.min(abs_starts))
    cluster_end_ps = int(np.max(abs_ends))
    cluster_mid_ps = (cluster_start_ps + cluster_end_ps) * 0.5
    mids = (abs_starts + abs_ends) * 0.5
    anchor_idx = int(np.argmin(np.abs(mids - cluster_mid_ps)))
    anchor = cluster_hits[anchor_idx]

    merged_sample_start = sample_start_window
    merged_sample_end = sample_end_window
    merged_width = float(max(merged_sample_end - merged_sample_start, 0.0))
    if merged_sample_start < 0 or merged_sample_end < 0:
        merged_width = -1.0

    return (
        int(anchor["position"]),
        int(merged_sample_start),
        int(merged_sample_end),
        merged_width,
        int(anchor["dt"]) if "dt" in anchor.dtype.names else int(dt_ns[anchor_idx]),
        int(anchor["timestamp"]),
        int(anchor["board"]) if "board" in anchor.dtype.names else 0,
        int(anchor["channel"]),
        int(anchor["record_id"]),
        component_offset,
        component_count,
    )


class HitMergePlugin(BatchProcessingPlugin):
    """Merge nearby hits from hit_threshold within the same channel."""

    provides = "hit_merged"
    depends_on = ["hit_threshold", "hit_merge_clusters"]
    description = "Merge nearby threshold hits per channel with time-gap and max-width constraints."
    version = "1.1.1"
    save_when = "always"
    output_dtype = HIT_MERGED_DTYPE

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

        merge_gap_ns, max_total_width_ns, explicit_dt = _resolve_merge_config(context, self)
        pre_trigger_ps = get_pre_trigger_offset_ps(context)

        if merge_gap_ns <= 0:
            return _hits_to_merged_fast(hits, explicit_dt=explicit_dt, plugin_name=self.provides)

        try:
            cluster_rows = context.get_data(run_id, "hit_merge_clusters")
            if cluster_rows is not None:
                cluster_rows = _materialize_array(
                    cluster_rows,
                    "hit_merged hit_merge_clusters input",
                    HIT_MERGE_CLUSTERS_DTYPE,
                )
        except (KeyError, FileNotFoundError):
            cluster_rows = _compute_cluster_rows(
                hits,
                merge_gap_ns=merge_gap_ns,
                max_total_width_ns=max_total_width_ns,
                explicit_dt=explicit_dt,
                plugin_name="hit_merge_clusters",
                pre_trigger_ps=pre_trigger_ps,
            )
        if cluster_rows is None:
            cluster_rows = _compute_cluster_rows(
                hits,
                merge_gap_ns=merge_gap_ns,
                max_total_width_ns=max_total_width_ns,
                explicit_dt=explicit_dt,
                plugin_name="hit_merge_clusters",
                pre_trigger_ps=pre_trigger_ps,
            )
        if not isinstance(cluster_rows, np.ndarray):
            raise ValueError("hit_merged expects hit_merge_clusters as a structured array")

        enriched = _build_enriched_for_hits(
            hits, explicit_dt=explicit_dt, plugin_name=self.provides, pre_trigger_ps=pre_trigger_ps
        )

        merged_rows: list[tuple] = []
        for cluster_index, start, end in _cluster_bounds(cluster_rows):
            hit_indices = np.asarray(cluster_rows["hit_index"][start:end], dtype=np.int64)
            if len(hit_indices) == 0:
                continue
            merged_rows.append(
                _emit_cluster(
                    hits[hit_indices],
                    abs_starts=enriched.abs_start_ps[hit_indices],
                    abs_ends=enriched.abs_end_ps[hit_indices],
                    dt_ns=enriched.dt_ns[hit_indices],
                    component_offset=start,
                )
            )
            if cluster_index != len(merged_rows) - 1:
                raise ValueError(
                    "hit_merge_clusters rows are not ordered by cluster_index without gaps"
                )

        if merged_rows:
            return np.array(merged_rows, dtype=HIT_MERGED_DTYPE)
        return np.zeros(0, dtype=HIT_MERGED_DTYPE)


class HitMergeClustersPlugin(Plugin):
    """Internal flat cluster membership for hit merge outputs."""

    provides = "hit_merge_clusters"
    depends_on = ["hit_threshold"]
    description = "Internal cluster membership rows shared by hit_merged outputs."
    version = "1.0.1"
    save_when = "always"
    output_dtype = HIT_MERGE_CLUSTERS_DTYPE

    options = HitMergePlugin.options

    def compute(self, context: Any, run_id: str, **_kwargs) -> np.ndarray:
        from waveform_analysis.core.processing.time_utils import get_pre_trigger_offset_ps

        hits = _materialize_array(
            context.get_data(run_id, "hit_threshold"),
            "hit_merge_clusters hit_threshold input",
            THRESHOLD_HIT_DTYPE,
        )
        if len(hits) == 0:
            return np.zeros(0, dtype=HIT_MERGE_CLUSTERS_DTYPE)

        merge_gap_ns, max_total_width_ns, explicit_dt = _resolve_merge_config(context, self)
        pre_trigger_ps = get_pre_trigger_offset_ps(context)

        if merge_gap_ns <= 0:
            return _hits_to_cluster_rows_fast(hits)

        return _compute_cluster_rows(
            hits,
            merge_gap_ns=merge_gap_ns,
            max_total_width_ns=max_total_width_ns,
            explicit_dt=explicit_dt,
            plugin_name=self.provides,
            pre_trigger_ps=pre_trigger_ps,
        )


class HitMergedComponentsPlugin(Plugin):
    """Return flat component hit indices for each hit_merged cluster."""

    provides = "hit_merged_components"
    depends_on = ["hit_merge_clusters", "hit_merged"]
    description = "Return per-cluster component hit indices for hit_merged rows."
    version = "1.0.1"
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

        try:
            cluster_rows = context.get_data(run_id, "hit_merge_clusters")
            if cluster_rows is not None:
                cluster_rows = _materialize_array(
                    cluster_rows,
                    "hit_merged_components hit_merge_clusters input",
                    HIT_MERGE_CLUSTERS_DTYPE,
                )
        except (KeyError, FileNotFoundError):
            hits = _materialize_array(
                context.get_data(run_id, "hit_threshold"),
                "hit_merged_components hit_threshold input",
                THRESHOLD_HIT_DTYPE,
            )
            merge_plugin = context.get_plugin("hit_merged")
            merge_gap_ns, max_total_width_ns, explicit_dt = _resolve_merge_config(
                context, merge_plugin
            )
            cluster_rows = _compute_cluster_rows(
                hits,
                merge_gap_ns=merge_gap_ns,
                max_total_width_ns=max_total_width_ns,
                explicit_dt=explicit_dt,
                plugin_name="hit_merge_clusters",
                pre_trigger_ps=pre_trigger_ps,
            )
        if cluster_rows is None:
            hits = _materialize_array(
                context.get_data(run_id, "hit_threshold"),
                "hit_merged_components hit_threshold input",
                THRESHOLD_HIT_DTYPE,
            )
            merge_plugin = context.get_plugin("hit_merged")
            merge_gap_ns, max_total_width_ns, explicit_dt = _resolve_merge_config(
                context, merge_plugin
            )
            cluster_rows = _compute_cluster_rows(
                hits,
                merge_gap_ns=merge_gap_ns,
                max_total_width_ns=max_total_width_ns,
                explicit_dt=explicit_dt,
                plugin_name="hit_merge_clusters",
                pre_trigger_ps=pre_trigger_ps,
            )
        if not isinstance(cluster_rows, np.ndarray):
            raise ValueError(
                "hit_merged_components expects hit_merge_clusters and hit_merged structured arrays"
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
