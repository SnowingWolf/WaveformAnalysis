"""
Hit Merge Plugin - 合并临近 hit（同通道，允许跨波形/跨文件）
"""

from typing import Any

import numpy as np

from waveform_analysis.core.hardware.channel import iter_hardware_channel_groups
from waveform_analysis.core.plugins.builtin.cpu.hit_finder import THRESHOLD_HIT_DTYPE
from waveform_analysis.core.plugins.core.base import Option, Plugin


class HitMergePlugin(Plugin):
    """Merge nearby hits from hit_threshold within the same channel."""

    provides = "hit_merged"
    depends_on = ["hit_threshold"]
    description = "Merge nearby threshold hits per channel with time-gap and max-width constraints."
    version = "0.4.0"
    save_when = "always"
    output_dtype = THRESHOLD_HIT_DTYPE

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
        "sampling_interval_ns": Option(
            default=2.0,
            type=float,
            help="采样间隔（ns），用于样点边界与时间换算",
        ),
    }

    def compute(self, context: Any, run_id: str, **_kwargs) -> np.ndarray:
        hits = context.get_data(run_id, "hit_threshold")
        if not isinstance(hits, np.ndarray):
            raise ValueError("hit_merged expects hit_threshold as a single structured array")
        if len(hits) == 0:
            return np.zeros(0, dtype=THRESHOLD_HIT_DTYPE)

        merge_gap_ns = float(context.get_config(self, "merge_gap_ns"))
        max_total_width_ns = float(context.get_config(self, "max_total_width_ns"))
        sampling_interval_ns = float(context.get_config(self, "sampling_interval_ns"))

        dt_ps = sampling_interval_ns * 1e3
        if dt_ps <= 0:
            raise ValueError("sampling_interval_ns must be > 0")

        if merge_gap_ns <= 0:
            return np.array(hits, dtype=THRESHOLD_HIT_DTYPE)

        merge_gap_ps = merge_gap_ns * 1e3
        max_total_width_ps = max_total_width_ns * 1e3

        merged_rows: list[tuple] = []
        for _hw_channel, ch_hits in iter_hardware_channel_groups(hits):
            if len(ch_hits) == 0:
                continue

            enriched = self._build_enriched(ch_hits, dt_ps)
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

                if gap_ps <= merge_gap_ps and total_width_ps <= max_total_width_ps:
                    cluster.append(item)
                    cluster_end = next_end
                else:
                    merged_rows.append(
                        self._emit_cluster(cluster, cluster_start, cluster_end, dt_ps)
                    )
                    cluster = [item]
                    cluster_start = item["abs_start_ps"]
                    cluster_end = item["abs_end_ps"]

            merged_rows.append(self._emit_cluster(cluster, cluster_start, cluster_end, dt_ps))

        if merged_rows:
            return np.array(merged_rows, dtype=THRESHOLD_HIT_DTYPE)
        return np.zeros(0, dtype=THRESHOLD_HIT_DTYPE)

    def _build_enriched(self, hits: np.ndarray, dt_ps: float) -> list[dict[str, Any]]:
        def _pick(hit: np.void, *candidates: str) -> Any:
            for name in candidates:
                if name in hit.dtype.names:
                    return hit[name]
            raise KeyError(f"Missing fields {candidates} in HIT_DTYPE")

        enriched: list[dict[str, Any]] = []
        for hit in hits:
            timestamp = float(_pick(hit, "timestamp", "hit_timestamp_ps"))
            position = float(_pick(hit, "position", "hit_sample_idx"))
            edge_start = float(_pick(hit, "edge_start", "hit_left_sample_idx"))
            edge_end = float(_pick(hit, "edge_end", "hit_right_sample_idx"))
            abs_start_ps = timestamp + (edge_start - position) * dt_ps
            abs_end_ps = timestamp + (edge_end - position) * dt_ps
            enriched.append(
                {
                    "hit": hit,
                    "abs_start_ps": abs_start_ps,
                    "abs_end_ps": abs_end_ps,
                }
            )
        return enriched

    def _emit_cluster(
        self,
        cluster: list[dict[str, Any]],
        cluster_start_ps: float,
        cluster_end_ps: float,
        dt_ps: float,
    ) -> tuple:
        if len(cluster) == 1:
            h = cluster[0]["hit"]
            return (
                int(h["position"]),
                float(h["height"]),
                float(h["integral"]),
                float(h["edge_start"]),
                float(h["edge_end"]),
                float(h["width"]),
                int(h["timestamp"]),
                int(h["board"]) if "board" in h.dtype.names else 0,
                int(h["channel"]),
                int(h["record_id"]),
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
            int(anchor["timestamp"]),
            int(anchor["board"]) if "board" in anchor.dtype.names else 0,
            int(anchor["channel"]),
            int(anchor["record_id"]),
        )
