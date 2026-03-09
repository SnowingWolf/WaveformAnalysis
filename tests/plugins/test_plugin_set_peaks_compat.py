import pytest

from waveform_analysis.core.plugins.plugin_sets import PLUGIN_SETS, get_plugin_set


def _provides_names(plugins):
    return [p.provides for p in plugins]


def test_get_plugin_set_peaks_available():
    factory = get_plugin_set("peaks")
    plugins = factory()

    assert len(plugins) >= 2
    assert _provides_names(plugins)[:2] == ["waveform_width", "s1_s2"]


def test_plugin_set_registry_contains_peaks_key():
    assert "peaks" in PLUGIN_SETS


def test_get_plugin_set_signal_processing_removed():
    with pytest.raises(KeyError, match="signal_processing"):
        get_plugin_set("signal_processing")
