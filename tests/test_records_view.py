# -*- coding: utf-8 -*-

import numpy as np

from waveform_analysis.core.data.records_view import RecordsView
from waveform_analysis.core.processing.records_builder import RECORDS_DTYPE


def _make_sample_view():
    records = np.zeros(3, dtype=RECORDS_DTYPE)
    records["timestamp"] = [10, 20, 30]
    records["pid"] = 0
    records["channel"] = [0, 0, 1]
    records["baseline"] = [1.0, 2.0, 0.0]
    records["wave_offset"] = [0, 3, 5]
    records["event_length"] = [3, 2, 1]
    records["time"] = [0, 0, 0]

    wave_pool = np.array([1, 2, 3, 10, 11, 99], dtype=np.uint16)
    return RecordsView(records, wave_pool)


def test_records_view_wave_slicing():
    rv = _make_sample_view()

    wave0 = rv.wave(0)
    assert wave0.dtype == np.uint16
    assert np.array_equal(wave0, np.array([1, 2, 3], dtype=np.uint16))

    wave1 = rv.wave(1, baseline_correct=True)
    assert wave1.dtype == np.float32
    assert np.allclose(wave1, np.array([8.0, 9.0], dtype=np.float32))


def test_records_view_waves_pad_mask():
    rv = _make_sample_view()

    waves, mask = rv.waves([0, 2], pad_to=4, mask=True, dtype=np.float32)
    assert waves.shape == (2, 4)
    assert mask.shape == (2, 4)

    assert np.allclose(waves[0], np.array([1.0, 2.0, 3.0, 0.0], dtype=np.float32))
    assert np.allclose(waves[1], np.array([99.0, 0.0, 0.0, 0.0], dtype=np.float32))

    assert np.array_equal(mask[0], np.array([True, True, True, False]))
    assert np.array_equal(mask[1], np.array([True, False, False, False]))


def test_records_view_query_time_window():
    rv = _make_sample_view()
    subset = rv.query_time_window(t_min=15, t_max=25)
    assert subset.shape == (1,)
    assert subset["timestamp"][0] == 20
