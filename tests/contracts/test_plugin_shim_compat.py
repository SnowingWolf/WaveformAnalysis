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


def test_records_old_paths_resolve_to_bundles():
    """records 家族迁移后，旧 cpu.records.* 路径与新 bundle 路径指向同一类对象。"""
    from waveform_analysis.core.plugins.builtin.cpu import records as old
    from waveform_analysis.core.plugins.builtin.records import RecordsPlugin as NewRecords
    from waveform_analysis.core.plugins.builtin.wave_pool import WavePoolPlugin as NewWavePool
    from waveform_analysis.core.plugins.builtin.wave_pool_filtered import (
        WavePoolFilteredPlugin as NewWavePoolFiltered,
    )

    assert old.RecordsPlugin is NewRecords
    assert old.WavePoolPlugin is NewWavePool
    assert old.WavePoolFilteredPlugin is NewWavePoolFiltered


def test_records_shim_reexports_private_names():
    """cpu.records shim 必须 re-export 供字符串 mock / 懒加载的私有名。"""
    from waveform_analysis.core.plugins.builtin.cpu import records as shim
    from waveform_analysis.core.plugins.builtin.records._compute import (
        _build_records_bundle,
        _cleanup_stale_bundles,
        _RecordsBundlePluginBase,
        get_records_bundle,
        get_records_bundle_cache_key,
    )

    assert shim._RecordsBundlePluginBase is _RecordsBundlePluginBase
    assert shim._build_records_bundle is _build_records_bundle
    assert shim._cleanup_stale_bundles is _cleanup_stale_bundles
    assert shim.get_records_bundle is get_records_bundle
    assert shim.get_records_bundle_cache_key is get_records_bundle_cache_key
    assert callable(shim.build_records_from_raw_files)
    assert callable(shim._build_polarity_lookup)
    assert hasattr(shim, "RecordLookup")


def test_records_asymmetry_mask_old_path_is_new_bundle():
    """records_asymmetry_mask 迁移后，旧深导入与新 bundle 路径指向同一类对象。"""
    from waveform_analysis.core.plugins.builtin.cpu.records_asymmetry import (
        RecordsAsymmetryMaskPlugin as Old,
    )
    from waveform_analysis.core.plugins.builtin.records_asymmetry_mask import (
        RecordsAsymmetryMaskPlugin as New,
    )

    assert Old is New


def test_records_channel_role_masks_old_paths_are_new_bundles():
    """channel-role masks 迁移后，旧 records_channel_role.* 路径指向新 bundle 类对象。"""
    from waveform_analysis.core.plugins.builtin.cpu.records_channel_role import (
        ROLE_DETECTOR as OldRoleDetector,
    )
    from waveform_analysis.core.plugins.builtin.cpu.records_channel_role import (
        ROLE_VETO as OldRoleVeto,
    )
    from waveform_analysis.core.plugins.builtin.cpu.records_channel_role import (
        RecordsDetectorMaskPlugin as OldDetector,
    )
    from waveform_analysis.core.plugins.builtin.cpu.records_channel_role import (
        RecordsVetoMaskPlugin as OldVeto,
    )
    from waveform_analysis.core.plugins.builtin.cpu.records_channel_role import (
        _RecordsChannelRoleMaskPlugin as OldBase,
    )
    from waveform_analysis.core.plugins.builtin.cpu.records_channel_role import (
        _resolve_roles as OldResolve,
    )
    from waveform_analysis.core.plugins.builtin.records_detector_mask import (
        RecordsDetectorMaskPlugin as NewDetector,
    )
    from waveform_analysis.core.plugins.builtin.records_detector_mask._compute import (
        ROLE_DETECTOR as NewRoleDetector,
    )
    from waveform_analysis.core.plugins.builtin.records_detector_mask._compute import (
        ROLE_VETO as NewRoleVeto,
    )
    from waveform_analysis.core.plugins.builtin.records_detector_mask._compute import (
        _RecordsChannelRoleMaskPlugin as NewBase,
    )
    from waveform_analysis.core.plugins.builtin.records_detector_mask._compute import (
        _resolve_roles as NewResolve,
    )
    from waveform_analysis.core.plugins.builtin.records_veto_mask import (
        RecordsVetoMaskPlugin as NewVeto,
    )

    assert OldDetector is NewDetector
    assert OldVeto is NewVeto
    assert OldBase is NewBase
    assert OldResolve is NewResolve
    assert OldRoleDetector == NewRoleDetector == "detector"
    assert OldRoleVeto == NewRoleVeto == "veto"


def test_event_analysis_old_paths_resolve_to_bundles():
    """event_analysis 迁移后，旧 cpu.event_analysis.* 路径指向 df_events / df_paired。"""
    from waveform_analysis.core.plugins.builtin.cpu.event_analysis import (
        GroupedEventsPlugin as OldGrouped,
    )
    from waveform_analysis.core.plugins.builtin.cpu.event_analysis import (
        PairedEventsPlugin as OldPaired,
    )
    from waveform_analysis.core.plugins.builtin.df_events import (
        GroupedEventsPlugin as NewGrouped,
    )
    from waveform_analysis.core.plugins.builtin.df_paired import (
        PairedEventsPlugin as NewPaired,
    )

    assert OldGrouped is NewGrouped
    assert OldPaired is NewPaired


def test_cpu_lazy_imports_resolve_to_new_bundles():
    """builtin.cpu 懒加载映射指向新 bundle（RecordsPlugin 等）。"""
    from waveform_analysis.core.plugins.builtin import cpu

    expected = {
        "RecordsPlugin": "waveform_analysis.core.plugins.builtin.records.plugin",
        "WavePoolPlugin": "waveform_analysis.core.plugins.builtin.wave_pool.plugin",
        "WavePoolFilteredPlugin": (
            "waveform_analysis.core.plugins.builtin.wave_pool_filtered.plugin"
        ),
        "RecordsAsymmetryMaskPlugin": (
            "waveform_analysis.core.plugins.builtin.records_asymmetry_mask.plugin"
        ),
        "RecordsDetectorMaskPlugin": (
            "waveform_analysis.core.plugins.builtin.records_detector_mask.plugin"
        ),
        "RecordsVetoMaskPlugin": (
            "waveform_analysis.core.plugins.builtin.records_veto_mask.plugin"
        ),
        "GroupedEventsPlugin": "waveform_analysis.core.plugins.builtin.df_events.plugin",
        "PairedEventsPlugin": "waveform_analysis.core.plugins.builtin.df_paired.plugin",
    }
    for name, module in expected.items():
        assert getattr(cpu, name).__module__ == module, name
