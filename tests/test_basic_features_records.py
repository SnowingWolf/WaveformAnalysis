"""Records-backed and filtered-source BasicFeaturesPlugin tests."""

import numpy as np

from tests.basic_features_helpers import (
    make_basic_feature_context,
    make_basic_feature_waveforms,
    make_records_and_pools,
    make_records_view,
    patch_records_view,
)
from tests.utils import FakeContext
from waveform_analysis.core.plugins.builtin.cpu.basic_features import BasicFeaturesPlugin


class TestWaveSources:
    def test_reads_from_filtered_waveforms(self):
        st = make_basic_feature_waveforms(n=2, wave_length=5)
        ctx = make_basic_feature_context(
            st,
            config={"use_filtered": True, "height_range": (0, 5), "area_range": (0, 5)},
            use_filtered=True,
        )
        result = BasicFeaturesPlugin().compute(ctx, "run_001")

        assert len(result) == 2

    def test_reads_from_records_view_when_wave_source_records(self):
        ctx = FakeContext(
            config={"wave_source": "records", "height_range": (0, 4), "area_range": (0, 4)}
        )
        records_view = make_records_view()

        with patch_records_view(records_view) as mocked:
            result = BasicFeaturesPlugin().compute(ctx, "run_001")

        assert mocked.call_count == 1
        assert len(result) == 2
        assert np.isclose(result["height"][0], 20.0)
        assert np.isclose(result["amp"][0], 15.0)

    def test_records_view_fixed_baseline_uses_normalized_signal(self):
        ctx = FakeContext(
            config={
                "wave_source": "records",
                "height_range": (0, 4),
                "area_range": (0, 4),
                "channel_config": {"channels": {"3:0": {"fixed_baseline": 95.0}}},
            }
        )
        records_view = make_records_view()
        records_view.wave_pool = np.array([95, 100, 115, 95, 90, 85, 90, 90], dtype=np.uint16)

        with patch_records_view(records_view):
            result = BasicFeaturesPlugin().compute(ctx, "run_001")

        assert np.isclose(result["height"][0], 0.0)
        assert np.isclose(result["area"][0], -25.0)

    def test_records_view_propagates_board_field(self):
        ctx = FakeContext(
            config={"wave_source": "records", "height_range": (0, 4), "area_range": (0, 4)}
        )
        with patch_records_view(make_records_view()):
            result = BasicFeaturesPlugin().compute(ctx, "run_001")

        np.testing.assert_array_equal(result["board"], np.array([3, 4], dtype=np.int16))

    def test_records_source_can_select_filtered_wave_pool(self):
        records, wave_pool, wave_pool_filtered = make_records_and_pools()
        ctx = FakeContext(
            config={
                "wave_source": "records",
                "use_filtered": True,
                "height_range": (0, 4),
                "area_range": (0, 4),
            },
            data={
                "records": records,
                "wave_pool": wave_pool,
                "wave_pool_filtered": wave_pool_filtered,
            },
        )
        result = BasicFeaturesPlugin().compute(ctx, "run_001")

        np.testing.assert_allclose(result["height"], [5.0, 5.0])
        np.testing.assert_allclose(result["amp"], [0.0, 0.0])
        np.testing.assert_allclose(result["area"], [20.0, 20.0])
