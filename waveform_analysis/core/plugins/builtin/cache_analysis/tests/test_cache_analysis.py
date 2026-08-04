"""Tests for CacheAnalysisPlugin (cache_analysis bundle)."""

from waveform_analysis.core.plugins.builtin.cache_analysis import CacheAnalysisPlugin
from waveform_analysis.core.plugins.builtin.cpu.cache_analysis import (
    CacheAnalysisPlugin as ShimPlugin,
)


def test_old_path_is_new_bundle():
    assert ShimPlugin is CacheAnalysisPlugin


def test_plugin_metadata():
    plugin = CacheAnalysisPlugin()
    assert plugin.provides == "cache_analysis"
    assert plugin.version == "0.1.0"
    assert plugin.output_schema.kind == "dict"
    assert plugin.save_when == "never"
