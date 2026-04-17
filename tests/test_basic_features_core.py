"""Core BasicFeaturesPlugin behavior tests."""

import numpy as np
import pytest

from tests.basic_features_helpers import (
    make_basic_feature_context,
    make_basic_feature_waveforms,
)
from waveform_analysis.core.plugins.builtin.cpu.basic_features import (
    BASIC_FEATURES_DTYPE,
    BasicFeaturesPlugin,
)


class TestBasicFeaturesCompute:
    def test_basic_output_shape_and_dtype(self):
        st = make_basic_feature_waveforms(n=4)
        ctx = make_basic_feature_context(st)
        result = BasicFeaturesPlugin().compute(ctx, "run_001")

        assert result.dtype == BASIC_FEATURES_DTYPE
        assert len(result) == 4

    def test_height_and_amp_values(self):
        st = make_basic_feature_waveforms(n=1, wave_length=10)
        st[0]["wave"][:] = 90
        st[0]["wave"][1] = 80
        st[0]["wave"][2] = 95
        st[0]["baseline"] = 100.0

        ctx = make_basic_feature_context(
            st,
            config={"height_range": (0, 10), "area_range": (0, 10)},
        )
        result = BasicFeaturesPlugin().compute(ctx, "run_001")

        assert np.isclose(result["height"][0], 20.0)
        assert np.isclose(result["amp"][0], 15.0)

    def test_area_calculation(self):
        st = make_basic_feature_waveforms(n=1, wave_length=5)
        st[0]["wave"][:] = [90, 90, 90, 90, 90]
        st[0]["baseline"] = 100.0

        ctx = make_basic_feature_context(
            st,
            config={"height_range": (0, 5), "area_range": (0, 5)},
        )
        result = BasicFeaturesPlugin().compute(ctx, "run_001")

        assert np.isclose(result["area"][0], 50.0)

    def test_max_abs_diff_calculation(self):
        st = make_basic_feature_waveforms(n=1, wave_length=6)
        st[0]["wave"][:] = [100, 96, 82, 95, 94, 110]
        st[0]["baseline"] = 100.0

        ctx = make_basic_feature_context(
            st,
            config={"height_range": (0, 6), "area_range": (0, 6)},
        )
        result = BasicFeaturesPlugin().compute(ctx, "run_001")

        assert np.isclose(result["max_abs_diff"][0], 16.0)

    def test_metadata_fields(self):
        st = make_basic_feature_waveforms(n=3, n_channels=2)
        ctx = make_basic_feature_context(st)
        result = BasicFeaturesPlugin().compute(ctx, "run_001")

        np.testing.assert_array_equal(result["timestamp"], [0, 1000, 2000])
        np.testing.assert_array_equal(result["channel"], [0, 1, 0])
        np.testing.assert_array_equal(result["event_index"], [0, 1, 2])

    def test_empty_input_returns_empty(self):
        st = make_basic_feature_waveforms(n=0)
        ctx = make_basic_feature_context(st)
        result = BasicFeaturesPlugin().compute(ctx, "run_001")

        assert len(result) == 0
        assert result.dtype == BASIC_FEATURES_DTYPE

    def test_single_record(self):
        st = make_basic_feature_waveforms(n=1)
        ctx = make_basic_feature_context(st)
        result = BasicFeaturesPlugin().compute(ctx, "run_001")

        assert len(result) == 1
        assert result["event_index"][0] == 0

    def test_single_sample_wave_has_zero_max_abs_diff(self):
        st = make_basic_feature_waveforms(n=1, wave_length=1)
        st[0]["wave"][:] = [90]
        ctx = make_basic_feature_context(st)
        result = BasicFeaturesPlugin().compute(ctx, "run_001")

        assert np.isclose(result["max_abs_diff"][0], 0.0)


class TestRangeConfig:
    def test_custom_height_range(self):
        st = make_basic_feature_waveforms(n=1, wave_length=10)
        st[0]["wave"][:] = 90
        st[0]["wave"][3] = 70
        st[0]["baseline"] = 100.0

        ctx = make_basic_feature_context(
            st,
            config={"height_range": (2, 5), "area_range": (0, 10)},
        )
        result = BasicFeaturesPlugin().compute(ctx, "run_001")

        assert np.isclose(result["height"][0], 30.0)

    def test_height_range_excludes_dip(self):
        st = make_basic_feature_waveforms(n=1, wave_length=10)
        st[0]["wave"][:] = 90
        st[0]["wave"][3] = 70
        st[0]["baseline"] = 100.0

        ctx = make_basic_feature_context(
            st,
            config={"height_range": (5, 10), "area_range": (0, 10)},
        )
        result = BasicFeaturesPlugin().compute(ctx, "run_001")

        assert np.isclose(result["height"][0], 10.0)

    def test_area_range_subset(self):
        st = make_basic_feature_waveforms(n=1, wave_length=10)
        st[0]["wave"][:] = 90
        st[0]["baseline"] = 100.0

        ctx = make_basic_feature_context(
            st,
            config={"height_range": (0, 10), "area_range": (2, 5)},
        )
        result = BasicFeaturesPlugin().compute(ctx, "run_001")

        assert np.isclose(result["area"][0], 30.0)


class TestErrorPaths:
    def test_non_array_input_raises(self):
        ctx = make_basic_feature_context(None)
        ctx._data["st_waveforms"] = [[1, 2], [3, 4]]

        with pytest.raises(ValueError, match="expects st_waveforms as a single structured array"):
            BasicFeaturesPlugin().compute(ctx, "run_001")

    def test_no_channel_field_uses_zeros(self):
        dtype = np.dtype(
            [
                ("baseline", "f8"),
                ("timestamp", "i8"),
                ("wave", "i2", (5,)),
            ]
        )
        data = np.zeros(2, dtype=dtype)
        data["baseline"] = 100.0
        data["wave"][:] = 90
        data["timestamp"] = [0, 1000]

        ctx = make_basic_feature_context(
            data,
            config={"height_range": (0, 5), "area_range": (0, 5)},
        )
        result = BasicFeaturesPlugin().compute(ctx, "run_001")

        np.testing.assert_array_equal(result["channel"], [0, 0])
