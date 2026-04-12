"""Configuration-focused BasicFeaturesPlugin tests."""

import numpy as np
import pytest

from tests.basic_features_helpers import (
    make_basic_feature_context,
    make_basic_feature_waveforms,
)
from waveform_analysis.core.plugins.builtin.cpu.basic_features import BasicFeaturesPlugin


@pytest.mark.parametrize(
    ("channel_config", "expected_heights"),
    [
        (None, [10.0, 15.0]),
        ({"channels": {"0:0": {"fixed_baseline": 200.0}}}, [110.0, 15.0]),
        (
            {
                "channels": {
                    "0:0": {"fixed_baseline": 200.0},
                    "0:1": {"fixed_baseline": 150.0},
                }
            },
            [110.0, 65.0],
        ),
    ],
)
def test_fixed_baseline_parametrized(channel_config, expected_heights):
    st = make_basic_feature_waveforms(n=2, wave_length=5, n_channels=2)
    st[0]["wave"][:] = 90
    st[0]["baseline"] = 100.0
    st[0]["channel"] = 0
    st[1]["wave"][:] = 85
    st[1]["baseline"] = 100.0
    st[1]["channel"] = 1

    config = {"height_range": (0, 5), "area_range": (0, 5)}
    if channel_config is not None:
        config["channel_config"] = channel_config

    ctx = make_basic_feature_context(st, config=config)
    result = BasicFeaturesPlugin().compute(ctx, "run_001")

    np.testing.assert_allclose(result["height"], expected_heights)
