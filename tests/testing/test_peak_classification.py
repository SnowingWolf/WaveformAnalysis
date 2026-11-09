"""Tests for the opt-in experimental peak-classification plugin."""

from __future__ import annotations

import numpy as np

from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.peaks import PEAKS_DTYPE
from waveform_analysis.testing.peak_classification import (
    HEIGHT_PER_AREA_ADC_CUT,
    HeightAreaLinePeakClassificationPlugin,
)


def _peaks(n: int) -> np.ndarray:
    peaks = np.zeros(n, dtype=PEAKS_DTYPE)
    peaks["peak_id"] = np.arange(n)
    peaks["area"] = 100.0
    peaks["height"] = 1.0
    peaks["rise_time"] = 1.0
    peaks["rise_time_10_50"] = 50.0
    return peaks


def test_line_and_negative_rise_rules_are_strict_and_non_mutating():
    peaks = _peaks(8)
    peaks["area"] = [100, 100, 155 * 999, 155 * 1001, 100, 100, 155 * 1000, 100]
    peaks["height"] = [30001, 29999, 29999, 29999, 30000, 29999, 29999, 4]
    peaks["rise_time"] = -1
    peaks["rise_time"][7] = 1
    peaks["rise_time_10_50"] = [50, 99, 101, 101, 50, 100, 101, 50]

    classification = np.zeros(8, dtype=[("peak_id", "i8"), ("label", "i1")])
    classification["peak_id"] = peaks["peak_id"]
    classification["label"] = 2

    result = HeightAreaLinePeakClassificationPlugin.apply_line_override(
        peaks, classification, threshold=HEIGHT_PER_AREA_ADC_CUT
    )

    assert result.dtype == classification.dtype
    assert result["label"].tolist() == [3, 1, 2, 2, 1, 1, 1, 2]
    assert classification["label"].tolist() == [2] * 8


def test_plugin_can_explicitly_override_builtin_and_preserves_contract(tmp_path):
    ctx = Context(storage_dir=str(tmp_path))
    plugin = HeightAreaLinePeakClassificationPlugin()
    ctx.register(plugin)

    peaks = _peaks(2)
    peaks["area"] = [100.0, 100.0]
    peaks["height"] = [10.0, 1.0]
    peaks["width"] = [50.0, 150.0]
    run_id = "run_001"
    ctx._results[(run_id, "peaks")] = peaks
    ctx.set_config(
        {
            "s1_s2_selection": {"accept_any": [{"width": (100.0, 200.0)}]},
            "priority_order": ["s1_s2", "s1", "s2"],
        },
        plugin_name="peak_classification",
    )

    result = ctx.get_data(run_id, "peak_classification")

    assert ctx._plugins["peak_classification"] is plugin
    assert plugin.provides == "peak_classification"
    assert plugin.depends_on == ["peaks"]
    assert plugin.version == "1.5.0.dev2"
    assert result.dtype == plugin.output_dtype
    assert result["label"].tolist() == [1, 2]
