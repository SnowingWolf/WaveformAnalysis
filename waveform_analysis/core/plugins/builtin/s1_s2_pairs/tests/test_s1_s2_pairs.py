"""Tests for S1S2PairSelectionPlugin (s1_s2_pairs bundle)."""

import numpy as np

from waveform_analysis.core.plugins.builtin.cpu.s1_s2_pair_selection import (
    S1S2PairSelectionPlugin as ShimPlugin,
)
from waveform_analysis.core.plugins.builtin.s1_s2_pair_candidates import (
    FLAG_ORPHAN_S1,
    FLAG_ORPHAN_S2,
    S1_S2_PAIR_CANDIDATES_DTYPE,
)
from waveform_analysis.core.plugins.builtin.s1_s2_pairs import S1S2PairSelectionPlugin


def test_old_path_is_new_bundle():
    assert ShimPlugin is S1S2PairSelectionPlugin


def test_plugin_metadata():
    plugin = S1S2PairSelectionPlugin()
    assert plugin.provides == "s1_s2_pairs"
    assert plugin.version == "0.3.0"
    assert plugin.depends_on == ["s1_s2_pair_candidates"]


class _MockContext:
    def __init__(self, candidates):
        self.candidates = candidates

    def get_data(self, run_id, data_name):
        assert data_name == "s1_s2_pair_candidates"
        return self.candidates

    def get_config(self, plugin, option_name):
        return plugin.options[option_name].default


def test_selection_filters_orphans_before_copy_score_and_rank():
    candidates = np.zeros(4, dtype=S1_S2_PAIR_CANDIDATES_DTYPE)
    candidates[0]["pair_id"] = 10
    candidates[0]["s1_peak_id"] = 1
    candidates[0]["s2_peak_id"] = 20
    candidates[0]["s1_area"] = 100.0
    candidates[0]["s2_area"] = 1000.0
    candidates[1]["pair_id"] = 11
    candidates[1]["s1_peak_id"] = 2
    candidates[1]["s2_peak_id"] = 20
    candidates[1]["s1_area"] = 200.0
    candidates[1]["s2_area"] = 1000.0
    candidates[2]["s1_peak_id"] = 3
    candidates[2]["s2_peak_id"] = -1
    candidates[2]["flags"] = FLAG_ORPHAN_S1
    candidates[2]["selected"] = True
    candidates[3]["s1_peak_id"] = -1
    candidates[3]["s2_peak_id"] = 21
    candidates[3]["flags"] = FLAG_ORPHAN_S2
    candidates[3]["selected"] = True

    result = S1S2PairSelectionPlugin().compute(_MockContext(candidates), "test_run")

    assert len(result) == 2
    assert np.all(result["s1_peak_id"] >= 0)
    assert np.all(result["s2_peak_id"] >= 0)
    assert np.all((result["flags"] & (FLAG_ORPHAN_S1 | FLAG_ORPHAN_S2)) == 0)
    assert result[result["selected"]][0]["s1_peak_id"] == 2
    assert np.all(candidates[2:]["selected"]), "输入 orphan 不应被原地修改"
