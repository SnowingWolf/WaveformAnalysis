import numpy as np
import pytest

from tests.utils import DummyContext
from waveform_analysis.core.plugins.builtin.cpu.hit_merged_features import HIT_MERGED_FEATURES_DTYPE
from waveform_analysis.core.plugins.builtin.cpu.peaklets import (
    PEAKLET_DTYPE,
    PEAKLET_FEATURES_DTYPE,
    PEAKLET_WAVEFORMS_DTYPE,
    PeakletFeaturesPlugin,
)
from waveform_analysis.core.plugins.builtin.peaklet_features import plugin as feature_module
from waveform_analysis.core.plugins.builtin.peaklets._compute import (
    _compute_area_quantile_times,
)


def _peaklets(n):
    out = np.zeros(n, dtype=PEAKLET_DTYPE)
    out["time_start"] = [0] * n
    out["time_end"] = [0] * n
    return out


def _waveforms(rows):
    out = np.zeros(len(rows), dtype=PEAKLET_WAVEFORMS_DTYPE)
    for i, row in enumerate(rows):
        for name, value in row.items():
            out[i][name] = value
    return out


def test_compute_area_quantile_times_returns_fixed_order_array():
    wave = np.array([0, 10, 20, 30, 40, 50, 40, 30, 20, 10, 0], dtype=np.float32)

    times = _compute_area_quantile_times(wave, time_start=0, dt_ns=1)

    assert times.dtype == np.int64
    assert times.tolist() == [1125, 1750, 3062, 4500, 5937, 7250, 7875]


def test_compute_area_quantile_times_handles_empty_and_non_positive_area():
    assert (
        _compute_area_quantile_times(np.array([], dtype=np.float32), 1234, 2).tolist() == [1234] * 7
    )
    assert (
        _compute_area_quantile_times(np.zeros(3, dtype=np.float32), 1234, 2).tolist() == [1234] * 7
    )


def test_compute_area_quantile_times_handles_zero_area_plateaus():
    wave = np.array([0, 0, 10, 0, 10, 0], dtype=np.float32)

    times = _compute_area_quantile_times(wave, time_start=1000, dt_ns=2)

    assert times.tolist() == [3200, 3400, 4000, 5000, 8000, 8600, 8800]


def test_peaklet_features_derive_waveform_fields_from_ragged_pool():
    waveforms = _waveforms(
        [
            {
                "peak_id": 0,
                "time_start": 6000,
                "time_end": 12000,
                "dt": 2,
                "wave_offset": 0,
                "wave_length": 3,
            }
        ]
    )
    ctx = DummyContext(
        {},
        {
            "peaklets": _peaklets(1),
            "peaklet_waveforms": waveforms,
            "peaklet_waveform_pool": np.array([20.0, 40.0, 20.0], dtype=np.float32),
        },
    )

    out = PeakletFeaturesPlugin().compute(ctx, "run_001")

    assert out.dtype == PEAKLET_FEATURES_DTYPE
    assert len(out) == 1
    assert int(out[0]["peak_id"]) == 0

    # Derived time fields.
    assert int(out[0]["time_start"]) == 6000
    assert int(out[0]["time_end"]) == 12000
    assert int(out[0]["time_peak"]) == 8000

    # Basic waveform features.
    assert float(out[0]["area"]) == 80.0
    assert float(out[0]["height"]) == 40.0
    assert float(out[0]["width"]) == 6.0

    # Cumulative-area quantile features for wave [20, 40, 20].
    center_time = int(out[0]["center_time"])
    assert 6000 < center_time < 10000

    # Rise/fall and ranges are derived from cumulative-area quantiles.
    assert float(out[0]["rise_time"]) > 0.0
    assert float(out[0]["fall_time"]) > 0.0
    assert float(out[0]["width_25_75"]) > 0.0
    assert float(out[0]["rise_time_10_50"]) > 0.0
    assert float(out[0]["range_90p_area"]) > 0.0


def test_peaklet_features_preserves_signed_area_and_first_quantile_crossing():
    waveforms = _waveforms(
        [
            {
                "peak_id": 0,
                "time_start": 0,
                "time_end": 4000,
                "dt": 1,
                "wave_offset": 0,
                "wave_length": 4,
            }
        ]
    )
    wave = np.array([10.0, -8.0, 10.0, -2.0], dtype=np.float32)
    ctx = DummyContext(
        {},
        {
            "peaklets": _peaklets(1),
            "peaklet_waveforms": waveforms,
            "peaklet_waveform_pool": wave,
        },
    )

    out = PeakletFeaturesPlugin().compute(ctx, "run_001")

    assert float(out[0]["area"]) == float(np.sum(wave)) == 10.0
    assert int(out[0]["center_time"]) == 0


