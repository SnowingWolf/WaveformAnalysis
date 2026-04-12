from waveform_analysis.core.plugins import profiles
from waveform_analysis.core.plugins.plugin_sets import PLUGIN_SETS, get_plugin_set


def _provides_names(plugins):
    return [p.provides for p in plugins]


def test_get_plugin_set_peaks_available():
    factory = get_plugin_set("peaks")
    plugins = factory()

    provides = _provides_names(plugins)
    assert len(plugins) >= 6
    assert provides == [
        "hit",
        "hit_threshold",
        "hit_merge_clusters",
        "hit_merged",
        "hit_merged_components",
        "waveform_width",
        "s1_s2",
    ]


def test_plugin_set_registry_contains_peaks_key():
    assert "peaks" in PLUGIN_SETS


def test_plugins_waveform_includes_records():
    factory = get_plugin_set("waveform")
    plugins = factory()
    provides = _provides_names(plugins)
    assert provides == ["st_waveforms", "filtered_waveforms", "records", "wave_pool"]


def test_cpu_default_includes_records():
    plugins = profiles.cpu_default()
    provides = _provides_names(plugins)
    assert "records" in provides
