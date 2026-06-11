import numpy as np

from tests.utils import DummyContext
from waveform_analysis.core.plugins.builtin.cpu.hit_merged_features import (
    HIT_MERGED_FEATURES_DTYPE,
)
from waveform_analysis.core.plugins.builtin.cpu.peaklet_channels import (
    PEAKLET_CHANNELS_DTYPE,
    PeakletChannelsPlugin,
)
from waveform_analysis.core.plugins.builtin.cpu.peaklets import (
    PEAKLET_COMPONENTS_DTYPE,
    PEAKLET_DTYPE,
    PEAKLET_FEATURES_DTYPE,
)


def _peaklets(areas):
    return np.zeros(len(areas), dtype=PEAKLET_DTYPE)


def _peaklet_features(areas):
    out = np.zeros(len(areas), dtype=PEAKLET_FEATURES_DTYPE)
    out["peaklet_index"] = np.arange(len(areas), dtype=np.int64)
    out["area"] = np.asarray(areas, dtype=np.float32)
    return out


def _components(pairs):
    out = np.zeros(len(pairs), dtype=PEAKLET_COMPONENTS_DTYPE)
    for i, (peaklet_index, merged_index) in enumerate(pairs):
        out[i]["peaklet_index"] = peaklet_index
        out[i]["merged_index"] = merged_index
    return out


def _features(rows):
    out = np.zeros(len(rows), dtype=HIT_MERGED_FEATURES_DTYPE)
    for i, row in enumerate(rows):
        out[i]["merged_index"] = row["merged_index"]
        out[i]["board"] = row.get("board", 0)
        out[i]["channel"] = row["channel"]
        out[i]["area"] = row["area"]
        out[i]["height"] = row["height"]
        out[i]["n_hits"] = row["n_hits"]
        out[i]["valid"] = row.get("valid", 1)
    return out


def _ctx(peaklets, components, features, peaklet_features):
    return DummyContext(
        {},
        {
            "peaklets": peaklets,
            "peaklet_components": components,
            "hit_merged_features": features,
            "peaklet_features": peaklet_features,
        },
    )


def test_peaklet_channels_single_peaklet_multiple_channels():
    ctx = _ctx(
        _peaklets([100.0]),
        _components([(0, 0), (0, 1)]),
        _features(
            [
                {"merged_index": 0, "channel": 0, "area": 60.0, "height": 30.0, "n_hits": 2},
                {"merged_index": 1, "channel": 1, "area": 40.0, "height": 25.0, "n_hits": 1},
            ]
        ),
        _peaklet_features([100.0]),
    )

    out = PeakletChannelsPlugin().compute(ctx, "run_001")

    assert out.dtype == PEAKLET_CHANNELS_DTYPE
    assert len(out) == 2
    np.testing.assert_array_equal(out["peaklet_index"], np.array([0, 0], dtype=np.int64))
    np.testing.assert_array_equal(out["channel"], np.array([0, 1], dtype=np.int16))
    np.testing.assert_allclose(out["area"], np.array([60.0, 40.0], dtype=np.float32))
    np.testing.assert_array_equal(out["n_hits"], np.array([2, 1], dtype=np.int32))
    np.testing.assert_allclose(out["area_fraction"], np.array([0.6, 0.4], dtype=np.float32))


def test_peaklet_channels_aggregates_multiple_rows_for_same_channel():
    ctx = _ctx(
        _peaklets([50.0]),
        _components([(0, 0), (0, 1)]),
        _features(
            [
                {"merged_index": 0, "channel": 3, "area": 20.0, "height": 7.0, "n_hits": 1},
                {"merged_index": 1, "channel": 3, "area": 30.0, "height": 11.0, "n_hits": 2},
            ]
        ),
        _peaklet_features([50.0]),
    )

    out = PeakletChannelsPlugin().compute(ctx, "run_001")

    assert len(out) == 1
    assert int(out[0]["channel"]) == 3
    assert float(out[0]["area"]) == 50.0
    assert float(out[0]["height"]) == 11.0
    assert int(out[0]["n_hits"]) == 3
    assert float(out[0]["area_fraction"]) == 1.0


def test_peaklet_channels_zero_peaklet_area_writes_zero_fraction():
    ctx = _ctx(
        _peaklets([0.0]),
        _components([(0, 0)]),
        _features(
            [
                {"merged_index": 0, "channel": 0, "area": 5.0, "height": 2.0, "n_hits": 1},
            ]
        ),
        _peaklet_features([0.0]),
    )

    out = PeakletChannelsPlugin().compute(ctx, "run_001")

    assert len(out) == 1
    assert float(out[0]["area_fraction"]) == 0.0
