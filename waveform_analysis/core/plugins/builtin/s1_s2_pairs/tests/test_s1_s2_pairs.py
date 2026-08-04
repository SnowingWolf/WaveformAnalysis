"""Tests for S1S2PairSelectionPlugin (s1_s2_pairs bundle)."""

from waveform_analysis.core.plugins.builtin.cpu.s1_s2_pair_selection import (
    S1S2PairSelectionPlugin as ShimPlugin,
)
from waveform_analysis.core.plugins.builtin.s1_s2_pairs import S1S2PairSelectionPlugin


def test_old_path_is_new_bundle():
    assert ShimPlugin is S1S2PairSelectionPlugin


def test_plugin_metadata():
    plugin = S1S2PairSelectionPlugin()
    assert plugin.provides == "s1_s2_pairs"
    assert plugin.version == "0.2.0"
    assert plugin.depends_on == ["s1_s2_pair_candidates"]
