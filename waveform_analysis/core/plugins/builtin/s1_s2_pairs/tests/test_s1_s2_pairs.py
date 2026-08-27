"""Tests for S1S2PairSelectionPlugin (s1_s2_pairs bundle)."""

import numpy as np
import pytest

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
    def __init__(self, candidates, config=None):
        self.candidates = candidates
        self.config = config or {}

    def get_data(self, run_id, data_name):
        assert data_name == "s1_s2_pair_candidates"
        return self.candidates

    def get_config(self, plugin, option_name):
        return self.config.get(option_name, plugin.options[option_name].default)


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


def _normalization_counterexample_candidates():
    candidates = np.zeros(3, dtype=S1_S2_PAIR_CANDIDATES_DTYPE)

    candidates[0]["pair_id"] = 10
    candidates[0]["s1_peak_id"] = 1
    candidates[0]["s2_peak_id"] = 20
    candidates[0]["drift_time_ns"] = 100.0
    candidates[0]["s1_area"] = 100.0
    candidates[0]["s2_area"] = 1000.0
    candidates[0]["s1_width"] = 100.0
    candidates[0]["s2_width"] = 100.0
    candidates[0]["s1_n_channels"] = 5
    candidates[0]["s2_n_channels"] = 5

    candidates[1]["pair_id"] = 11
    candidates[1]["s1_peak_id"] = 2
    candidates[1]["s2_peak_id"] = 20
    candidates[1]["drift_time_ns"] = 200.0
    candidates[1]["s1_area"] = 160.0
    candidates[1]["s2_area"] = 1000.0
    candidates[1]["s1_width"] = 100.0
    candidates[1]["s2_width"] = 100.0
    candidates[1]["s1_n_channels"] = 5
    candidates[1]["s2_n_channels"] = 5

    candidates[2]["s1_peak_id"] = 3
    candidates[2]["s2_peak_id"] = -1
    candidates[2]["drift_time_ns"] = -1.0
    candidates[2]["flags"] = FLAG_ORPHAN_S1
    return candidates


def _legacy_scored_complete_rows(candidates, mode, require_s2_larger):
    """Reproduce the pre-filter score/rank path for complete rows only."""
    legacy = candidates.copy()
    if require_s2_larger:
        mask = (
            (legacy["s2_peak_id"] == -1)
            | (legacy["s1_peak_id"] == -1)
            | (legacy["s2_area"] > legacy["s1_area"])
        )
        legacy = legacy[mask]
    plugin = S1S2PairSelectionPlugin()
    plugin._compute_scores(legacy, mode)
    plugin._select_best_pairs(legacy, close_threshold=0.1)
    return legacy[(legacy["s1_peak_id"] >= 0) & (legacy["s2_peak_id"] >= 0)]


@pytest.mark.parametrize("mode", ["nearest", "best_score"])
@pytest.mark.parametrize("require_s2_larger", [True, False])
def test_orphan_does_not_change_complete_pair_score_or_selection(mode, require_s2_larger):
    candidates = _normalization_counterexample_candidates()
    config = {
        "selection_mode": mode,
        "require_s2_larger_than_s1": require_s2_larger,
    }

    expected = _legacy_scored_complete_rows(candidates, mode, require_s2_larger)
    result = S1S2PairSelectionPlugin().compute(_MockContext(candidates, config), "test_run")

    assert np.array_equal(result["pair_id"], expected["pair_id"])
    for field in (
        "score_time",
        "score_s1_quality",
        "score_s2_quality",
        "score_ratio",
        "score_total",
        "delta_score_to_next_best",
    ):
        np.testing.assert_allclose(result[field], expected[field], equal_nan=True)
    np.testing.assert_array_equal(result["rank_for_s2"], expected["rank_for_s2"])
    np.testing.assert_array_equal(result["selected"], expected["selected"])

    selected_pair_id = int(result[result["selected"]][0]["pair_id"])
    assert selected_pair_id == (10 if mode == "nearest" else 11)
