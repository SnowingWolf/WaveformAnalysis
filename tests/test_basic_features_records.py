"""Records-backed and filtered-source BasicFeaturesPlugin tests."""

import numpy as np
import pytest

from tests.basic_features_helpers import (
    make_basic_feature_context,
    make_basic_feature_waveforms,
    make_records_and_pools,
    make_records_view,
)
from tests.utils import FakeContext
import waveform_analysis.core.plugins.builtin.cpu.basic_features as basic_features_module
from waveform_analysis.core.plugins.builtin.cpu.basic_features import BasicFeaturesPlugin
from waveform_analysis.core.processing.records_builder import RECORDS_DTYPE


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
        records_view = make_records_view()
        ctx = FakeContext(
            config={"wave_source": "records", "height_range": (0, 4), "area_range": (0, 4)},
            data={"records": records_view.records, "wave_pool": records_view.wave_pool},
        )

        result = BasicFeaturesPlugin().compute(ctx, "run_001")

        assert len(result) == 2
        assert np.isclose(result["height"][0], 20.0)
        assert np.isclose(result["amp"][0], 15.0)
        assert np.isclose(result["max_abs_diff"][0], 15.0)

    def test_records_source_prefers_wave_pool_fast_path(self, monkeypatch):
        records_view = make_records_view()
        ctx = FakeContext(
            config={"wave_source": "records", "height_range": (0, 4), "area_range": (0, 4)},
            data={"records": records_view.records, "wave_pool": records_view.wave_pool},
        )
        plugin = BasicFeaturesPlugin()

        def fail_ragged_path(*_args, **_kwargs):
            pytest.fail("records pool fast path should not call ragged fallback")

        monkeypatch.setattr(plugin, "_compute_records_ragged_fast", fail_ragged_path)
        result = plugin.compute(ctx, "run_001")

        np.testing.assert_allclose(result["height"], [20.0, 15.0])
        np.testing.assert_allclose(result["area"], [45.0, 45.0])

    def test_records_pool_fast_path_works_without_numba(self, monkeypatch):
        records_view = make_records_view()
        ctx = FakeContext(
            config={"wave_source": "records", "height_range": (0, 4), "area_range": (0, 4)},
            data={"records": records_view.records, "wave_pool": records_view.wave_pool},
        )
        monkeypatch.setattr(basic_features_module, "NUMBA_AVAILABLE", False)

        result = BasicFeaturesPlugin().compute(ctx, "run_001")

        np.testing.assert_allclose(result["height"], [20.0, 15.0])
        np.testing.assert_allclose(result["amp"], [15.0, 5.0])
        np.testing.assert_allclose(result["area"], [45.0, 45.0])

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
        ctx._data.update({"records": records_view.records, "wave_pool": records_view.wave_pool})

        result = BasicFeaturesPlugin().compute(ctx, "run_001")

        assert np.isclose(result["height"][0], 0.0)
        assert np.isclose(result["area"][0], -25.0)

    def test_records_view_propagates_board_field(self):
        ctx = FakeContext(
            config={"wave_source": "records", "height_range": (0, 4), "area_range": (0, 4)}
        )
        records_view = make_records_view()
        ctx._data.update({"records": records_view.records, "wave_pool": records_view.wave_pool})
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
        np.testing.assert_allclose(result["max_abs_diff"], [0.0, 0.0])

    def test_records_batch_path_preserves_per_record_baseline(self):
        records = np.zeros(3, dtype=RECORDS_DTYPE)
        records["timestamp"] = [10, 20, 30]
        records["board"] = 3
        records["channel"] = 0
        records["record_id"] = [10, 11, 12]
        records["baseline"] = [100.0, 200.0, 300.0]
        records["wave_offset"] = [0, 2, 4]
        records["event_length"] = [2, 2, 2]
        records["polarity"] = "negative"
        records["time"] = [0, 1, 2]
        wave_pool = np.array([90, 90, 90, 90, 90, 90], dtype=np.uint16)
        ctx = FakeContext(
            config={
                "wave_source": "records",
                "height_range": (0, 2),
                "area_range": (0, 2),
                "batch_size": 2,
            },
            data={"records": records, "wave_pool": wave_pool},
        )

        result = BasicFeaturesPlugin().compute(ctx, "run_001")

        np.testing.assert_allclose(result["height"], [10.0, 110.0, 210.0])
        np.testing.assert_allclose(result["area"], [20.0, 220.0, 420.0])

    def test_records_batch_wave_padding_does_not_affect_area(self):
        records = np.zeros(2, dtype=RECORDS_DTYPE)
        records["timestamp"] = [10, 20]
        records["board"] = [3, 3]
        records["channel"] = [0, 0]
        records["record_id"] = [10, 11]
        records["baseline"] = [100.0, 100.0]
        records["wave_offset"] = [0, 4]
        records["event_length"] = [4, 2]
        records["polarity"] = "negative"
        records["time"] = [0, 1]
        wave_pool = np.array([90, 90, 90, 90, 90, 90], dtype=np.uint16)
        ctx = FakeContext(
            config={"wave_source": "records", "height_range": (0, 4), "area_range": (0, None)},
            data={"records": records, "wave_pool": wave_pool},
        )

        result = BasicFeaturesPlugin().compute(ctx, "run_001")

        np.testing.assert_allclose(result["area"], [40.0, 20.0])
