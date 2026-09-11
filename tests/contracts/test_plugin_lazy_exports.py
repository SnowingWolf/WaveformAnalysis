"""Import and identity contracts for the lazy plugin package exports."""

from __future__ import annotations

import importlib
import json
import subprocess
import sys

import pytest

pytestmark = pytest.mark.contract


PLUGIN_AGGREGATORS = (
    "waveform_analysis.core.plugins",
    "waveform_analysis.core.plugins.core",
    "waveform_analysis.core.plugins.builtin",
    "waveform_analysis.core.plugins.builtin.cpu",
    "waveform_analysis.core.plugins.builtin.hit",
    "waveform_analysis.core.plugins.builtin.peaks",
    "waveform_analysis.core.plugins.builtin.streaming",
    "waveform_analysis.core.plugins.builtin.streaming.cpu",
)

EXPECTED_ALL = {
    "waveform_analysis.core.plugins": [
        "Plugin",
        "Option",
        "option",
        "takes_config",
        "StreamingPlugin",
        "StreamingContext",
        "PluginLoader",
        "load_plugins_from_entry_points",
        "load_plugins_from_directory",
        "PluginExecutionRecord",
        "PluginStatistics",
        "PluginStatsCollector",
        "get_stats_collector",
        "PluginHotReloader",
        "enable_hot_reload",
        "StraxPluginAdapter",
        "StraxContextAdapter",
        "wrap_strax_plugin",
        "create_strax_context",
        "strax_dtype_to_numpy",
        "numpy_dtype_to_strax",
        "RawFileNamesPlugin",
        "WaveformsPlugin",
        "WaveformStruct",
        "WaveformStructConfig",
        "HitFinderPlugin",
        "BasicFeaturesPlugin",
        "DataFramePlugin",
        "GroupedEventsPlugin",
        "PairedEventsPlugin",
        "RecordsPlugin",
        "WavePoolPlugin",
        "WavePoolFilteredPlugin",
        "RecordsAsymmetryMaskPlugin",
        "RecordsDetectorMaskPlugin",
        "RecordsVetoMaskPlugin",
        "FilteredWaveformsPlugin",
        "WaveformWidthPlugin",
        "SignalPeaksStreamPlugin",
        "plugin_sets",
        "profiles",
    ],
    "waveform_analysis.core.plugins.core": [
        "Plugin",
        "Option",
        "option",
        "takes_config",
        "PluginSpec",
        "OutputSchema",
        "FieldSpec",
        "InputRequirement",
        "Capabilities",
        "ConfigField",
        "StreamingPlugin",
        "StreamingContext",
        "BatchProcessingPlugin",
        "PluginLoader",
        "load_plugins_from_entry_points",
        "load_plugins_from_directory",
        "PluginExecutionRecord",
        "PluginStatistics",
        "PluginStatsCollector",
        "get_stats_collector",
        "PluginHotReloader",
        "enable_hot_reload",
        "StraxPluginAdapter",
        "StraxContextAdapter",
        "wrap_strax_plugin",
        "create_strax_context",
        "strax_dtype_to_numpy",
        "numpy_dtype_to_strax",
    ],
    "waveform_analysis.core.plugins.builtin": [
        "RawFileNamesPlugin",
        "RawFilesPlugin",
        "WaveformsPlugin",
        "StWaveformsPlugin",
        "WaveformStruct",
        "WaveformStructConfig",
        "HitFinderPlugin",
        "BasicFeaturesPlugin",
        "DataFramePlugin",
        "GroupedEventsPlugin",
        "PairedEventsPlugin",
        "RecordsPlugin",
        "WavePoolPlugin",
        "WavePoolFilteredPlugin",
        "FilteredWaveformsPlugin",
        "HIT_DTYPE",
        "WaveformWidthPlugin",
        "WAVEFORM_WIDTH_DTYPE",
        "WaveformWidthIntegralPlugin",
        "WAVEFORM_WIDTH_INTEGRAL_DTYPE",
        "CacheAnalysisPlugin",
        "SignalPeaksStreamPlugin",
        "standard_plugins",
    ],
    "waveform_analysis.core.plugins.builtin.cpu": [
        "RawFileNamesPlugin",
        "RawFilesPlugin",
        "WaveformsPlugin",
        "StWaveformsPlugin",
        "WaveformStruct",
        "WaveformStructConfig",
        "HitFinderPlugin",
        "BasicFeaturesPlugin",
        "BASIC_FEATURES_DTYPE",
        "DataFramePlugin",
        "EventPlugin",
        "GroupedEventsPlugin",
        "PairedEventsPlugin",
        "PositionReconstructionPlugin",
        "EnergyReconstructionPlugin",
        "ENERGY_RECONSTRUCTION_DTYPE",
        "FilteredWaveformsPlugin",
        "PeakClassificationPlugin",
        "PEAK_CLASSIFICATION_DTYPE",
        "LABEL_S1",
        "LABEL_S2",
        "LABEL_S1_S2",
        "LABEL_UNKNOWN",
        "HIT_DTYPE",
        "WaveformWidthPlugin",
        "WAVEFORM_WIDTH_DTYPE",
        "WaveformWidthIntegralPlugin",
        "WAVEFORM_WIDTH_INTEGRAL_DTYPE",
        "S1S2PairCandidatesPlugin",
        "S1S2PairSelectionPlugin",
        "S1_S2_PAIR_CANDIDATES_DTYPE",
        "FLAG_VALID_TIME",
        "FLAG_RATIO_IN_RANGE",
        "FLAG_S1_LOW_QUALITY",
        "FLAG_S2_LOW_QUALITY",
        "FLAG_MULTI_S1_CANDIDATE",
        "FLAG_MULTI_S2_CANDIDATE",
        "FLAG_CLOSE_COMPETITOR",
        "FLAG_ORPHAN_S1",
        "FLAG_ORPHAN_S2",
        "FLAG_NEAR_CHUNK_BOUNDARY",
        "CacheAnalysisPlugin",
        "RecordsPlugin",
        "WavePoolPlugin",
        "WavePoolFilteredPlugin",
        "RecordsAsymmetryMaskPlugin",
        "RecordsDetectorMaskPlugin",
        "RecordsVetoMaskPlugin",
        "standard_plugins",
        "HitGroupedPlugin",
        "ThresholdHitPlugin",
        "HitMergePlugin",
        "HitMergeClustersPlugin",
        "HitMergedComponentsPlugin",
        "HitMergedFeaturesPlugin",
        "THRESHOLD_HIT_DTYPE",
        "HIT_MERGED_DTYPE",
        "HIT_MERGE_CLUSTERS_DTYPE",
        "HIT_MERGED_COMPONENTS_DTYPE",
        "HIT_MERGED_FEATURES_DTYPE",
        "PeakletPlugin",
        "PeakletComponentsPlugin",
        "PeakletWaveformPlugin",
        "PeakletWaveformPoolPlugin",
        "PeakletFeaturesPlugin",
        "PeakletChannelsPlugin",
        "PeaksPlugin",
        "PEAKLET_DTYPE",
        "PEAKLET_COMPONENTS_DTYPE",
        "PEAKLET_WAVEFORMS_DTYPE",
        "PEAKLET_FEATURES_DTYPE",
        "PEAKLET_CHANNELS_DTYPE",
        "PEAKS_DTYPE",
    ],
    "waveform_analysis.core.plugins.builtin.hit": [
        "HitFinderPlugin",
        "ThresholdHitPlugin",
        "HitMergePlugin",
        "HitMergeClustersPlugin",
        "HitMergedComponentsPlugin",
        "HitMergedFeaturesPlugin",
        "HitGroupedPlugin",
        "HIT_DTYPE",
        "THRESHOLD_HIT_DTYPE",
        "HIT_MERGED_DTYPE",
        "HIT_MERGE_CLUSTERS_DTYPE",
        "HIT_MERGED_COMPONENTS_DTYPE",
        "HIT_MERGED_FEATURES_DTYPE",
    ],
    "waveform_analysis.core.plugins.builtin.peaks": [
        "PeakletPlugin",
        "PeakletComponentsPlugin",
        "PeakletWaveformPlugin",
        "PeakletWaveformPoolPlugin",
        "PeakletFeaturesPlugin",
        "PeakletChannelsPlugin",
        "PeaksPlugin",
        "PEAKLET_DTYPE",
        "PEAKLET_COMPONENTS_DTYPE",
        "PEAKLET_WAVEFORMS_DTYPE",
        "PEAKLET_FEATURES_DTYPE",
        "PEAKLET_CHANNELS_DTYPE",
        "PEAKS_DTYPE",
    ],
    "waveform_analysis.core.plugins.builtin.streaming": [
        "SignalPeaksStreamPlugin",
    ],
    "waveform_analysis.core.plugins.builtin.streaming.cpu": [
        "SignalPeaksStreamPlugin",
    ],
}


