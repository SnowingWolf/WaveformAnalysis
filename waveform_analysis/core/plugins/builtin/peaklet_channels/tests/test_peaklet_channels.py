import numpy as np
import pytest

from tests.utils import DummyContext, make_hit, make_records
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
from waveform_analysis.core.plugins.builtin.hit.hit_finder import THRESHOLD_HIT_DTYPE
from waveform_analysis.core.plugins.builtin.hit.hit_merge import (
    HIT_MERGED_COMPONENTS_DTYPE,
    HIT_MERGED_DTYPE,
)


def _peaklets(areas, *, component_count=1):
    out = np.zeros(len(areas), dtype=PEAKLET_DTYPE)
    out["component_count"] = component_count
    return out


def _peaklet_features(areas):
    out = np.zeros(len(areas), dtype=PEAKLET_FEATURES_DTYPE)
    out["peak_id"] = np.arange(len(areas), dtype=np.int64)
    out["area"] = np.asarray(areas, dtype=np.float32)
    return out


def _components(pairs):
    out = np.zeros(len(pairs), dtype=PEAKLET_COMPONENTS_DTYPE)
    for i, (peaklet_id, merged_index) in enumerate(pairs):
        out[i]["peak_id"] = peaklet_id
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


def _compute(ctx):
    return PeakletChannelsPlugin()._compute_channels(
        peaklets=ctx._data["peaklets"],
        components=ctx._data["peaklet_components"],
        features=ctx._data["hit_merged_features"],
        peaklet_features=ctx._data["peaklet_features"],
    )


def test_peaklet_channels_single_peaklet_multiple_channels():
    ctx = _ctx(
        _peaklets([100.0], component_count=2),
        _components([(0, 0), (0, 1)]),
        _features(
            [
                {"merged_index": 0, "channel": 0, "area": 60.0, "height": 30.0, "n_hits": 2},
                {"merged_index": 1, "channel": 1, "area": 40.0, "height": 25.0, "n_hits": 1},
            ]
        ),
        _peaklet_features([100.0]),
    )

    out = _compute(ctx)

    assert out.dtype == PEAKLET_CHANNELS_DTYPE
    assert len(out) == 2
    np.testing.assert_array_equal(out["peaklet_id"], np.array([0, 0], dtype=np.int64))
    np.testing.assert_array_equal(out["channel"], np.array([0, 1], dtype=np.int16))
    np.testing.assert_allclose(out["area"], np.array([60.0, 40.0], dtype=np.float32))
    np.testing.assert_array_equal(out["n_hits"], np.array([2, 1], dtype=np.int32))
    np.testing.assert_allclose(out["area_fraction"], np.array([0.6, 0.4], dtype=np.float32))


def test_peaklet_channels_aggregates_multiple_rows_for_same_channel():
    ctx = _ctx(
        _peaklets([50.0], component_count=2),
        _components([(0, 0), (0, 1)]),
        _features(
            [
                {"merged_index": 0, "channel": 3, "area": 20.0, "height": 7.0, "n_hits": 1},
                {"merged_index": 1, "channel": 3, "area": 30.0, "height": 11.0, "n_hits": 2},
            ]
        ),
        _peaklet_features([50.0]),
    )

    out = _compute(ctx)

    assert len(out) == 1
    assert int(out[0]["channel"]) == 3
    assert float(out[0]["area"]) == 50.0
    assert float(out[0]["height"]) == 11.0
    assert int(out[0]["n_hits"]) == 3
    assert float(out[0]["area_fraction"]) == 1.0


