"""Hit Merge - 兼容 shim。

``HitMergePlugin``、``HitMergeClustersPlugin``、``HitMergedComponentsPlugin`` 与共享集群计算
已分别迁至 :mod:`waveform_analysis.core.plugins.builtin.hit_merged`（算法属主，共享计算位于其
``_compute``）以及兄弟 bundle ``hit_merge_clusters`` / ``hit_merged_components``。
本模块仅向后兼容转发全部符号。
"""

from waveform_analysis.core.plugins.builtin.hit_merge_clusters import (
    HitMergeClustersPlugin,
)
from waveform_analysis.core.plugins.builtin.hit_merged import (
    HIT_MERGED_DTYPE,
    HitMergePlugin,
)
from waveform_analysis.core.plugins.builtin.hit_merged._compute import (
    HIT_MERGE_CLUSTERS_DTYPE,
    HIT_MERGED_COMPONENTS_DTYPE,
)
from waveform_analysis.core.plugins.builtin.hit_merged_components import (
    HitMergedComponentsPlugin,
)

__all__ = [
    "HIT_MERGE_CLUSTERS_DTYPE",
    "HIT_MERGED_COMPONENTS_DTYPE",
    "HIT_MERGED_DTYPE",
    "HitMergeClustersPlugin",
    "HitMergePlugin",
    "HitMergedComponentsPlugin",
]