def _run_fresh(code: str) -> dict:
    result = subprocess.run(
        [sys.executable, "-c", code],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def test_plugin_aggregators_are_light_in_fresh_processes():
    code = """
import importlib
import json
import sys

module_name = MODULE_NAME
module = importlib.import_module(module_name)
parts = module_name.split('.')
ancestors = {'.'.join(parts[:index]) for index in range(1, len(parts) + 1)}
bundle_prefix = 'waveform_analysis.core.plugins.builtin.'
loaded = set(sys.modules)
unexpected_bundles = sorted(
    name for name in loaded
    if name.startswith(bundle_prefix) and name not in ancestors
)
print(json.dumps({
    'heavy': sorted(
        name for name in loaded
        if name == 'importlib.metadata'
        or name.startswith(('numpy', 'scipy', 'pandas', 'numba', 'jax'))
    ),
    'unexpected_bundles': unexpected_bundles,
    'all': module.__all__,
    'lazy_missing': [name for name in module.__all__ if name not in vars(module)],
}))
"""
    for module_name in PLUGIN_AGGREGATORS:
        observed = _run_fresh(code.replace("MODULE_NAME", repr(module_name)))
        assert observed["heavy"] == [], module_name
        assert observed["unexpected_bundles"] == [], module_name
        assert observed["all"] == EXPECTED_ALL[module_name]
        assert observed["lazy_missing"] == EXPECTED_ALL[module_name], module_name


def test_plugin_aggregator_dir_keeps_legacy_extra_names():
    expected_extras = {
        "waveform_analysis.core.plugins": {
            "builtin",
            "core",
            "import_module",
            "plugin_sets",
            "profiles",
        },
        "waveform_analysis.core.plugins.core": {
            "adapters",
            "base",
            "batch_processing",
            "hot_reload",
            "loader",
            "spec",
            "stats",
            "streaming",
        },
        "waveform_analysis.core.plugins.builtin": {
            "cpu",
            "streaming",
            "raw_files",
            "st_waveforms",
            "hit",
            "peaks",
        },
        "waveform_analysis.core.plugins.builtin.cpu": {
            "S1S2ClassifierPlugin",
            "S1_S2_CLASSIFIER_DTYPE",
            "LABEL_S1",
            "LABEL_S2",
            "LABEL_UNKNOWN",
            "cpu_default",
        },
        "waveform_analysis.core.plugins.builtin.hit": {
            "hit_finder",
            "hit_grouped",
            "hit_merge",
            "hit_merged_features",
            "plugin",
        },
        "waveform_analysis.core.plugins.builtin.peaks": {"plugin"},
        "waveform_analysis.core.plugins.builtin.streaming": {"cpu", "export", "exporter"},
        "waveform_analysis.core.plugins.builtin.streaming.cpu": {
            "signal_peaks",
            "export",
            "exporter",
        },
    }
    for module_name, names in expected_extras.items():
        module = importlib.import_module(module_name)
        assert names <= {name for name in dir(module) if not name.startswith("_")}


@pytest.mark.parametrize(
    ("module_name", "name", "canonical_module", "canonical_name"),
    [
        (
            "waveform_analysis.core.plugins",
            "Plugin",
            "waveform_analysis.core.plugins.core.base",
            "Plugin",
        ),
        (
            "waveform_analysis.core.plugins",
            "RawFileNamesPlugin",
            "waveform_analysis.core.plugins.builtin.raw_files",
            "RawFileNamesPlugin",
        ),
        (
            "waveform_analysis.core.plugins.core",
            "PluginSpec",
            "waveform_analysis.core.plugins.core.spec",
            "PluginSpec",
        ),
        (
            "waveform_analysis.core.plugins.builtin",
            "WaveformsPlugin",
            "waveform_analysis.core.plugins.builtin.st_waveforms",
            "WaveformsPlugin",
        ),
        (
            "waveform_analysis.core.plugins.builtin",
            "RawFilesPlugin",
            "waveform_analysis.core.plugins.builtin.raw_files",
            "RawFileNamesPlugin",
        ),
        (
            "waveform_analysis.core.plugins.builtin.cpu",
            "WaveformStruct",
            "waveform_analysis.core.plugins.builtin.st_waveforms",
            "WaveformStruct",
        ),
        (
            "waveform_analysis.core.plugins.builtin.hit",
            "HIT_MERGED_DTYPE",
            "waveform_analysis.core.plugins.builtin.hit_merged",
            "HIT_MERGED_DTYPE",
        ),
        (
            "waveform_analysis.core.plugins.builtin.peaks",
            "PEAKS_DTYPE",
            "waveform_analysis.core.plugins.builtin.peaklets._compute",
            "PEAKS_DTYPE",
        ),
        (
            "waveform_analysis.core.plugins.builtin.streaming",
            "SignalPeaksStreamPlugin",
            "waveform_analysis.core.plugins.builtin.signal_peaks_stream",
            "SignalPeaksStreamPlugin",
        ),
    ],
)
def test_lazy_export_identity_and_cache(module_name, name, canonical_module, canonical_name):
    observed = _run_fresh(
        f"""
import importlib
import json

module = importlib.import_module({module_name!r})
assert {name!r} not in vars(module)
value = getattr(module, {name!r})
canonical = getattr(importlib.import_module({canonical_module!r}), {canonical_name!r})
assert value is canonical
assert vars(module)[{name!r}] is value
assert getattr(module, {name!r}) is value
print(json.dumps({{'ok': True}}))
"""
    )
    assert observed == {"ok": True}


def test_cpu_legacy_exports_and_standard_plugins_are_cached():
    observed = _run_fresh(
        """
import importlib
import json

cpu = importlib.import_module('waveform_analysis.core.plugins.builtin.cpu')
profiles = importlib.import_module('waveform_analysis.core.plugins.profiles')
legacy = importlib.import_module('waveform_analysis.core.plugins.builtin.cpu.s1_s2_classifier')
assert 'standard_plugins' not in vars(cpu)
assert cpu.S1S2ClassifierPlugin is legacy.S1S2ClassifierPlugin
assert cpu.S1_S2_CLASSIFIER_DTYPE is legacy.S1_S2_CLASSIFIER_DTYPE
assert cpu.LABEL_S1 is legacy.LABEL_S1
assert cpu.LABEL_S2 is legacy.LABEL_S2
assert cpu.LABEL_UNKNOWN is legacy.LABEL_UNKNOWN
assert cpu.cpu_default is profiles.cpu_default
standard = cpu.standard_plugins
assert vars(cpu)['standard_plugins'] is standard
assert cpu.standard_plugins is standard
builtin = importlib.import_module('waveform_analysis.core.plugins.builtin')
assert builtin.standard_plugins is standard
print(json.dumps({'provides': [plugin.provides for plugin in standard]}))
"""
    )
    assert observed["provides"] == [
        "raw_files",
        "st_waveforms",
        "filtered_waveforms",
        "records",
        "wave_pool",
        "wave_pool_filtered",
        "hit",
        "records_asymmetry_mask",
        "records_detector_mask",
        "records_veto_mask",
        "hit_threshold",
        "hit_merge_clusters",
        "hit_merged",
        "hit_merged_components",
        "hit_merged_features",
        "peaklet_components",
        "peaklets",
        "peaklet_waveforms",
        "peaklet_waveform_pool",
        "peaklet_features",
        "peaklet_channels",
        "peaks",
        "waveform_width",
        "s1_s2",
        "peak_classification",
        "basic_features",
        "waveform_width_integral",
        "df",
        "df_events",
        "df_paired",
        "s1_s2_pair_candidates",
        "s1_s2_pairs",
        "position_reconstruction",
        "energy_reconstruction",
        "events",
        "hit_grouped",
    ]


def test_profiles_and_plugin_sets_keep_registry_identity():
    profiles = importlib.import_module("waveform_analysis.core.plugins.profiles")
    registry = profiles.PROFILES
    assert profiles.PROFILES is registry
    for alias, target in {
        "cpu": "cpu_default",
        "streaming": "streaming_default",
        "jax": "jax_accel",
    }.items():
        assert registry[alias] is registry[target]

    plugin_sets = importlib.import_module("waveform_analysis.core.plugins.plugin_sets")
    sets = plugin_sets.PLUGIN_SETS
    assert plugin_sets.PLUGIN_SETS is sets
    assert list(sets) == [
        "io",
        "waveform",
        "hit",
        "peaks",
        "basic_features",
        "tabular",
        "events",
    ]
    for name in sets:
        assert sets[name] is getattr(plugin_sets, f"plugins_{name}")


@pytest.mark.parametrize(
    "legacy,canonical,attribute",
    [
        (
            "waveform_analysis.core.plugins.builtin.cpu.waveforms",
            "waveform_analysis.core.plugins.builtin.st_waveforms",
            "WaveformsPlugin",
        ),
        (
            "waveform_analysis.core.plugins.builtin.cpu.peak_finding",
            "waveform_analysis.core.plugins.builtin.hit",
            "HitFinderPlugin",
        ),
        (
            "waveform_analysis.core.plugins.builtin.cpu.peaklets",
            "waveform_analysis.core.plugins.builtin.peaklets",
            "PeakletPlugin",
        ),
        (
            "waveform_analysis.core.plugins.builtin.hit.hit_merge",
            "waveform_analysis.core.plugins.builtin.hit_merged",
            "HitMergePlugin",
        ),
        (
            "waveform_analysis.core.plugins.builtin.peaks.peaklets",
            "waveform_analysis.core.plugins.builtin.peaklets",
            "PeakletPlugin",
        ),
        (
            "waveform_analysis.core.plugins.builtin.streaming.cpu.signal_peaks",
            "waveform_analysis.core.plugins.builtin.signal_peaks_stream",
            "SignalPeaksStreamPlugin",
        ),
    ],
)
@pytest.mark.parametrize("canonical_first", [False, True])
def test_legacy_and_canonical_direct_import_orders(legacy, canonical, attribute, canonical_first):
    first, second = (canonical, legacy) if canonical_first else (legacy, canonical)
    code = f"""
import importlib
first = importlib.import_module({first!r})
second = importlib.import_module({second!r})
assert getattr(first, {attribute!r}) is getattr(second, {attribute!r})
"""
    subprocess.run([sys.executable, "-c", code], check=True, capture_output=True, text=True)


def test_unknown_plugin_export_keeps_attribute_error_message():
    for module_name in PLUGIN_AGGREGATORS + (
        "waveform_analysis.core.plugins.profiles",
        "waveform_analysis.core.plugins.plugin_sets",
    ):
        module = importlib.import_module(module_name)
        unknown_name = "__definitely_not_a_plugin_export__"
        with pytest.raises(AttributeError) as caught:
            getattr(module, unknown_name)
        assert str(caught.value) == (f"module {module_name!r} has no attribute {unknown_name!r}")
