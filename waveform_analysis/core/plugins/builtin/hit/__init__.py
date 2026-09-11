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

from waveform_analysis._lazy_exports import LazyExport as _LazyExport
from waveform_analysis._lazy_exports import lazy_dir as _lazy_dir
from waveform_analysis._lazy_exports import (
    resolve_lazy_attribute as _resolve_lazy_attribute,
)

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


_BUILTIN = "waveform_analysis.core.plugins.builtin"
_LAZY_EXPORTS: dict[str, _LazyExport] = {
    "HitFinderPlugin": (f"{_BUILTIN}.hit.plugin", "HitFinderPlugin"),
    "ThresholdHitPlugin": (
        f"{_BUILTIN}.hit_threshold",
        "ThresholdHitPlugin",
    ),
    "HitMergePlugin": (f"{_BUILTIN}.hit_merged", "HitMergePlugin"),
    "HitMergeClustersPlugin": (
        f"{_BUILTIN}.hit_merge_clusters",
        "HitMergeClustersPlugin",
    ),
    "HitMergedComponentsPlugin": (
        f"{_BUILTIN}.hit_merged_components",
        "HitMergedComponentsPlugin",
    ),
    "HitMergedFeaturesPlugin": (
        f"{_BUILTIN}.hit_merged_features",
        "HitMergedFeaturesPlugin",
    ),
    "HitGroupedPlugin": (f"{_BUILTIN}.hit_grouped", "HitGroupedPlugin"),
    "HIT_DTYPE": (f"{_BUILTIN}.hit.plugin", "HIT_DTYPE"),
    "THRESHOLD_HIT_DTYPE": (
        f"{_BUILTIN}.hit_threshold",
        "THRESHOLD_HIT_DTYPE",
    ),
    "HIT_MERGED_DTYPE": (f"{_BUILTIN}.hit_merged", "HIT_MERGED_DTYPE"),
    "HIT_MERGE_CLUSTERS_DTYPE": (
        f"{_BUILTIN}.hit_merge_clusters",
        "HIT_MERGE_CLUSTERS_DTYPE",
    ),
    "HIT_MERGED_COMPONENTS_DTYPE": (
        f"{_BUILTIN}.hit_merged_components",
        "HIT_MERGED_COMPONENTS_DTYPE",
    ),
    "HIT_MERGED_FEATURES_DTYPE": (
        f"{_BUILTIN}.hit_merged_features",
        "HIT_MERGED_FEATURES_DTYPE",
    ),
    # Keep the legacy child shims visible and directly importable.
    "hit_finder": (f"{__name__}.hit_finder", None),
    "hit_grouped": (f"{__name__}.hit_grouped", None),
    "hit_merge": (f"{__name__}.hit_merge", None),
    "hit_merged_features": (f"{__name__}.hit_merged_features", None),
    "plugin": (f"{__name__}.plugin", None),
}

_LAZY_ATTRS = _LAZY_EXPORTS


def __getattr__(name: str):
    return _resolve_lazy_attribute(name, _LAZY_EXPORTS, globals())


def __dir__():
    return _lazy_dir(globals(), _LAZY_EXPORTS, __all__)
