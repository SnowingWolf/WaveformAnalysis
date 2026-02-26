"""Tests for BasicFeaturesPlugin (cpu/basic_features.py)."""

import numpy as np
import pytest

from tests.utils import FakeContext
from waveform_analysis.core.plugins.builtin.cpu.basic_features import (
    BASIC_FEATURES_DTYPE,
    BasicFeaturesPlugin,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_st_waveforms(n=4, wave_length=100, n_channels=2):
    """Create a minimal structured waveform array for testing."""
    dtype = np.dtype([
        ("baseline", "f8"),
        ("timestamp", "i8"),
        ("channel", "i2"),
        ("wave", "i2", (wave_length,)),
    ])
    data = np.zeros(n, dtype=dtype)
    for i in range(n):
        data[i]["baseline"] = 100.0
        data[i]["timestamp"] = i * 1000
        data[i]["channel"] = i % n_channels
        wave = np.full(wave_length, 90, dtype="i2")
        # Place dip/peak at relative positions that fit any wave_length
        mid = wave_length // 2
        wave[mid] = 80       # dip -> height = 100 - 80 = 20
        if mid + 1 < wave_length:
            wave[mid + 1] = 95  # local max
        data[i]["wave"] = wave
    return data


def _ctx_with_waveforms(waveform_data, config=None, use_filtered=False):
    """Build a FakeContext pre-seeded with waveform data.

    Always sets height_range/area_range to (0, None) unless overridden,
    to avoid FeatureDefaults.PEAK_RANGE (40,90) exceeding short test waves.
    """
    cfg = {"height_range": (0, None), "area_range": (0, None)}
    if config:
        cfg.update(config)
    data_key = "filtered_waveforms" if use_filtered else "st_waveforms"
    ctx = FakeContext(config=cfg, data={data_key: waveform_data})
    return ctx


# ---------------------------------------------------------------------------
# BasicFeaturesPlugin.compute – happy path
# ---------------------------------------------------------------------------


class TestBasicFeaturesCompute:
    """Core compute tests."""

    def test_basic_output_shape_and_dtype(self):
        st = _make_st_waveforms(n=4)
        ctx = _ctx_with_waveforms(st)
        plugin = BasicFeaturesPlugin()
        result = plugin.compute(ctx, "run_001")

        assert result.dtype == BASIC_FEATURES_DTYPE
        assert len(result) == 4

    def test_height_and_amp_values(self):
        """height = baseline - min(wave), amp = max - min."""
        st = _make_st_waveforms(n=1, wave_length=10)
        # Craft a specific wave: baseline=100, wave=[90,80,95,90,90,90,90,90,90,90]
        st[0]["wave"][:] = 90
        st[0]["wave"][1] = 80
        st[0]["wave"][2] = 95
        st[0]["baseline"] = 100.0

        ctx = _ctx_with_waveforms(st, config={"height_range": (0, 10), "area_range": (0, 10)})
        plugin = BasicFeaturesPlugin()
        result = plugin.compute(ctx, "run_001")

        assert np.isclose(result["height"][0], 20.0)   # 100 - 80
        assert np.isclose(result["amp"][0], 15.0)       # 95 - 80

    def test_area_calculation(self):
        st = _make_st_waveforms(n=1, wave_length=5)
        st[0]["wave"][:] = [90, 90, 90, 90, 90]
        st[0]["baseline"] = 100.0

        ctx = _ctx_with_waveforms(st, config={"height_range": (0, 5), "area_range": (0, 5)})
        plugin = BasicFeaturesPlugin()
        result = plugin.compute(ctx, "run_001")

        # area = sum(100 - 90) * 5 = 50
        assert np.isclose(result["area"][0], 50.0)

    def test_metadata_fields(self):
        st = _make_st_waveforms(n=3, n_channels=2)
        ctx = _ctx_with_waveforms(st)
        plugin = BasicFeaturesPlugin()
        result = plugin.compute(ctx, "run_001")

        np.testing.assert_array_equal(result["timestamp"], [0, 1000, 2000])
        np.testing.assert_array_equal(result["channel"], [0, 1, 0])
        np.testing.assert_array_equal(result["event_index"], [0, 1, 2])

    def test_empty_input_returns_empty(self):
        st = _make_st_waveforms(n=0)
        ctx = _ctx_with_waveforms(st)
        plugin = BasicFeaturesPlugin()
        result = plugin.compute(ctx, "run_001")

        assert len(result) == 0
        assert result.dtype == BASIC_FEATURES_DTYPE

    def test_single_record(self):
        st = _make_st_waveforms(n=1)
        ctx = _ctx_with_waveforms(st)
        plugin = BasicFeaturesPlugin()
        result = plugin.compute(ctx, "run_001")

        assert len(result) == 1
        assert result["event_index"][0] == 0


# ---------------------------------------------------------------------------
# resolve_depends_on
# ---------------------------------------------------------------------------


class TestResolveDependsOn:
    def test_default_depends_on_st_waveforms(self):
        ctx = FakeContext(config={})
        plugin = BasicFeaturesPlugin()
        assert plugin.resolve_depends_on(ctx) == ["st_waveforms"]

    def test_use_filtered_depends_on_filtered(self):
        ctx = FakeContext(config={"use_filtered": True})
        plugin = BasicFeaturesPlugin()
        assert plugin.resolve_depends_on(ctx) == ["filtered_waveforms"]

    def test_use_filtered_false_explicit(self):
        ctx = FakeContext(config={"use_filtered": False})
        plugin = BasicFeaturesPlugin()
        assert plugin.resolve_depends_on(ctx) == ["st_waveforms"]


# ---------------------------------------------------------------------------
# fixed_baseline override
# ---------------------------------------------------------------------------


class TestFixedBaseline:
    def test_full_override(self):
        st = _make_st_waveforms(n=2, wave_length=5, n_channels=2)
        st[0]["wave"][:] = 90
        st[0]["baseline"] = 100.0
        st[0]["channel"] = 0
        st[1]["wave"][:] = 85
        st[1]["baseline"] = 100.0
        st[1]["channel"] = 1

        ctx = _ctx_with_waveforms(st, config={
            "height_range": (0, 5),
            "area_range": (0, 5),
            "fixed_baseline": {0: 200.0, 1: 150.0},
        })
        plugin = BasicFeaturesPlugin()
        result = plugin.compute(ctx, "run_001")

        # ch0: height = 200 - 90 = 110
        # ch1: height = 150 - 85 = 65
        assert np.isclose(result["height"][0], 110.0)
        assert np.isclose(result["height"][1], 65.0)

    def test_partial_override(self):
        st = _make_st_waveforms(n=2, wave_length=5, n_channels=2)
        st[0]["wave"][:] = 90
        st[0]["baseline"] = 100.0
        st[0]["channel"] = 0
        st[1]["wave"][:] = 85
        st[1]["baseline"] = 100.0
        st[1]["channel"] = 1

        ctx = _ctx_with_waveforms(st, config={
            "height_range": (0, 5),
            "area_range": (0, 5),
            "fixed_baseline": {0: 200.0},  # only ch0
        })
        plugin = BasicFeaturesPlugin()
        result = plugin.compute(ctx, "run_001")

        assert np.isclose(result["height"][0], 110.0)  # overridden
        assert np.isclose(result["height"][1], 15.0)    # original: 100 - 85

    def test_no_fixed_baseline(self):
        st = _make_st_waveforms(n=1, wave_length=5)
        st[0]["wave"][:] = 90
        st[0]["baseline"] = 100.0

        ctx = _ctx_with_waveforms(st, config={
            "height_range": (0, 5),
            "area_range": (0, 5),
        })
        plugin = BasicFeaturesPlugin()
        result = plugin.compute(ctx, "run_001")

        assert np.isclose(result["height"][0], 10.0)  # 100 - 90


# ---------------------------------------------------------------------------
# height_range / area_range configuration
# ---------------------------------------------------------------------------


class TestRangeConfig:
    def test_custom_height_range(self):
        st = _make_st_waveforms(n=1, wave_length=10)
        st[0]["wave"][:] = 90
        st[0]["wave"][3] = 70  # dip at index 3
        st[0]["baseline"] = 100.0

        # height_range covers index 3
        ctx = _ctx_with_waveforms(st, config={
            "height_range": (2, 5),
            "area_range": (0, 10),
        })
        plugin = BasicFeaturesPlugin()
        result = plugin.compute(ctx, "run_001")
        assert np.isclose(result["height"][0], 30.0)  # 100 - 70

    def test_height_range_excludes_dip(self):
        st = _make_st_waveforms(n=1, wave_length=10)
        st[0]["wave"][:] = 90
        st[0]["wave"][3] = 70  # dip at index 3
        st[0]["baseline"] = 100.0

        # height_range does NOT cover index 3
        ctx = _ctx_with_waveforms(st, config={
            "height_range": (5, 10),
            "area_range": (0, 10),
        })
        plugin = BasicFeaturesPlugin()
        result = plugin.compute(ctx, "run_001")
        assert np.isclose(result["height"][0], 10.0)  # 100 - 90

    def test_area_range_subset(self):
        st = _make_st_waveforms(n=1, wave_length=10)
        st[0]["wave"][:] = 90
        st[0]["baseline"] = 100.0

        ctx = _ctx_with_waveforms(st, config={
            "height_range": (0, 10),
            "area_range": (2, 5),  # only 3 samples
        })
        plugin = BasicFeaturesPlugin()
        result = plugin.compute(ctx, "run_001")
        # area = sum(100 - 90) for 3 samples = 30
        assert np.isclose(result["area"][0], 30.0)


# ---------------------------------------------------------------------------
# use_filtered data source
# ---------------------------------------------------------------------------


class TestUseFiltered:
    def test_reads_from_filtered_waveforms(self):
        st = _make_st_waveforms(n=2, wave_length=5)
        ctx = _ctx_with_waveforms(st, config={
            "use_filtered": True,
            "height_range": (0, 5),
            "area_range": (0, 5),
        }, use_filtered=True)
        plugin = BasicFeaturesPlugin()
        result = plugin.compute(ctx, "run_001")
        assert len(result) == 2


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------


class TestErrorPaths:
    def test_non_array_input_raises(self):
        ctx = FakeContext(config={}, data={"st_waveforms": [[1, 2], [3, 4]]})
        plugin = BasicFeaturesPlugin()
        with pytest.raises(ValueError, match="expects st_waveforms as a single structured array"):
            plugin.compute(ctx, "run_001")

    def test_no_channel_field_uses_zeros(self):
        """When dtype has no 'channel' field, channels default to 0."""
        dtype = np.dtype([
            ("baseline", "f8"),
            ("timestamp", "i8"),
            ("wave", "i2", (5,)),
        ])
        data = np.zeros(2, dtype=dtype)
        data["baseline"] = 100.0
        data["wave"][:] = 90
        data["timestamp"] = [0, 1000]

        ctx = FakeContext(
            config={"height_range": (0, 5), "area_range": (0, 5)},
            data={"st_waveforms": data},
        )
        plugin = BasicFeaturesPlugin()
        result = plugin.compute(ctx, "run_001")

        np.testing.assert_array_equal(result["channel"], [0, 0])


# ---------------------------------------------------------------------------
# Parametrized: fixed_baseline scenarios
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("fixed_baseline,expected_heights", [
    (None, [10.0, 15.0]),                   # dynamic baseline
    ({0: 200.0}, [110.0, 15.0]),            # partial override ch0
    ({0: 200.0, 1: 150.0}, [110.0, 65.0]), # full override
])
def test_fixed_baseline_parametrized(fixed_baseline, expected_heights):
    st = _make_st_waveforms(n=2, wave_length=5, n_channels=2)
    st[0]["wave"][:] = 90
    st[0]["baseline"] = 100.0
    st[0]["channel"] = 0
    st[1]["wave"][:] = 85
    st[1]["baseline"] = 100.0
    st[1]["channel"] = 1

    cfg = {"height_range": (0, 5), "area_range": (0, 5)}
    if fixed_baseline is not None:
        cfg["fixed_baseline"] = fixed_baseline

    ctx = _ctx_with_waveforms(st, config=cfg)
    plugin = BasicFeaturesPlugin()
    result = plugin.compute(ctx, "run_001")

    np.testing.assert_allclose(result["height"], expected_heights)
