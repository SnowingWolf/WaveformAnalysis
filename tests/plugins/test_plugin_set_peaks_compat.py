import pytest

from waveform_analysis.core.plugins.plugin_sets import PLUGIN_SETS, get_plugin_set
from waveform_analysis.core.plugins.plugin_sets.peaks import plugins_peaks
from waveform_analysis.core.plugins.plugin_sets.signal_processing import (
    plugins_signal_processing,
)


def _provides_names(plugins):
    return [p.provides for p in plugins]


def test_get_plugin_set_peaks_available():
    factory = get_plugin_set("peaks")
    plugins = factory()

    assert len(plugins) >= 2
    assert _provides_names(plugins)[:2] == ["waveform_width", "s1_s2"]


def test_get_plugin_set_signal_processing_alias_available():
    factory = get_plugin_set("signal_processing")
    plugins = factory()

    assert len(plugins) >= 2
    assert _provides_names(plugins)[:2] == ["waveform_width", "s1_s2"]


def test_plugin_set_registry_contains_both_keys():
    assert "peaks" in PLUGIN_SETS
    assert "signal_processing" in PLUGIN_SETS

    peaks_plugins = PLUGIN_SETS["peaks"]()
    alias_plugins = PLUGIN_SETS["signal_processing"]()

    assert _provides_names(peaks_plugins) == _provides_names(alias_plugins)


def test_plugins_signal_processing_emits_deprecation_warning():
    with pytest.warns(DeprecationWarning, match="signal_processing"):
        alias_plugins = plugins_signal_processing()

    peaks_plugins = plugins_peaks()
    assert _provides_names(alias_plugins) == _provides_names(peaks_plugins)
