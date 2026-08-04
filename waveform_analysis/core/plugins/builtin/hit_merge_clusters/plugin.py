"""HitMergeClustersPlugin 类实现 - 导出 hit merge 的 cluster 成员关系。"""

from typing import Any

import numpy as np

from waveform_analysis.core.plugins.builtin.hit.hit_finder import THRESHOLD_HIT_DTYPE
from waveform_analysis.core.plugins.builtin.hit_merged._compute import (
    HIT_MERGE_CLUSTERS_DTYPE,
    _compute_canonical_cluster_rows,
    _materialize_array,
)
from waveform_analysis.core.plugins.core.base import Plugin


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
