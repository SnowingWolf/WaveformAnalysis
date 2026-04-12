from unittest.mock import patch

import numpy as np
import pytest

from tests.utils import FakeContext
from waveform_analysis.core.context import Context
from waveform_analysis.core.data.records_view import RecordsView, records_view
from waveform_analysis.core.plugins import profiles
from waveform_analysis.core.processing.records_builder import RECORDS_DTYPE


def _make_sample_view():
    records = np.zeros(3, dtype=RECORDS_DTYPE)
    records["timestamp"] = [10, 20, 30]
    records["pid"] = 0
    records["channel"] = [0, 0, 1]
    records["record_id"] = [10, 11, 12]
    records["baseline"] = [1.0, 2.0, 0.0]
    records["polarity"] = ["positive", "negative", "unknown"]
    records["wave_offset"] = [0, 3, 5]
    records["event_length"] = [3, 2, 1]
    records["time"] = [0, 0, 0]

    wave_pool = np.array([1, 2, 3, 10, 11, 99], dtype=np.uint16)
    return RecordsView(records, wave_pool)


def _make_records() -> np.ndarray:
    records = np.zeros(2, dtype=RECORDS_DTYPE)
    records["record_id"] = np.array([11, 12], dtype=np.int64)
    records["timestamp"] = np.array([100, 200], dtype=np.int64)
    records["board"] = 0
    records["channel"] = np.array([1, 2], dtype=np.int16)
    records["baseline"] = 100.0
    records["polarity"] = "negative"
    records["dt"] = 2
    records["wave_offset"] = np.array([0, 4], dtype=np.int64)
    records["event_length"] = 4
    return records


def test_records_view_wave_slicing():
    rv = _make_sample_view()

    wave0 = rv.waves(10)
    assert wave0.dtype == np.uint16
    assert np.array_equal(wave0, np.array([1, 2, 3], dtype=np.uint16))

    wave1 = rv.waves(11, baseline_correct=True)
    assert wave1.dtype == np.float32
    assert np.allclose(wave1, np.array([8.0, 9.0], dtype=np.float32))


def test_records_view_waves_pad_mask():
    rv = _make_sample_view()

    waves, mask = rv.waves([10, 12], pad_to=4, mask=True, dtype=np.float32)
    assert waves.shape == (2, 4)
    assert mask.shape == (2, 4)

    assert np.allclose(waves[0], np.array([1.0, 2.0, 3.0, 0.0], dtype=np.float32))
    assert np.allclose(waves[1], np.array([99.0, 0.0, 0.0, 0.0], dtype=np.float32))

    assert np.array_equal(mask[0], np.array([True, True, True, False]))
    assert np.array_equal(mask[1], np.array([True, False, False, False]))


def test_records_view_wave_unified_batch_access():
    rv = _make_sample_view()

    waves, mask = rv.waves([10, 12], pad_to=4, mask=True, dtype=np.float32)
    assert waves.shape == (2, 4)
    assert mask.shape == (2, 4)
    assert np.allclose(waves[0], np.array([1.0, 2.0, 3.0, 0.0], dtype=np.float32))
    assert np.array_equal(mask[1], np.array([True, False, False, False]))


def test_records_view_query_time_window():
    rv = _make_sample_view()
    subset = rv.query_time_window(t_min=15, t_max=25)
    assert subset.shape == (1,)
    assert subset["timestamp"][0] == 20


def test_records_view_record_windows():
    rv = _make_sample_view()
    wave = rv.waves(10, sample_start=1, sample_end=3)
    signal = rv.signals(11, sample_start=0, sample_end=2)

    assert np.array_equal(wave, np.array([2, 3], dtype=np.uint16))
    assert np.allclose(signal, np.array([8.0, 9.0], dtype=np.float32))


def test_records_view_signal_normalizes_to_negative_pulses():
    rv = _make_sample_view()

    signal0 = rv.signals(10)
    signal1 = rv.signals(11)
    signal2 = rv.signals(12)

    assert np.allclose(signal0, np.array([0.0, -1.0, -2.0], dtype=np.float32))
    assert np.allclose(signal1, np.array([8.0, 9.0], dtype=np.float32))
    assert np.allclose(signal2, np.array([99.0], dtype=np.float32))


def test_records_view_signal_supports_baseline_override():
    rv = _make_sample_view()

    signal = rv.signals(10, baseline=2.0)

    assert np.allclose(signal, np.array([1.0, 0.0, -1.0], dtype=np.float32))


