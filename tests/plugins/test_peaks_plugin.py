import numpy as np
import pytest

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
    features[0]["rise_time_10_50"] = 3.0
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
    assert float(out[0]["rise_time_10_50"]) == 3.0
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


def test_peaks_aligns_features_by_peaklet_id_when_unsorted():
    peaklets = np.zeros(2, dtype=PEAKLET_DTYPE)
    peaklets["n_hits"] = [3, 5]
    peaklets["n_channels"] = [2, 4]

    features = np.zeros(2, dtype=PEAKLET_FEATURES_DTYPE)
    features["peak_id"] = [1, 0]
    features["time_start"] = [2000, 1000]
    features["time_end"] = [2600, 1400]
    features["time_peak"] = [2300, 1200]
    features["center_time"] = [2400, 1300]
    features["area"] = [20.0, 10.0]
    features["height"] = [8.0, 4.0]
    features["width"] = [6.0, 4.0]

    ctx = DummyContext(
        {},
        {
            "peaklets": peaklets,
            "peaklet_features": features,
            "peaklet_channels": np.zeros(0, dtype=[]),
        },
    )

    out = PeaksPlugin().compute(ctx, "run_001")

    np.testing.assert_array_equal(out["peak_id"], np.array([0, 1], dtype=np.int64))
    np.testing.assert_array_equal(out["time_start"], np.array([1000, 2000], dtype=np.int64))
    np.testing.assert_allclose(out["area"], np.array([10.0, 20.0], dtype=np.float32))
    np.testing.assert_array_equal(out["n_hits"], np.array([3, 5], dtype=np.int32))


def test_peaks_rejects_missing_peaklet_feature():
    peaklets = np.zeros(2, dtype=PEAKLET_DTYPE)
    features = np.zeros(1, dtype=PEAKLET_FEATURES_DTYPE)
    features[0]["peak_id"] = 0

    ctx = DummyContext(
        {},
        {
            "peaklets": peaklets,
            "peaklet_features": features,
            "peaklet_channels": np.zeros(0, dtype=[]),
        },
    )

    with pytest.raises(ValueError, match="peaklet_id=1"):
        PeaksPlugin().compute(ctx, "run_001")
