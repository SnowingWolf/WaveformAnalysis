"""
插件 shim 路径兼容性测试。

验证迁移到 per-plugin bundle 后，旧 import 路径（``builtin.hit.*`` / ``builtin.cpu.*`` 等）
与新 bundle 路径（``builtin.<provides>``）解析到**同一类对象**。

每迁移一个插件，在此追加一条身份断言。
"""

import pytest

pytestmark = pytest.mark.contract


def test_hit_merged_old_path_is_new_bundle():
    """hit_merged 迁移后，旧深导入与新 bundle 路径指向同一 HitMergePlugin。"""
    from waveform_analysis.core.plugins.builtin.hit.hit_merge import (
        HIT_MERGED_DTYPE as OldDT,
    )
    from waveform_analysis.core.plugins.builtin.hit.hit_merge import (
        HitMergePlugin as Old,
    )
    from waveform_analysis.core.plugins.builtin.hit_merged import (
        HIT_MERGED_DTYPE as NewDT,
    )
    from waveform_analysis.core.plugins.builtin.hit_merged import (
        HitMergePlugin as New,
    )

    assert Old is New
    assert OldDT is NewDT


def test_hit_merge_clusters_old_path_is_new_bundle():
    """hit_merge_clusters 迁移后，旧深导入与新 bundle 路径指向同一 HitMergeClustersPlugin。"""
    from waveform_analysis.core.plugins.builtin.hit.hit_merge import (
        HIT_MERGE_CLUSTERS_DTYPE as OldDT,
    )
    from waveform_analysis.core.plugins.builtin.hit.hit_merge import (
        HitMergeClustersPlugin as Old,
    )
    from waveform_analysis.core.plugins.builtin.hit_merge_clusters import (
        HIT_MERGE_CLUSTERS_DTYPE as NewDT,
    )
    from waveform_analysis.core.plugins.builtin.hit_merge_clusters import (
        HitMergeClustersPlugin as New,
    )

    assert Old is New
    assert OldDT is NewDT


def test_hit_merged_components_old_path_is_new_bundle():
    """hit_merged_components 迁移后，旧深导入与新 bundle 路径指向同一 HitMergedComponentsPlugin。"""
    from waveform_analysis.core.plugins.builtin.hit.hit_merge import (
        HIT_MERGED_COMPONENTS_DTYPE as OldDT,
    )
    from waveform_analysis.core.plugins.builtin.hit.hit_merge import (
        HitMergedComponentsPlugin as Old,
    )
    from waveform_analysis.core.plugins.builtin.hit_merged_components import (
        HIT_MERGED_COMPONENTS_DTYPE as NewDT,
    )
    from waveform_analysis.core.plugins.builtin.hit_merged_components import (
        HitMergedComponentsPlugin as New,
    )

    assert Old is New
    assert OldDT is NewDT


def test_hit_merged_plugin_module_is_bundle():
    """HitMergePlugin 的 __module__ 应指向 bundle 内 plugin.py。"""
    from waveform_analysis.core.plugins.builtin.hit_merged import HitMergePlugin

    assert HitMergePlugin.__module__ == ("waveform_analysis.core.plugins.builtin.hit_merged.plugin")


def test_peaklet_old_paths_resolve_to_bundles():
    """peaklet 家族迁移后，旧 peaks.* 路径与新 bundle 路径指向同一类对象。"""
    import importlib

    from waveform_analysis.core.plugins.builtin import peaks as peaks_pkg

    pairs = [
        ("PeakletPlugin", "peaklets"),
        ("PeakletComponentsPlugin", "peaklet_components"),
        ("PeakletWaveformPlugin", "peaklet_waveforms"),
        ("PeakletWaveformPoolPlugin", "peaklet_waveform_pool"),
        ("PeakletFeaturesPlugin", "peaklet_features"),
        ("PeakletChannelsPlugin", "peaklet_channels"),
        ("PeaksPlugin", "peaks"),
    ]
    for class_name, bundle in pairs:
        old = getattr(peaks_pkg, class_name)
        new = getattr(
            importlib.import_module(f"waveform_analysis.core.plugins.builtin.{bundle}"), class_name
        )
        assert old is new, f"{class_name}: peaks.* 与 {bundle} bundle 不是同一对象"


