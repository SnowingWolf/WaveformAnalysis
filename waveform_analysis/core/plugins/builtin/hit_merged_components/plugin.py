"""HitMergedComponentsPlugin 类实现 - 展开每个 hit_merged cluster 的 component hit 索引。"""

from typing import Any

import numpy as np

from waveform_analysis.core.plugins.builtin.hit_merged._compute import (
    HIT_MERGED_COMPONENTS_DTYPE,
    HIT_MERGED_DTYPE,
    _cluster_bounds,
    _cluster_rows_to_components,
    _compute_canonical_cluster_rows,
    _materialize_array,
)
from waveform_analysis.core.plugins.builtin.hit_threshold import THRESHOLD_HIT_DTYPE
from waveform_analysis.core.plugins.core.base import Option, Plugin


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
