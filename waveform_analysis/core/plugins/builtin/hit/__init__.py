"""
Hit 插件模块 - Hit 检测与处理管道

本模块包含所有与 hit 检测、合并和分组相关的插件：
- hit_finder.py: Hit 检测插件（阈值检测）
- hit_merge.py: Hit 合并与簇检测插件
- hit_merged_features.py: Merged hit 特征计算插件
- hit_grouped.py: Hit 分组插件
- hit_threshold_numba.py: Numba 加速的阈值处理

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

__all__ = [
    # Hit 插件
    "ThresholdHitPlugin",
    "HitMergePlugin",
    "HitMergeClustersPlugin",
    "HitMergedComponentsPlugin",
    "HitMergedFeaturesPlugin",
    "HitGroupedPlugin",
    # 数据类型
    "THRESHOLD_HIT_DTYPE",
    "HIT_MERGED_DTYPE",
    "HIT_MERGE_CLUSTERS_DTYPE",
    "HIT_MERGED_COMPONENTS_DTYPE",
    "HIT_MERGED_FEATURES_DTYPE",
]