def test_peaklet_features_nonpositive_signed_area_is_not_rewritten_to_zero():
    waveforms = _waveforms(
        [
            {
                "peak_id": 0,
                "time_start": 5000,
                "time_end": 8000,
                "dt": 1,
                "wave_offset": 0,
                "wave_length": 3,
            }
        ]
    )
    ctx = DummyContext(
        {},
        {
            "peaklets": _peaklets(1),
            "peaklet_waveforms": waveforms,
            "peaklet_waveform_pool": np.array([-2.0, 1.0, -3.0], dtype=np.float32),
        },
    )

    out = PeakletFeaturesPlugin().compute(ctx, "run_001")

    assert float(out[0]["area"]) == -4.0
    assert float(out[0]["height"]) == 1.0
    assert int(out[0]["center_time"]) == 5000
    assert int(out[0]["time_peak"]) == 6000


def test_peaklet_features_numba_nonpositive_branch_matches_python(monkeypatch):
    wave = np.array([-2.0, 1.0, -3.0], dtype=np.float32)
    waveforms = _waveforms(
        [
            {
                "peak_id": i,
                "time_start": 5000 + i * 10_000,
                "time_end": 8000 + i * 10_000,
                "dt": 1,
                "wave_offset": i * len(wave),
                "wave_length": len(wave),
            }
            for i in range(11)
        ]
    )
    data = {
        "peaklets": _peaklets(11),
        "peaklet_waveforms": waveforms,
        "peaklet_waveform_pool": np.tile(wave, 11),
    }

    optimized = PeakletFeaturesPlugin().compute(DummyContext({}, data), "run_001")
    monkeypatch.setattr(feature_module, "HAS_NUMBA", False)
    reference = PeakletFeaturesPlugin().compute(DummyContext({}, data), "run_001")

    for field in PEAKLET_FEATURES_DTYPE.names:
        np.testing.assert_array_equal(optimized[field], reference[field], err_msg=field)


def test_peaklet_features_rise_is_peak_based_fall_and_width_are_area_based():
    waveforms = _waveforms(
        [
            {
                "peak_id": 0,
                "time_start": 0,
                "time_end": 11000,
                "dt": 1,
                "wave_offset": 0,
                "wave_length": 11,
            }
        ]
    )
    ctx = DummyContext(
        {},
        {
            "peaklets": _peaklets(1),
            "peaklet_waveforms": waveforms,
            "peaklet_waveform_pool": np.array(
                [0, 10, 20, 30, 40, 50, 40, 30, 20, 10, 0],
                dtype=np.float32,
            ),
        },
    )

    out = PeakletFeaturesPlugin().compute(ctx, "run_001")

    assert int(out[0]["time_peak"]) == 5000
    assert int(out[0]["center_time"]) == 4500
    assert float(out[0]["rise_time"]) == 3.25
    assert float(out[0]["fall_time"]) == 2.75
    assert float(out[0]["width_25_75"]) == 2.875
    assert float(out[0]["rise_time_10_50"]) == 2.75


def test_peaklet_features_numba_path_matches_area_rise_time_field():
    waveforms = _waveforms(
        [
            {
                "peak_id": i,
                "time_start": 0,
                "time_end": 11000,
                "dt": 1,
                "wave_offset": i * 11,
                "wave_length": 11,
            }
            for i in range(11)
        ]
    )
    wave = np.array([0, 10, 20, 30, 40, 50, 40, 30, 20, 10, 0], dtype=np.float32)
    ctx = DummyContext(
        {},
        {
            "peaklets": _peaklets(11),
            "peaklet_waveforms": waveforms,
            "peaklet_waveform_pool": np.tile(wave, 11),
        },
    )

    out = PeakletFeaturesPlugin().compute(ctx, "run_001")

    assert len(out) == 11
    assert float(out[0]["rise_time_10_50"]) == 2.75
    assert "range_50p_area" not in out.dtype.names


def test_peaklet_features_numba_output_exactly_matches_python_dtype_and_values(monkeypatch):
    wave = np.array([0, 10, 20, 30, 40, 50, 40, 30, 20, 10, 0], dtype=np.float32)
    waveforms = _waveforms(
        [
            {
                "peak_id": i,
                "time_start": i * 100000,
                "time_end": i * 100000 + 11000,
                "dt": 1,
                "wave_offset": i * len(wave),
                "wave_length": len(wave),
            }
            for i in range(11)
        ]
    )
    data = {
        "peaklets": _peaklets(11),
        "peaklet_waveforms": waveforms,
        "peaklet_waveform_pool": np.tile(wave, 11),
    }

    optimized = PeakletFeaturesPlugin().compute(DummyContext({}, data), "run_001")
    monkeypatch.setattr(feature_module, "HAS_NUMBA", False)
    reference = PeakletFeaturesPlugin().compute(DummyContext({}, data), "run_001")

    assert optimized.dtype == PEAKLET_FEATURES_DTYPE
    assert reference.dtype == PEAKLET_FEATURES_DTYPE
    for field in PEAKLET_FEATURES_DTYPE.names:
        np.testing.assert_array_equal(optimized[field], reference[field], err_msg=field)


