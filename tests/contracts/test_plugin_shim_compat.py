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


def test_phase4c_cpu_module_shims_resolve_to_bundles():
    """Phase 4c 迁移后，旧 cpu.* 深导入与新 bundle 路径指向同一类对象。"""
    import importlib

    mod_pairs = [
        # (old module, name, new bundle)
        ("waveform_analysis.core.plugins.builtin.cpu.raw_files", "RawFileNamesPlugin", "raw_files"),
        ("waveform_analysis.core.plugins.builtin.cpu.waveforms", "RawFileNamesPlugin", "raw_files"),
        ("waveform_analysis.core.plugins.builtin.cpu.waveforms", "WaveformsPlugin", "st_waveforms"),
        ("waveform_analysis.core.plugins.builtin.cpu.waveforms", "WaveformStruct", "st_waveforms"),
        (
            "waveform_analysis.core.plugins.builtin.cpu.waveforms",
            "WaveformStructConfig",
            "st_waveforms",
        ),
        (
            "waveform_analysis.core.plugins.builtin.cpu.filtering",
            "FilteredWaveformsPlugin",
            "filtered_waveforms",
        ),
        ("waveform_analysis.core.plugins.builtin.cpu.dataframe", "DataFramePlugin", "df"),
        (
            "waveform_analysis.core.plugins.builtin.cpu.basic_features",
            "BasicFeaturesPlugin",
            "basic_features",
        ),
        (
            "waveform_analysis.core.plugins.builtin.cpu.cache_analysis",
            "CacheAnalysisPlugin",
            "cache_analysis",
        ),
        (
            "waveform_analysis.core.plugins.builtin.cpu.peak_classification",
            "PeakClassificationPlugin",
            "peak_classification",
        ),
        (
            "waveform_analysis.core.plugins.builtin.cpu.s1_s2_pair_candidates",
            "S1S2PairCandidatesPlugin",
            "s1_s2_pair_candidates",
        ),
        (
            "waveform_analysis.core.plugins.builtin.cpu.s1_s2_pair_selection",
            "S1S2PairSelectionPlugin",
            "s1_s2_pairs",
        ),
        (
            "waveform_analysis.core.plugins.builtin.cpu.waveform_width",
            "WaveformWidthPlugin",
            "waveform_width",
        ),
        (
            "waveform_analysis.core.plugins.builtin.cpu.waveform_width_integral",
            "WaveformWidthIntegralPlugin",
            "waveform_width_integral",
        ),
        (
            "waveform_analysis.core.plugins.builtin.cpu.energy_reconstruction",
            "EnergyReconstructionPlugin",
            "energy_reconstruction",
        ),
        (
            "waveform_analysis.core.plugins.builtin.cpu.position_reconstruction",
            "PositionReconstructionPlugin",
            "position_reconstruction",
        ),
        ("waveform_analysis.core.plugins.builtin.cpu.event", "EventPlugin", "events"),
        (
            "waveform_analysis.core.plugins.builtin.streaming.cpu.signal_peaks",
            "SignalPeaksStreamPlugin",
            "signal_peaks_stream",
        ),
    ]
    for old_mod, name, bundle in mod_pairs:
        old = getattr(importlib.import_module(old_mod), name)
        new = getattr(
            importlib.import_module(f"waveform_analysis.core.plugins.builtin.{bundle}"), name
        )
        assert old is new, f"{name}: {old_mod} 与 {bundle} bundle 不是同一对象"


def test_phase4c_cpu_package_lazy_resolves_to_bundles():
    """Phase 4c 迁移后，builtin.cpu 懒加载类名指向新 bundle 同一类对象。"""
    import importlib

    from waveform_analysis.core.plugins.builtin import cpu

    pairs = [
        ("WaveformsPlugin", "st_waveforms"),
        ("WaveformStruct", "st_waveforms"),
        ("WaveformStructConfig", "st_waveforms"),
        ("RawFileNamesPlugin", "raw_files"),
        ("FilteredWaveformsPlugin", "filtered_waveforms"),
        ("DataFramePlugin", "df"),
        ("BasicFeaturesPlugin", "basic_features"),
        ("CacheAnalysisPlugin", "cache_analysis"),
        ("PeakClassificationPlugin", "peak_classification"),
        ("S1S2PairCandidatesPlugin", "s1_s2_pair_candidates"),
        ("S1S2PairSelectionPlugin", "s1_s2_pairs"),
        ("WaveformWidthPlugin", "waveform_width"),
        ("WaveformWidthIntegralPlugin", "waveform_width_integral"),
        ("EnergyReconstructionPlugin", "energy_reconstruction"),
        ("PositionReconstructionPlugin", "position_reconstruction"),
        ("EventPlugin", "events"),
    ]
    for class_name, bundle in pairs:
        old = getattr(cpu, class_name)
        new = getattr(
            importlib.import_module(f"waveform_analysis.core.plugins.builtin.{bundle}"),
            class_name,
        )
        assert old is new, f"{class_name}: builtin.cpu 与 {bundle} bundle 不是同一对象"


def test_phase4c_dtypes_resolve_from_bundles():
    """Phase 4c 迁移后 dtype 常量可从新 bundle 路径解析。"""
    import importlib

    dtype_pairs = [
        (
            "waveform_analysis.core.plugins.builtin.cpu.basic_features",
            "BASIC_FEATURES_DTYPE",
            "basic_features",
        ),
        (
            "waveform_analysis.core.plugins.builtin.cpu.waveform_width",
            "WAVEFORM_WIDTH_DTYPE",
            "waveform_width",
        ),
        (
            "waveform_analysis.core.plugins.builtin.cpu.waveform_width_integral",
            "WAVEFORM_WIDTH_INTEGRAL_DTYPE",
            "waveform_width_integral",
        ),
        (
            "waveform_analysis.core.plugins.builtin.cpu.peak_classification",
            "PEAK_CLASSIFICATION_DTYPE",
            "peak_classification",
        ),
        (
            "waveform_analysis.core.plugins.builtin.cpu.s1_s2_pair_candidates",
            "S1_S2_PAIR_CANDIDATES_DTYPE",
            "s1_s2_pair_candidates",
        ),
        (
            "waveform_analysis.core.plugins.builtin.cpu.energy_reconstruction",
            "ENERGY_RECONSTRUCTION_DTYPE",
            "energy_reconstruction",
        ),
        (
            "waveform_analysis.core.plugins.builtin.cpu.position_reconstruction",
            "POSITION_RECONSTRUCTION_DTYPE",
            "position_reconstruction",
        ),
        ("waveform_analysis.core.plugins.builtin.cpu.event", "EVENT_DTYPE", "events"),
    ]
    for old_mod, name, bundle in dtype_pairs:
        old = getattr(importlib.import_module(old_mod), name)
        new = getattr(
            importlib.import_module(f"waveform_analysis.core.plugins.builtin.{bundle}"), name
        )
        assert old is new, f"{name}: {old_mod} 与 {bundle} bundle 不是同一对象"


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
