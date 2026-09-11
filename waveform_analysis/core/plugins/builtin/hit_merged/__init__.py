"""hit_merged bundle - provides 'hit_merged'。

本 bundle 是 hit merge 家族的算法属主：共享计算（dtype 常量 + 集群合并）位于 ``_compute``，
兄弟 bundle ``hit_merge_clusters`` / ``hit_merged_components`` 单向依赖本模块。
"""

from waveform_analysis.core.plugins.builtin.hit_merged._compute import HIT_MERGED_DTYPE
from waveform_analysis.core.plugins.builtin.hit_merged.plugin import HitMergePlugin

__all__ = ["HitMergePlugin", "HIT_MERGED_DTYPE"]
