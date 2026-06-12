import numpy as np

from tests.utils import DummyContext
from waveform_analysis.core.plugins.builtin.cpu.peaklets import (
    PEAKLET_DTYPE,
    PEAKLET_FEATURES_DTYPE,
    PEAKS_DTYPE,
    PeaksPlugin,
)


def test_peaks_merge_peaklet_metadata_and_waveform_features():
    peaklets = np.zeros(1, dtype=PEAKLET_DTYPE)
    peaklets[0]["time_start"] = 6000
    peaklets[0]["time_end"] = 12000
    peaklets[0]["center_time"] = 9000
    peaklets[0]["n_hits"] = 2
    peaklets[0]["n_channels"] = 2

    features = np.zeros(1, dtype=PEAKLET_FEATURES_DTYPE)
    features[0]["peak_id"] = 0
    features[0]["time_start"] = 6000
    features[0]["time_end"] = 12000
    features[0]["time_peak"] = 8000
    features[0]["center_time"] = 9000
    features[0]["area"] = 80.0
    features[0]["height"] = 40.0
    features[0]["width"] = 6.0
    features[0]["rise_time"] = 2.0
    features[0]["fall_time"] = 4.0
    features[0]["range_50p_area"] = 3.0
    features[0]["range_90p_area"] = 5.0

    ctx = DummyContext(
        {},
        {
            "peaklets": peaklets,
            "peaklet_features": features,
            "peaklet_channels": np.zeros(0, dtype=[]),
        },
    )

    out = PeaksPlugin().compute(ctx, "run_001")

    assert out.dtype == PEAKS_DTYPE
    assert len(out) == 1
    assert int(out[0]["peak_id"]) == 0
    assert int(out[0]["time_start"]) == 6000
    assert int(out[0]["time_end"]) == 12000
    assert int(out[0]["time_peak"]) == 8000
    assert int(out[0]["center_time"]) == 9000
    assert float(out[0]["area"]) == 80.0
    assert float(out[0]["height"]) == 40.0
    assert float(out[0]["width"]) == 6.0
    assert float(out[0]["rise_time"]) == 2.0
    assert float(out[0]["fall_time"]) == 4.0
    assert float(out[0]["range_50p_area"]) == 3.0
    assert float(out[0]["range_90p_area"]) == 5.0
    assert int(out[0]["n_hits"]) == 2
    assert int(out[0]["n_channels"]) == 2


def test_peaks_empty_peaklets_return_empty_peaks():
    ctx = DummyContext(
        {},
        {
            "peaklets": np.zeros(0, dtype=PEAKLET_DTYPE),
            "peaklet_features": np.zeros(0, dtype=PEAKLET_FEATURES_DTYPE),
            "peaklet_channels": np.zeros(0, dtype=[]),
        },
    )

    out = PeaksPlugin().compute(ctx, "run_001")

    assert out.dtype == PEAKS_DTYPE
    assert len(out) == 0
