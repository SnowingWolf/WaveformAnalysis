"""Tests for DataFramePlugin (df bundle)."""

from waveform_analysis.core.plugins.builtin.cpu.dataframe import (
    DataFramePlugin as ShimPlugin,
)
from waveform_analysis.core.plugins.builtin.df import DataFramePlugin


def test_old_path_is_new_bundle():
    assert ShimPlugin is DataFramePlugin


def test_plugin_metadata():
    plugin = DataFramePlugin()
    assert plugin.provides == "df"
    assert plugin.version == "1.7.0"
    assert "use_filtered" in plugin.options