def test_peaklet_channels_reconstructs_and_deduplicates_cross_record_waveform():
    peaklets = _peaklets([70.0])
    components = _components([(0, 0)])
    features = _features(
        [{"merged_index": 0, "channel": 3, "area": 100.0, "height": 30.0, "n_hits": 2}]
    )
    peaklet_features = _peaklet_features([70.0])
    merged = np.zeros(1, dtype=HIT_MERGED_DTYPE)
    merged[0]["board"] = 0
    merged[0]["channel"] = 3
    merged[0]["record_id"] = 0
    merged[0]["sample_start"] = -1
    merged[0]["sample_end"] = -1
    merged[0]["is_single_record"] = False
    hits = np.array(
        [
            make_hit(record_id=0, channel=3, edge_start=2, edge_end=4),
            make_hit(record_id=1, channel=3, edge_start=1, edge_end=3),
        ],
        dtype=THRESHOLD_HIT_DTYPE,
    )
    component_hits = np.array([(0, 0), (0, 1)], dtype=HIT_MERGED_COMPONENTS_DTYPE)
    records = make_records(n_records=2, event_length=10, baseline=100.0, dt=2)
    records["timestamp"] = [0, 4000]
    records["polarity"] = "negative"
    wave_pool = np.full(20, 100, dtype=np.uint16)
    wave_pool[[2, 3, 11, 12]] = [80, 80, 80, 70]

    ctx = DummyContext(
        {"wave_source": "records", "use_filtered": False, "clip_negative_signal": False},
        {
            "peaklets": peaklets,
            "peaklet_components": components,
            "hit_merged_features": features,
            "peaklet_features": peaklet_features,
            "hit_merged": merged,
            "hit_merged_components": component_hits,
            "hit_threshold": hits,
            "records": records,
            "wave_pool": wave_pool,
        },
    )
    out = PeakletChannelsPlugin().compute(ctx, "run_001")

    assert float(out[0]["area"]) == 70.0
    assert float(out[0]["height"]) == 30.0
    assert float(out[0]["area_fraction"]) == 1.0


def test_peaklet_channels_rejects_invalid_features_that_break_area_conservation():
    ctx = _ctx(
        _peaklets([50.0, 100.0], component_count=2),
        _components([(1, 3), (0, 2), (1, 1), (0, 0)]),
        _features(
            [
                {
                    "merged_index": 3,
                    "board": 1,
                    "channel": 2,
                    "area": 60.0,
                    "height": 9.0,
                    "n_hits": 2,
                },
                {
                    "merged_index": 2,
                    "board": 0,
                    "channel": 4,
                    "area": 25.0,
                    "height": 4.0,
                    "n_hits": 1,
                },
                {
                    "merged_index": 1,
                    "board": 0,
                    "channel": 1,
                    "area": 40.0,
                    "height": 7.0,
                    "n_hits": 3,
                },
                {
                    "merged_index": 0,
                    "board": 0,
                    "channel": 3,
                    "area": 25.0,
                    "height": 5.0,
                    "n_hits": 1,
                    "valid": 0,
                },
            ]
        ),
        _peaklet_features([50.0, 100.0]),
    )

    with pytest.raises(ValueError, match="area conservation failed"):
        _compute(ctx)


def test_peaklet_channels_zero_peaklet_area_rejects_nonzero_channel_area():
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

    with pytest.raises(ValueError, match="area conservation failed"):
        _compute(ctx)


def test_peaklet_channels_zero_peaklet_area_writes_zero_fractions_when_channels_cancel():
    ctx = _ctx(
        _peaklets([0.0], component_count=2),
        _components([(0, 0), (0, 1)]),
        _features(
            [
                {"merged_index": 0, "channel": 0, "area": 5.0, "height": 2.0, "n_hits": 1},
                {"merged_index": 1, "channel": 1, "area": -5.0, "height": 1.0, "n_hits": 1},
            ]
        ),
        _peaklet_features([0.0]),
    )

    out = _compute(ctx)

    np.testing.assert_array_equal(out["area_fraction"], np.zeros(2, dtype=np.float32))


def test_peaklet_channels_near_zero_nonzero_area_checks_fraction_sum():
    ctx = _ctx(
        _peaklets([1e-6]),
        _components([(0, 0)]),
        _features([{"merged_index": 0, "channel": 0, "area": 2e-6, "height": 1.0, "n_hits": 1}]),
        _peaklet_features([1e-6]),
    )

    with pytest.raises(ValueError, match="fraction conservation failed"):
        _compute(ctx)


def test_peaklet_channels_reject_components_misaligned_with_peaklets():
    peaklets = _peaklets([100.0])
    peaklets[0]["component_count"] = 2
    ctx = _ctx(
        peaklets,
        _components([(0, 0)]),
        _features(
            [
                {"merged_index": 0, "channel": 0, "area": 5.0, "height": 2.0, "n_hits": 1},
            ]
        ),
        _peaklet_features([100.0]),
    )

    with pytest.raises(ValueError, match="inconsistent with peaklets"):
        PeakletChannelsPlugin().compute(ctx, "run_001")
