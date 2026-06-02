"""Hit Merge Plugin - 合并临近 hit（同通道，允许跨波形/跨文件）"""

from collections.abc import Iterator
from typing import Any

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

    if arrays:
        return np.concatenate(arrays)
    return np.zeros(0, dtype=output_dtype)


# Numba-accelerated cluster merging
if _NUMBA_AVAILABLE:

    @njit(cache=True, nogil=True)  # type: ignore[misc]
    def _merge_clusters_numba(
        abs_starts: np.ndarray,
        abs_ends: np.ndarray,
        dt_ps: np.ndarray,
        merge_gap_ps: float,
        max_total_width_ps: float,
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
        cluster_start_ps = float(abs_starts[0])
        cluster_end_ps = float(abs_ends[0])
        cluster_dt = float(dt_ps[0])

        for i in range(1, n):
            gap = float(abs_starts[i]) - cluster_end_ps
            next_end = max(cluster_end_ps, float(abs_ends[i]))
            total_width = next_end - cluster_start_ps
            same_dt = abs(float(dt_ps[i]) - cluster_dt) < 1e-3

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
                cluster_start_ps = float(abs_starts[i])
                cluster_end_ps = float(abs_ends[i])
                cluster_dt = float(dt_ps[i])

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
        merge_gap_ps: float,
        max_total_width_ps: float,
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


def _build_enriched_hits(
    hits: np.ndarray,
    dt_values: np.ndarray,
    source_indices: np.ndarray,
) -> list[dict[str, Any]]:
    """Build enriched hits with absolute time coordinates.

    Optimized version: vectorized field extraction replaces hot _pick calls.
    """
    n = len(hits)
    if n == 0:
        return []

    # Vectorized field extraction (replaces 4*n calls to _pick)
    # This alone saves ~0.4 seconds for 10k hits
    timestamps = _get_field_safe(hits, "timestamp", "hit_timestamp_ps").astype(np.float64)
    positions = _get_field_safe(hits, "position", "hit_sample_idx").astype(np.float64)
    edge_starts = _get_field_safe(hits, "edge_start", "sample_start", "hit_left_sample_idx").astype(
        np.float64
    )
    edge_ends = _get_field_safe(hits, "edge_end", "sample_end", "hit_right_sample_idx").astype(
        np.float64
    )

    # Vectorized computation
    dt_ps = dt_values.astype(np.float64) * 1e3
    abs_start_ps = timestamps + (edge_starts - positions) * dt_ps
    abs_end_ps = timestamps + (edge_ends - positions) * dt_ps

    # Build dict list (kept for compatibility, but much faster now)
    enriched: list[dict[str, Any]] = []
    for i in range(n):
        enriched.append(
            {
                "hit": hits[i],
                "source_index": int(source_indices[i]),
                "abs_start_ps": float(abs_start_ps[i]),
                "abs_end_ps": float(abs_end_ps[i]),
                "dt_ns": int(dt_values[i]),
                "dt_ps": float(dt_ps[i]),
            }
        )
    return enriched


def _resolve_cluster_sample_window(cluster: list[dict[str, Any]]) -> tuple[int, int]:
    record_ids = {int(item["hit"]["record_id"]) for item in cluster}
    if len(record_ids) != 1:
        return -1, -1

    names = set(cluster[0]["hit"].dtype.names or ())
    if {"sample_start", "sample_end"}.issubset(names):
        start_name = "sample_start"
        end_name = "sample_end"
    elif {"edge_start", "edge_end"}.issubset(names):
        start_name = "edge_start"
        end_name = "edge_end"
    else:
        return -1, -1

    sample_start = min(int(item["hit"][start_name]) for item in cluster)
    sample_end = max(int(item["hit"][end_name]) for item in cluster)
    return sample_start, sample_end


def _build_merged_clusters(
    hits: np.ndarray,
    merge_gap_ns: float,
    max_total_width_ns: float,
    explicit_dt: int | None,
    plugin_name: str,
) -> list[list[dict[str, Any]]]:
    if len(hits) == 0:
        return []

    if "board" in hits.dtype.names:
        boards = hits["board"]
    else:
        boards = np.zeros(len(hits), dtype=np.int16)
    if "channel" not in hits.dtype.names:
        raise ValueError(f"{plugin_name} requires hit data with a 'channel' field")
    channels = hits["channel"]

    clusters_out: list[list[dict[str, Any]]] = []
    merge_gap_ps = merge_gap_ns * 1e3
    max_total_width_ps = max_total_width_ns * 1e3

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
        enriched = _build_enriched_hits(ch_hits, channel_dt, indices.astype(np.int64, copy=False))
        order = np.argsort(
            np.array([x["abs_start_ps"] for x in enriched], dtype=np.float64),
            kind="mergesort",
        )
        enriched = [enriched[i] for i in order]

        # Try Numba-accelerated clustering if available
        # Threshold increased from 50 to 200 to reduce JIT overhead on small datasets
        if _NUMBA_AVAILABLE and len(enriched) > 200:
            # Extract arrays for Numba
            abs_starts = np.array([x["abs_start_ps"] for x in enriched], dtype=np.float32)
            abs_ends = np.array([x["abs_end_ps"] for x in enriched], dtype=np.float32)
            dts = np.array([x["dt_ps"] for x in enriched], dtype=np.float32)

            cluster_starts, cluster_ends = _merge_clusters_numba(
                abs_starts, abs_ends, dts, merge_gap_ps, max_total_width_ps
            )

            # Build cluster list from indices
            for start, end in zip(cluster_starts, cluster_ends, strict=False):
                clusters_out.append(enriched[int(start) : int(end)])
        else:
            # Fallback: Python loop (for small datasets or when Numba unavailable)
            cluster: list[dict[str, Any]] = [enriched[0]]
            cluster_start = enriched[0]["abs_start_ps"]
            cluster_end = enriched[0]["abs_end_ps"]

            for item in enriched[1:]:
                gap_ps = item["abs_start_ps"] - cluster_end
                next_end = max(cluster_end, item["abs_end_ps"])
                total_width_ps = next_end - cluster_start
                same_dt = item["dt_ps"] == cluster[-1]["dt_ps"]

                if (
                    merge_gap_ns > 0
                    and same_dt
                    and gap_ps <= merge_gap_ps
                    and total_width_ps <= max_total_width_ps
                ):
                    cluster.append(item)
                    cluster_end = next_end
                else:
                    clusters_out.append(cluster)
                    cluster = [item]
                    cluster_start = item["abs_start_ps"]
                    cluster_end = item["abs_end_ps"]

            clusters_out.append(cluster)

    return clusters_out


def _build_cluster_rows(clusters: list[list[dict[str, Any]]]) -> np.ndarray:
    cluster_rows: list[tuple[int, int]] = []
    for cluster_index, cluster in enumerate(clusters):
        for item in cluster:
            cluster_rows.append((cluster_index, int(item["source_index"])))
    if cluster_rows:
        return np.array(cluster_rows, dtype=HIT_MERGE_CLUSTERS_DTYPE)
    return np.zeros(0, dtype=HIT_MERGE_CLUSTERS_DTYPE)


def _build_enriched_lookup(
    hits: np.ndarray,
    explicit_dt: int | None,
    plugin_name: str,
) -> dict[int, dict[str, Any]]:
    if len(hits) == 0:
        return {}

    if "board" in hits.dtype.names:
        boards = hits["board"]
    else:
        boards = np.zeros(len(hits), dtype=np.int16)
    channels = hits["channel"]

    enriched_lookup: dict[int, dict[str, Any]] = {}
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
        enriched = _build_enriched_hits(ch_hits, channel_dt, indices.astype(np.int64, copy=False))
        for item in enriched:
            enriched_lookup[int(item["source_index"])] = item
    return enriched_lookup


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


def _compute_cluster_rows(
    hits: np.ndarray,
    merge_gap_ns: float,
    max_total_width_ns: float,
    explicit_dt: int | None,
    plugin_name: str,
) -> np.ndarray:
    clusters = _build_merged_clusters(
        hits,
        merge_gap_ns=merge_gap_ns,
        max_total_width_ns=max_total_width_ns,
        explicit_dt=explicit_dt,
        plugin_name=plugin_name,
    )
    return _build_cluster_rows(clusters)


def _emit_cluster(
    cluster: list[dict[str, Any]],
    cluster_start_ps: float,
    cluster_end_ps: float,
    dt_ps: float,
    component_offset: int,
) -> tuple:
    """Emit a merged hit row from a cluster.

    Optimized: reduced _pick calls by using direct field access where possible.
    """
    component_count = len(cluster)
    sample_start_window, sample_end_window = _resolve_cluster_sample_window(cluster)

    if len(cluster) == 1:
        h = cluster[0]["hit"]
        # Use direct field access where safe, fallback to _pick
        sample_start = int(_get_field_safe(np.array([h]), "sample_start", "edge_start")[0])
        sample_end = int(_get_field_safe(np.array([h]), "sample_end", "edge_end")[0])

        return (
            int(h["position"]),
            sample_start,
            sample_end,
            float(h["width"]),
            int(h["dt"]) if "dt" in h.dtype.names else int(cluster[0]["dt_ns"]),
            int(h["timestamp"]),
            int(h["board"]) if "board" in h.dtype.names else 0,
            int(h["channel"]),
            int(h["record_id"]),
            component_offset,
            component_count,
        )

    # Vectorized anchor finding
    cluster_mid_ps = (cluster_start_ps + cluster_end_ps) * 0.5
    abs_starts = np.array([c["abs_start_ps"] for c in cluster], dtype=np.float32)
    abs_ends = np.array([c["abs_end_ps"] for c in cluster], dtype=np.float32)
    mids = (abs_starts + abs_ends) * 0.5
    anchor_idx = int(np.argmin(np.abs(mids - cluster_mid_ps)))
    anchor = cluster[anchor_idx]["hit"]

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
        int(anchor["dt"]) if "dt" in anchor.dtype.names else int(cluster[anchor_idx]["dt_ns"]),
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
    version = "1.1.0"
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
        hits = _materialize_array(
            context.get_data(run_id, "hit_threshold"),
            "hit_merged hit_threshold input",
            THRESHOLD_HIT_DTYPE,
        )
        if len(hits) == 0:
            return np.zeros(0, dtype=HIT_MERGED_DTYPE)

        merge_gap_ns, max_total_width_ns, explicit_dt = _resolve_merge_config(context, self)
        try:
            cluster_rows = context.get_data(run_id, "hit_merge_clusters")
            if cluster_rows is not None:
                cluster_rows = _materialize_array(
                    cluster_rows,
                    "hit_merged hit_merge_clusters input",
                    HIT_MERGE_CLUSTERS_DTYPE,
                )
        except Exception:
            cluster_rows = _compute_cluster_rows(
                hits,
                merge_gap_ns=merge_gap_ns,
                max_total_width_ns=max_total_width_ns,
                explicit_dt=explicit_dt,
                plugin_name="hit_merge_clusters",
            )
        if cluster_rows is None:
            cluster_rows = _compute_cluster_rows(
                hits,
                merge_gap_ns=merge_gap_ns,
                max_total_width_ns=max_total_width_ns,
                explicit_dt=explicit_dt,
                plugin_name="hit_merge_clusters",
            )
        if not isinstance(cluster_rows, np.ndarray):
            raise ValueError("hit_merged expects hit_merge_clusters as a structured array")

        enriched_lookup = _build_enriched_lookup(
            hits, explicit_dt=explicit_dt, plugin_name=self.provides
        )

        merged_rows: list[tuple] = []
        for cluster_index, start, end in _cluster_bounds(cluster_rows):
            hit_indices = np.asarray(cluster_rows["hit_index"][start:end], dtype=np.int64)
            cluster = [enriched_lookup[int(hit_idx)] for hit_idx in hit_indices]
            if len(cluster) == 0:
                continue
            cluster_start = cluster[0]["abs_start_ps"]
            cluster_end = max(item["abs_end_ps"] for item in cluster)
            merged_rows.append(
                _emit_cluster(
                    cluster,
                    cluster_start_ps=cluster_start,
                    cluster_end_ps=cluster_end,
                    dt_ps=cluster[0]["dt_ps"],
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
    version = "1.0.0"
    save_when = "always"
    output_dtype = HIT_MERGE_CLUSTERS_DTYPE

    options = HitMergePlugin.options

    def compute(self, context: Any, run_id: str, **_kwargs) -> np.ndarray:
        hits = _materialize_array(
            context.get_data(run_id, "hit_threshold"),
            "hit_merge_clusters hit_threshold input",
            THRESHOLD_HIT_DTYPE,
        )
        if len(hits) == 0:
            return np.zeros(0, dtype=HIT_MERGE_CLUSTERS_DTYPE)

        merge_gap_ns, max_total_width_ns, explicit_dt = _resolve_merge_config(context, self)
        clusters = _build_merged_clusters(
            hits,
            merge_gap_ns=merge_gap_ns,
            max_total_width_ns=max_total_width_ns,
            explicit_dt=explicit_dt,
            plugin_name=self.provides,
        )
        return _build_cluster_rows(clusters)


class HitMergedComponentsPlugin(Plugin):
    """Return flat component hit indices for each hit_merged cluster."""

    provides = "hit_merged_components"
    depends_on = ["hit_merge_clusters", "hit_merged"]
    description = "Return per-cluster component hit indices for hit_merged rows."
    version = "1.0.0"
    save_when = "always"
    output_dtype = HIT_MERGED_COMPONENTS_DTYPE

    def compute(self, context: Any, run_id: str, **_kwargs) -> np.ndarray:
        merged = _materialize_array(
            context.get_data(run_id, "hit_merged"),
            "hit_merged_components hit_merged input",
            HIT_MERGED_DTYPE,
        )
        if len(merged) == 0:
            return np.zeros(0, dtype=HIT_MERGED_COMPONENTS_DTYPE)

        try:
            cluster_rows = context.get_data(run_id, "hit_merge_clusters")
            if cluster_rows is not None:
                cluster_rows = _materialize_array(
                    cluster_rows,
                    "hit_merged_components hit_merge_clusters input",
                    HIT_MERGE_CLUSTERS_DTYPE,
                )
        except Exception:
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
            )
        if not isinstance(cluster_rows, np.ndarray):
            raise ValueError(
                "hit_merged_components expects hit_merge_clusters and hit_merged structured arrays"
            )
        if len(cluster_rows) == 0:
            return np.zeros(0, dtype=HIT_MERGED_COMPONENTS_DTYPE)

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