def test_peaklet_features_numba_matches_python_for_signed_nonmonotonic_cumsum(monkeypatch):
    wave = np.array([10, -8, 10, -2, 5, -4, 10, -3, 1, -1, 2], dtype=np.float32)
    waveforms = _waveforms(
        [
            {
                "peak_id": i,
                "time_start": i * 100_000,
                "time_end": i * 100_000 + 11_000,
                "dt": 1,
                "wave_offset": i * len(wave),
                "wave_length": len(wave),
            }
            for i in range(11)
        ]
    )
    data = {
        "peaklets": _peaklets(11),
        "peaklet_waveforms": waveforms,
        "peaklet_waveform_pool": np.tile(wave, 11),
    }

    optimized = PeakletFeaturesPlugin().compute(DummyContext({}, data), "run_001")
    monkeypatch.setattr(feature_module, "HAS_NUMBA", False)
    reference = PeakletFeaturesPlugin().compute(DummyContext({}, data), "run_001")

    for field in PEAKLET_FEATURES_DTYPE.names:
        np.testing.assert_array_equal(optimized[field], reference[field], err_msg=field)


def test_peaklet_features_numba_matches_python_for_long_float32_waveform(monkeypatch):
    rng = np.random.default_rng(20260817)
    wave = rng.normal(loc=2.0, scale=20.0, size=10_000).astype(np.float32)
    waveforms = _waveforms(
        [
            {
                "peak_id": i,
                "time_start": i * 20_000_000,
                "time_end": i * 20_000_000 + len(wave) * 1000,
                "dt": 1,
                "wave_offset": i * len(wave),
                "wave_length": len(wave),
            }
            for i in range(11)
        ]
    )
    data = {
        "peaklets": _peaklets(11),
        "peaklet_waveforms": waveforms,
        "peaklet_waveform_pool": np.tile(wave, 11),
    }

    optimized = PeakletFeaturesPlugin().compute(DummyContext({}, data), "run_001")
    monkeypatch.setattr(feature_module, "HAS_NUMBA", False)
    reference = PeakletFeaturesPlugin().compute(DummyContext({}, data), "run_001")

    for field in PEAKLET_FEATURES_DTYPE.names:
        np.testing.assert_array_equal(optimized[field], reference[field], err_msg=field)


def test_peaklet_features_empty_waveforms_return_empty_features():
    ctx = DummyContext(
        {},
        {
            "peaklets": _peaklets(0),
            "peaklet_waveforms": np.zeros(0, dtype=PEAKLET_WAVEFORMS_DTYPE),
            "peaklet_waveform_pool": np.zeros(0, dtype=np.float32),
        },
    )

    out = PeakletFeaturesPlugin().compute(ctx, "run_001")

    assert out.dtype == PEAKLET_FEATURES_DTYPE
    assert len(out) == 0


def test_peaklet_channels_rejects_fraction_when_channel_area_is_incomplete():
    from waveform_analysis.core.plugins.builtin.cpu.peaklet_channels import PeakletChannelsPlugin
    from waveform_analysis.core.plugins.builtin.cpu.peaklets import PEAKLET_COMPONENTS_DTYPE

    peaklets = _peaklets(1)
    peaklets[0]["component_count"] = 1
    components = np.zeros(1, dtype=PEAKLET_COMPONENTS_DTYPE)
    components[0]["peak_id"] = 0
    components[0]["merged_index"] = 0
    hit_features = np.zeros(1, dtype=HIT_MERGED_FEATURES_DTYPE)
    hit_features[0]["merged_index"] = 0
    hit_features[0]["channel"] = 0
    hit_features[0]["area"] = 25.0
    hit_features[0]["height"] = 10.0
    hit_features[0]["n_hits"] = 1
    hit_features[0]["valid"] = 1
    peaklet_features = np.zeros(1, dtype=PEAKLET_FEATURES_DTYPE)
    peaklet_features[0]["peak_id"] = 0
    peaklet_features[0]["area"] = 100.0
    with pytest.raises(ValueError, match="area conservation failed"):
        PeakletChannelsPlugin()._compute_channels(
            peaklets=peaklets,
            components=components,
            features=hit_features,
            peaklet_features=peaklet_features,
        )
