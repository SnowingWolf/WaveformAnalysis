from waveform_analysis.core.plugins import profiles
from waveform_analysis.core.plugins.plugin_sets import PLUGIN_SETS, get_plugin_set


def _provides_names(plugins):
    return [p.provides for p in plugins]


def test_get_plugin_set_hit_available():
    """Test the new hit plugin set."""
    factory = get_plugin_set("hit")
    plugins = factory()

    provides = _provides_names(plugins)
    assert len(plugins) == 9
    assert provides == [
        "hit",
        "records_asymmetry_mask",
        "records_detector_mask",
        "records_veto_mask",
        "hit_threshold",
        "hit_merge_clusters",
        "hit_merged",
        "hit_merged_components",
        "hit_merged_features",
    ]


def test_get_plugin_set_peaks_available():
    """Test the updated peaks plugin set (now includes peaklets)."""
    factory = get_plugin_set("peaks")
    plugins = factory()

    provides = _provides_names(plugins)
    assert len(plugins) == 10
    assert provides == [
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
    ]


def test_get_plugin_set_event_available():
    """Test the events plugin set.

    The events set now hosts the new S1-S2 pairing workflow plus the
    deprecated ``hit_grouped`` legacy plugin. ``df_events`` and ``df_paired``
    have been moved to the ``tabular`` plugin set because they produce
    DataFrame (tabular) outputs.
    """
    factory = get_plugin_set("events")
    plugins = factory()

    provides = _provides_names(plugins)
    assert provides == [
        "s1_s2_pair_candidates",
        "s1_s2_pairs",
        "position_reconstruction",
        "events",
        "hit_grouped",
    ]


def test_plugin_set_events_in_registry():
    """Test that events key exists in registry."""
    assert "events" in PLUGIN_SETS


def test_get_plugin_set_tabular_includes_df_events_and_df_paired():
    """Tabular set should include df, df_events, and df_paired."""
    factory = get_plugin_set("tabular")
    plugins = factory()

    provides = _provides_names(plugins)
    assert provides == ["df", "df_events", "df_paired"]


def test_plugin_set_registry_contains_all_keys():
    """Test that registry contains all expected keys."""
    assert "io" in PLUGIN_SETS
    assert "waveform" in PLUGIN_SETS
    assert "hit" in PLUGIN_SETS
    assert "peaks" in PLUGIN_SETS
    assert "basic_features" in PLUGIN_SETS
    assert "tabular" in PLUGIN_SETS
    assert "events" in PLUGIN_SETS


def test_plugins_waveform_includes_records():
    factory = get_plugin_set("waveform")
    plugins = factory()
    provides = _provides_names(plugins)
    assert provides == [
        "st_waveforms",
        "filtered_waveforms",
        "records",
        "wave_pool",
        "wave_pool_filtered",
    ]


def test_cpu_default_includes_records():
    plugins = profiles.cpu_default()
    provides = _provides_names(plugins)
    assert "records" in provides


def test_cpu_default_includes_all_layers():
    """Test that cpu_default includes all processing layers."""
    plugins = profiles.cpu_default()
    provides = _provides_names(plugins)

    # Check key data types from each layer are present
    assert "records" in provides  # waveform layer
    assert "hit_threshold" in provides  # hit layer
    assert "peaklets" in provides  # hit layer (peaklets)
    assert "peaks" in provides  # peaks layer
    assert "df_events" in provides  # event layer
