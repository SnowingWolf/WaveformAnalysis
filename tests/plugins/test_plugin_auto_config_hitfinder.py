from unittest.mock import patch

import numpy as np

from tests.utils import DummyContext, make_records, make_st_waveforms
from waveform_analysis.core.data.records_view import RecordsView
from waveform_analysis.core.plugins.builtin.cpu.peak_finding import (
    HIT_DTYPE,
    HitFinderPlugin,
)


def test_hitfinder_empty_dtype():
    st_waveforms = make_st_waveforms(n_events=0, n_samples=5)
    ctx = DummyContext({"use_filtered": False}, {"st_waveforms": st_waveforms})
    plugin = HitFinderPlugin()

    peaks = plugin.compute(ctx, "run_001")

    assert len(peaks) == 0
    assert peaks.dtype == HIT_DTYPE


def test_hitfinder_parallel_consistency():
    st_waveforms = make_st_waveforms(
        n_events=200, n_samples=128, n_channels=2, baseline=100.0, dt=2
    )

    for i in range(len(st_waveforms)):
        wave = np.ones(128, dtype=np.int16) * 100
        pulse_start = 20 + (i % 40)
        wave[pulse_start : pulse_start + 4] = 40
        st_waveforms[i]["wave"] = wave
        st_waveforms[i]["timestamp"] = 100_000 + i * 1000

    base_config = {
        "use_filtered": False,
        "use_derivative": False,
        "height": 5.0,
        "distance": 1,
        "prominence": 1.0,
        "width": 1,
        "threshold": None,
    }
    plugin = HitFinderPlugin()

    ctx_serial = DummyContext({**base_config, "parallel": False}, {"st_waveforms": st_waveforms})
    ctx_parallel = DummyContext(
        {
            **base_config,
            "parallel": True,
            "n_workers": 4,
            "chunk_size": 32,
            "parallel_min_events": 1,
        },
        {"st_waveforms": st_waveforms},
    )

    serial_result = plugin.compute(ctx_serial, "run_001")
    parallel_result = plugin.compute(ctx_parallel, "run_001")

    np.testing.assert_array_equal(parallel_result, serial_result)


def test_hitfinder_height_window_extension_effect():
    st_waveforms = make_st_waveforms(n_events=1, n_samples=64, baseline=100.0, dt=2)
    wave = np.ones(64, dtype=np.int16) * 100
    wave[30:34] = 60
    wave[38] = 130
    st_waveforms[0]["wave"] = wave
    st_waveforms[0]["timestamp"] = 100_000

    plugin = HitFinderPlugin()
    base_config = {
        "use_filtered": False,
        "use_derivative": False,
        "height": 5.0,
        "distance": 1,
        "prominence": 1.0,
        "width": 1,
        "threshold": None,
        "height_method": "minmax",
        "parallel": False,
    }

    peaks_small = plugin.compute(
        DummyContext({**base_config, "height_window_extension": 0}, {"st_waveforms": st_waveforms}),
        "run_001",
    )
    peaks_large = plugin.compute(
        DummyContext({**base_config, "height_window_extension": 8}, {"st_waveforms": st_waveforms}),
        "run_001",
    )

    assert len(peaks_small) > 0
    assert len(peaks_large) > 0
    assert peaks_large["height"][0] > peaks_small["height"][0]


def test_hitfinder_wave_source_records_and_use_filtered_depends_on_filtered_pool():
    plugin = HitFinderPlugin()
    ctx = DummyContext({"wave_source": "records", "use_filtered": True}, {})

    assert plugin.resolve_depends_on(ctx) == ["records", "wave_pool_filtered"]


def test_hitfinder_reads_records_view_when_wave_source_records():
    plugin = HitFinderPlugin()
    ctx = DummyContext(
        {
            "wave_source": "records",
            "use_derivative": False,
            "height": 5.0,
            "distance": 1,
            "prominence": 1.0,
            "width": 1,
            "threshold": None,
            "parallel": False,
            "dt": 2,
        },
        {},
    )

    records = make_records(
        n_records=1, event_length=8, baseline=100.0, dt=2, timestamp_start=123_456
    )
    records["board"] = 5
    records["channel"] = 2
    records["polarity"] = ["negative"]
    wave_pool = np.array([100, 100, 80, 80, 80, 80, 100, 100], dtype=np.uint16)
    rv = RecordsView(records, wave_pool)

    with patch("waveform_analysis.core.records_view", return_value=rv) as mocked:
        result = plugin.compute(ctx, "run_001")

    assert mocked.call_count == 1
    assert len(result) == 1
    assert int(result[0]["board"]) == 5
    assert int(result[0]["channel"]) == 2
    assert int(result[0]["record_id"]) == 0
    assert int(result[0]["dt"]) == 2


def test_hitfinder_records_use_filtered_reads_filtered_pool():
    plugin = HitFinderPlugin()
    ctx = DummyContext(
        {
            "wave_source": "records",
            "use_filtered": True,
            "use_derivative": False,
            "height": 5.0,
            "distance": 1,
            "prominence": 1.0,
            "width": 1,
            "threshold": None,
            "parallel": False,
            "dt": 2,
        },
        {},
    )

    records = make_records(
        n_records=1, event_length=8, baseline=100.0, dt=2, timestamp_start=123_456
    )
    records["board"] = 5
    records["channel"] = 2
    records["polarity"] = ["negative"]
    wave_pool_filtered = np.array([100, 100, 80, 80, 80, 80, 100, 100], dtype=np.float32)
    rv = RecordsView(records, wave_pool_filtered)

    with patch("waveform_analysis.core.records_view", return_value=rv) as mocked:
        plugin.compute(ctx, "run_001")

    assert mocked.call_args.kwargs["wave_pool_name"] == "wave_pool_filtered"