def test_peaklet_dtypes_resolve_from_bundles():
    """peaklet 家族 dtype 常量可从新 bundle/_compute 路径解析。"""
    from waveform_analysis.core.plugins.builtin import cpu
    from waveform_analysis.core.plugins.builtin.peaklets._compute import (
        PEAKLET_COMPONENTS_DTYPE,
        PEAKLET_DTYPE,
        PEAKLET_FEATURES_DTYPE,
        PEAKLET_WAVEFORMS_DTYPE,
        PEAKS_DTYPE,
    )

    assert cpu.PEAKLET_DTYPE is PEAKLET_DTYPE
    assert cpu.PEAKLET_COMPONENTS_DTYPE is PEAKLET_COMPONENTS_DTYPE
    assert cpu.PEAKLET_WAVEFORMS_DTYPE is PEAKLET_WAVEFORMS_DTYPE
    assert cpu.PEAKLET_FEATURES_DTYPE is PEAKLET_FEATURES_DTYPE
    assert cpu.PEAKS_DTYPE is PEAKS_DTYPE


def test_hit_old_path_is_new_bundle():
    """hit 迁移后，旧 cpu.peak_finding 深导入与新 hit bundle 指向同一 HitFinderPlugin。"""
    from waveform_analysis.core.plugins.builtin.cpu.peak_finding import (
        HIT_DTYPE as OldDT,
    )
    from waveform_analysis.core.plugins.builtin.cpu.peak_finding import (
        HitFinderPlugin as Old,
    )
    from waveform_analysis.core.plugins.builtin.hit import HIT_DTYPE as NewDT
    from waveform_analysis.core.plugins.builtin.hit import HitFinderPlugin as New

    assert Old is New
    assert OldDT is NewDT


def test_hit_threshold_old_path_is_new_bundle():
    """hit_threshold 迁移后，旧 hit.hit_finder 深导入与新 hit_threshold bundle 指向同一 ThresholdHitPlugin。"""
    from waveform_analysis.core.plugins.builtin.hit.hit_finder import (
        THRESHOLD_HIT_DTYPE as OldDT,
    )
    from waveform_analysis.core.plugins.builtin.hit.hit_finder import (
        ThresholdHitPlugin as Old,
    )
    from waveform_analysis.core.plugins.builtin.hit_threshold import (
        THRESHOLD_HIT_DTYPE as NewDT,
    )
    from waveform_analysis.core.plugins.builtin.hit_threshold import (
        ThresholdHitPlugin as New,
    )

    assert Old is New
    assert OldDT is NewDT


def test_hit_threshold_numba_old_path_is_new_compute():
    """hit_threshold_numba 迁移后，旧 hit.hit_threshold_numba 与新 hit_threshold._compute 指向同一内核。"""
    from waveform_analysis.core.plugins.builtin.hit.hit_threshold_numba import (
        count_ragged_hits as Old,
    )
    from waveform_analysis.core.plugins.builtin.hit_threshold._compute import (
        count_ragged_hits as New,
    )

    assert Old is New


def test_hit_grouped_old_path_is_new_bundle():
    """hit_grouped 迁移后，旧 hit.hit_grouped 深导入与新 hit_grouped bundle 指向同一 HitGroupedPlugin。"""
    from waveform_analysis.core.plugins.builtin.hit.hit_grouped import (
        HitGroupedPlugin as Old,
    )
    from waveform_analysis.core.plugins.builtin.hit_grouped import (
        HitGroupedPlugin as New,
    )

    assert Old is New


def test_hit_merged_features_old_path_is_new_bundle():
    """hit_merged_features 迁移后，旧 cpu/hit 深导入与新 hit_merged_features bundle 指向同一插件。"""
    from waveform_analysis.core.plugins.builtin.cpu.hit_merged_features import (
        HIT_MERGED_FEATURES_DTYPE as OldDT,
    )
    from waveform_analysis.core.plugins.builtin.cpu.hit_merged_features import (
        HitMergedFeaturesPlugin as Old,
    )
    from waveform_analysis.core.plugins.builtin.hit.hit_merged_features import (
        HIT_MERGED_FEATURES_DTYPE as OldDeepDT,
    )
    from waveform_analysis.core.plugins.builtin.hit.hit_merged_features import (
        HitMergedFeaturesPlugin as OldDeep,
    )
    from waveform_analysis.core.plugins.builtin.hit_merged_features import (
        HIT_MERGED_FEATURES_DTYPE as NewDT,
    )
    from waveform_analysis.core.plugins.builtin.hit_merged_features import (
        HitMergedFeaturesPlugin as New,
    )

    assert Old is New
    assert OldDeep is New
    assert OldDT is NewDT
    assert OldDeepDT is NewDT