def test_records_view_signals_pad_mask():
    rv = _make_sample_view()

    signals, mask = rv.signals([10, 11], pad_to=4, mask=True)

    assert signals.shape == (2, 4)
    assert np.allclose(
        signals,
        np.array(
            [
                [0.0, -1.0, -2.0, 0.0],
                [8.0, 9.0, 0.0, 0.0],
            ],
            dtype=np.float32,
        ),
    )
    assert np.array_equal(
        mask,
        np.array(
            [
                [True, True, True, False],
                [True, True, False, False],
            ]
        ),
    )


def test_records_view_uses_records_branch_with_cpu_default():
    ctx = Context()
    ctx.register(*profiles.cpu_default())

    records = np.zeros(1, dtype=RECORDS_DTYPE)
    records["timestamp"] = [10]
    records["pid"] = 0
    records["channel"] = [0]
    records["record_id"] = [100]
    records["baseline"] = [1.0]
    records["wave_offset"] = [0]
    records["event_length"] = [1]
    records["time"] = [0]
    wave_pool = np.array([7], dtype=np.uint16)
    with patch.object(ctx, "get_data", side_effect=[records, wave_pool]) as mocked:
        rv = records_view(ctx, "run_001")

    assert isinstance(rv, RecordsView)
    assert mocked.call_count == 2
    assert len(rv) == 1
    assert int(rv.waves(100)[0]) == 7


def test_records_view_requires_formal_wave_pool_output():
    records = np.zeros(1, dtype=RECORDS_DTYPE)
    records["timestamp"] = [10]
    records["pid"] = 0
    records["channel"] = [0]
    records["record_id"] = [100]
    records["baseline"] = [1.0]
    records["wave_offset"] = [0]
    records["event_length"] = [1]
    records["time"] = [0]
    ctx = Context()

    with patch.object(ctx, "get_data", side_effect=[records, None]) as get_data_mock:
        with pytest.raises(ValueError, match="wave_pool"):
            records_view(ctx, "run_001")

    assert get_data_mock.call_count == 2


def test_records_view_supports_custom_wave_pool_name():
    records = _make_records()
    ctx = FakeContext(
        data={
            "records": records,
            "wave_pool": np.array([100, 90, 95, 100, 100, 95, 90, 100], dtype=np.uint16),
            "wave_pool_filtered": np.array(
                [99.0, 98.0, 97.0, 96.0, 95.0, 94.0, 93.0, 92.0], dtype=np.float32
            ),
        }
    )

    rv = records_view(ctx, "run_001", wave_pool_name="wave_pool_filtered")

    np.testing.assert_allclose(rv.waves(11), [99.0, 98.0, 97.0, 96.0])


def test_records_view_missing_custom_wave_pool_raises():
    records = _make_records()
    ctx = FakeContext(data={"records": records})

    with pytest.raises(ValueError, match="wave_pool_filtered"):
        records_view(ctx, "run_001", wave_pool_name="wave_pool_filtered")


def test_records_view_batch_window_uses_record_ids():
    rv = _make_sample_view()

    waves, mask = rv.waves([10, 11], sample_start=1, sample_end=3, pad_to=3, mask=True)

    assert np.array_equal(
        waves,
        np.array(
            [
                [2, 3, 0],
                [11, 0, 0],
            ],
            dtype=np.uint16,
        ),
    )
    assert np.array_equal(
        mask,
        np.array(
            [
                [True, True, False],
                [True, False, False],
            ]
        ),
    )


def test_records_view_rejects_duplicate_record_ids():
    records = np.zeros(2, dtype=RECORDS_DTYPE)
    records["record_id"] = [10, 10]
    records["timestamp"] = [0, 1]
    records["wave_offset"] = [0, 1]
    records["event_length"] = [1, 1]
    records["baseline"] = [0.0, 0.0]

    with pytest.raises(ValueError, match="record_id"):
        RecordsView(records, np.array([1, 2], dtype=np.uint16))


def test_records_view_rejects_out_of_bounds_wave_reference():
    records = np.zeros(1, dtype=RECORDS_DTYPE)
    records["record_id"] = [10]
    records["timestamp"] = [0]
    records["wave_offset"] = [1]
    records["event_length"] = [2]
    records["baseline"] = [0.0]

    with pytest.raises(ValueError, match="wave_pool"):
        RecordsView(records, np.array([1, 2], dtype=np.uint16))
