"""hit_merge_clusters bundle - provides 'hit_merge_clusters'。

共享计算来自属主 bundle ``hit_merged``（_compute）。本 bundle 仅导出 HitMergeClustersPlugin。
"""

from waveform_analysis.core.plugins.builtin.hit_merge_clusters.plugin import (
    HitMergeClustersPlugin,
)
from waveform_analysis.core.plugins.builtin.hit_merged._compute import (
    HIT_MERGE_CLUSTERS_DTYPE,
)

__all__ = ["HitMergeClustersPlugin", "HIT_MERGE_CLUSTERS_DTYPE"]
