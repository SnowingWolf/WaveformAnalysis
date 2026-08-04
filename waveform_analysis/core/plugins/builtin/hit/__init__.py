"""
Hit 插件模块 - Hit 检测与处理管道

本模块是 hit 家族的属主 bundle（provides='hit'，实现位于 plugin.py），
同时保留对兄弟 hit 插件的兼容转发：
- plugin.py: Hit 检测插件（HitFinderPlugin，scipy 寻峰）
- hit_finder.py: 阈值 hit 兼容插件（ThresholdHitPlugin，已迁至 builtin.hit_threshold）
- hit_merge.py: Hit 合并与簇检测插件（已迁至 builtin.hit_merged 等）
- hit_merged_features.py: Merged hit 特征计算插件（已迁至 builtin.hit_merged_features）
- hit_grouped.py: Hit 分组插件（已迁至 builtin.hit_grouped）
- hit_threshold_numba.py: Numba 加速的阈值处理（已迁至 builtin.hit_threshold._compute）

**功能域**: Hit Detection & Processing
"""

from .hit_finder import THRESHOLD_HIT_DTYPE, ThresholdHitPlugin
from .hit_grouped import HitGroupedPlugin
from .hit_merge import (
    HIT_MERGE_CLUSTERS_DTYPE,
    HIT_MERGED_COMPONENTS_DTYPE,
    HIT_MERGED_DTYPE,
    HitMergeClustersPlugin,
    HitMergedComponentsPlugin,
    HitMergePlugin,
)
from .hit_merged_features import HIT_MERGED_FEATURES_DTYPE, HitMergedFeaturesPlugin
from .plugin import HIT_DTYPE, HitFinderPlugin

__all__ = [
    # Hit 插件
    "HitFinderPlugin",
    "ThresholdHitPlugin",
    "HitMergePlugin",
    "HitMergeClustersPlugin",
    "HitMergedComponentsPlugin",
    "HitMergedFeaturesPlugin",
    "HitGroupedPlugin",
    # 数据类型
    "HIT_DTYPE",
    "THRESHOLD_HIT_DTYPE",
    "HIT_MERGED_DTYPE",
    "HIT_MERGE_CLUSTERS_DTYPE",
    "HIT_MERGED_COMPONENTS_DTYPE",
    "HIT_MERGED_FEATURES_DTYPE",
]
