"""
Hit Merge Plugin - 合并临近 hit（同通道，允许跨波形/跨文件）
"""

from typing import Any

import numpy as np

from waveform_analysis.core.hardware.channel import group_indices_by_hardware_channel
from waveform_analysis.core.plugins.builtin.cpu._dt_compat import (
    require_dt_array,
    resolve_dt_config,
)
from waveform_analysis.core.plugins.builtin.cpu.hit_finder import THRESHOLD_HIT_DTYPE
from waveform_analysis.core.plugins.core.base import Option, Plugin

HIT_MERGED_DTYPE = np.dtype(
    THRESHOLD_HIT_DTYPE.descr
    + [
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


def _pick(hit: np.void, *candidates: str) -> Any:
    for name in candidates:
        if name in hit.dtype.names:
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
    enriched: list[dict[str, Any]] = []
    for hit, dt_ns, source_index in zip(hits, dt_values, source_indices, strict=False):
        timestamp = float(_pick(hit, "timestamp", "hit_timestamp_ps"))
        position = float(_pick(hit, "position", "hit_sample_idx"))
        edge_start = float(_pick(hit, "edge_start", "hit_left_sample_idx"))
        edge_end = float(_pick(hit, "edge_end", "hit_right_sample_idx"))
        dt_ps = float(int(dt_ns)) * 1e3
        abs_start_ps = timestamp + (edge_start - position) * dt_ps
        abs_end_ps = timestamp + (edge_end - position) * dt_ps
        enriched.append(
            {
                "hit": hit,
                "source_index": int(source_index),
                "abs_start_ps": abs_start_ps,
                "abs_end_ps": abs_end_ps,
                "dt_ns": int(dt_ns),
                "dt_ps": dt_ps,
            }
        )
    return enriched


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


def _resolve_cluster_sample_window(cluster: list[dict[str, Any]]) -> tuple[int, int, int, int]:
    record_ids = {int(item["hit"]["record_id"]) for item in cluster}
    if len(record_ids) != 1:
        return -1, -1, -1, -1

    required_fields = {
        "record_sample_start",
        "record_sample_end",
        "wave_pool_start",
        "wave_pool_end",
    }
    if not required_fields.issubset(set(cluster[0]["hit"].dtype.names or ())):
        return -1, -1, -1, -1

    record_sample_start = min(int(item["hit"]["record_sample_start"]) for item in cluster)
    record_sample_end = max(int(item["hit"]["record_sample_end"]) for item in cluster)
    wave_pool_start = min(int(item["hit"]["wave_pool_start"]) for item in cluster)
    wave_pool_end = max(int(item["hit"]["wave_pool_end"]) for item in cluster)
    return record_sample_start, record_sample_end, wave_pool_start, wave_pool_end


def _emit_cluster(
    cluster: list[dict[str, Any]],
    cluster_start_ps: float,
    cluster_end_ps: float,
    dt_ps: float,
    component_offset: int,
) -> tuple:
    component_count = len(cluster)
    record_sample_start, record_sample_end, wave_pool_start, wave_pool_end = (
        _resolve_cluster_sample_window(cluster)
    )

    if len(cluster) == 1:
        h = cluster[0]["hit"]
        return (
            int(h["position"]),
            float(h["height"]),
            float(h["integral"]),
            float(h["edge_start"]),
            float(h["edge_end"]),
            float(h["width"]),
            int(h["dt"]) if "dt" in h.dtype.names else int(cluster[0]["dt_ns"]),
            float(h["rise_time"]) if "rise_time" in h.dtype.names else 0.0,
            float(h["fall_time"]) if "fall_time" in h.dtype.names else 0.0,
            int(h["timestamp"]),
            int(h["board"]) if "board" in h.dtype.names else 0,
            int(h["channel"]),
            int(h["record_id"]),
            (
                int(h["record_sample_start"])
                if "record_sample_start" in h.dtype.names
                else record_sample_start
            ),
            (
                int(h["record_sample_end"])
                if "record_sample_end" in h.dtype.names
                else record_sample_end
            ),
            int(h["wave_pool_start"]) if "wave_pool_start" in h.dtype.names else wave_pool_start,
            int(h["wave_pool_end"]) if "wave_pool_end" in h.dtype.names else wave_pool_end,
            component_offset,
            component_count,
        )

    heights = np.array([float(x["hit"]["height"]) for x in cluster], dtype=np.float64)
    max_h = float(np.max(heights))
    candidates = [i for i, x in enumerate(cluster) if float(x["hit"]["height"]) == max_h]
    if len(candidates) == 1:
        anchor_idx = candidates[0]
    else:
        anchor_idx = min(
            candidates,
            key=lambda i: int(cluster[i]["hit"]["timestamp"]),
        )

    anchor = cluster[anchor_idx]["hit"]
    anchor_pos = float(anchor["position"])
    anchor_ts = float(anchor["timestamp"])

    merged_edge_start = anchor_pos + (cluster_start_ps - anchor_ts) / dt_ps
    merged_edge_end = anchor_pos + (cluster_end_ps - anchor_ts) / dt_ps
    merged_width = float(max(merged_edge_end - merged_edge_start, 0.0))
    merged_integral = float(np.sum([float(x["hit"]["integral"]) for x in cluster]))

    return (
        int(anchor["position"]),
        max_h,
        merged_integral,
        float(merged_edge_start),
        float(merged_edge_end),
        merged_width,
        int(anchor["dt"]) if "dt" in anchor.dtype.names else int(cluster[anchor_idx]["dt_ns"]),
        float(anchor["rise_time"]) if "rise_time" in anchor.dtype.names else 0.0,
        float(anchor["fall_time"]) if "fall_time" in anchor.dtype.names else 0.0,
        int(anchor["timestamp"]),
        int(anchor["board"]) if "board" in anchor.dtype.names else 0,
        int(anchor["channel"]),
        int(anchor["record_id"]),
        record_sample_start,
        record_sample_end,
        wave_pool_start,
        wave_pool_end,
        component_offset,
        component_count,
    )


class HitMergePlugin(Plugin):
    """Merge nearby hits from hit_threshold within the same channel."""

    provides = "hit_merged"
    depends_on = ["hit_threshold"]
    description = "Merge nearby threshold hits per channel with time-gap and max-width constraints."
    version = "0.6.0"
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
        hits = context.get_data(run_id, "hit_threshold")
        if not isinstance(hits, np.ndarray):
            raise ValueError("hit_merged expects hit_threshold as a single structured array")
        if len(hits) == 0:
            return np.zeros(0, dtype=HIT_MERGED_DTYPE)

        merge_gap_ns, max_total_width_ns, explicit_dt = _resolve_merge_config(context, self)
        clusters = _build_merged_clusters(
            hits,
            merge_gap_ns=merge_gap_ns,
            max_total_width_ns=max_total_width_ns,
            explicit_dt=explicit_dt,
            plugin_name=self.provides,
        )

        merged_rows: list[tuple] = []
        component_offset = 0
        for cluster in clusters:
            cluster_start = cluster[0]["abs_start_ps"]
            cluster_end = max(item["abs_end_ps"] for item in cluster)
            merged_rows.append(
                _emit_cluster(
                    cluster,
                    cluster_start_ps=cluster_start,
                    cluster_end_ps=cluster_end,
                    dt_ps=cluster[0]["dt_ps"],
                    component_offset=component_offset,
                )
            )
            component_offset += len(cluster)

        if merged_rows:
            return np.array(merged_rows, dtype=HIT_MERGED_DTYPE)
        return np.zeros(0, dtype=HIT_MERGED_DTYPE)


class HitMergedComponentsPlugin(Plugin):
    """Return flat component hit indices for each hit_merged cluster."""

    provides = "hit_merged_components"
    depends_on = ["hit_threshold", "hit_merged"]
    description = "Return per-cluster component hit indices for hit_merged rows."
    version = "0.1.0"
    save_when = "always"
    output_dtype = HIT_MERGED_COMPONENTS_DTYPE

    def compute(self, context: Any, run_id: str, **_kwargs) -> np.ndarray:
        hits = context.get_data(run_id, "hit_threshold")
        merged = context.get_data(run_id, "hit_merged")
        if not isinstance(hits, np.ndarray) or not isinstance(merged, np.ndarray):
            raise ValueError(
                "hit_merged_components expects hit_threshold and hit_merged structured arrays"
            )
        if len(hits) == 0 or len(merged) == 0:
            return np.zeros(0, dtype=HIT_MERGED_COMPONENTS_DTYPE)

        merge_plugin = context.get_plugin("hit_merged")
        merge_gap_ns, max_total_width_ns, explicit_dt = _resolve_merge_config(context, merge_plugin)
        clusters = _build_merged_clusters(
            hits,
            merge_gap_ns=merge_gap_ns,
            max_total_width_ns=max_total_width_ns,
            explicit_dt=explicit_dt,
            plugin_name="hit_merged",
        )
        if len(clusters) != len(merged):
            raise ValueError(
                "hit_merged_components cluster count does not match hit_merged rows: "
                f"clusters={len(clusters)}, hit_merged={len(merged)}"
            )

        component_rows: list[tuple[int, int]] = []
        expected_offset = 0
        for merged_idx, cluster in enumerate(clusters):
            if (
                "component_offset" in merged.dtype.names
                and int(merged[merged_idx]["component_offset"]) != expected_offset
            ):
                raise ValueError(
                    f"hit_merged[{merged_idx}] component_offset mismatch: "
                    f"expected {expected_offset}, got {int(merged[merged_idx]['component_offset'])}"
                )
            if "component_count" in merged.dtype.names and int(
                merged[merged_idx]["component_count"]
            ) != len(cluster):
                raise ValueError(
                    f"hit_merged[{merged_idx}] component_count mismatch: "
                    f"expected {len(cluster)}, got {int(merged[merged_idx]['component_count'])}"
                )
            for item in cluster:
                component_rows.append((merged_idx, int(item["source_index"])))
            expected_offset += len(cluster)

        if component_rows:
            return np.array(component_rows, dtype=HIT_MERGED_COMPONENTS_DTYPE)
        return np.zeros(0, dtype=HIT_MERGED_COMPONENTS_DTYPE)


__all__ = [
    "HIT_MERGED_COMPONENTS_DTYPE",
    "HIT_MERGED_DTYPE",
    "HitMergePlugin",
    "HitMergedComponentsPlugin",
]
