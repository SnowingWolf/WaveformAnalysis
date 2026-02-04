# -*- coding: utf-8 -*-
"""Tests for S1S2ClassifierPlugin."""

from __future__ import annotations

import numpy as np

from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import (
    BASIC_FEATURES_DTYPE,
    LABEL_S1,
    LABEL_S2,
    S1S2ClassifierPlugin,
    WAVEFORM_WIDTH_DTYPE,
)


def _make_widths(channel: int = 0) -> np.ndarray:
    widths = np.zeros(2, dtype=WAVEFORM_WIDTH_DTYPE)
    widths[0]["total_width"] = 30.0
    widths[0]["total_width_samples"] = 15.0
    widths[0]["timestamp"] = 1000
    widths[0]["channel"] = channel
    widths[0]["event_index"] = 0
    widths[0]["peak_position"] = 50

    widths[1]["total_width"] = 400.0
    widths[1]["total_width_samples"] = 200.0
    widths[1]["timestamp"] = 2000
    widths[1]["channel"] = channel
    widths[1]["event_index"] = 1
    widths[1]["peak_position"] = 60
    return widths


def _make_features() -> np.ndarray:
    feats = np.zeros(2, dtype=BASIC_FEATURES_DTYPE)
    feats[0]["height"] = 10.0
    feats[0]["area"] = 50.0
    feats[1]["height"] = 25.0
    feats[1]["area"] = 500.0
    return feats


def test_s1_s2_classifier_basic(tmp_path):
    ctx = Context(storage_dir=str(tmp_path))
    ctx.register(S1S2ClassifierPlugin())

    run_id = "run_001"
    ctx._results[(run_id, "waveform_width")] = [_make_widths()]
    ctx._results[(run_id, "basic_features")] = [_make_features()]

    ctx.set_config(
        {
            "width_unit": "ns",
            "s1_width_range": (0.0, 80.0),
            "s2_width_range": (200.0, None),
            "s1_area_range": (0.0, 120.0),
            "s2_area_range": (200.0, None),
        },
        plugin_name="s1_s2",
    )

    labels = ctx.get_data(run_id, "s1_s2")

    assert len(labels) == 1
    assert len(labels[0]) == 2
    assert labels[0][0]["label"] == LABEL_S1
    assert labels[0][1]["label"] == LABEL_S2
