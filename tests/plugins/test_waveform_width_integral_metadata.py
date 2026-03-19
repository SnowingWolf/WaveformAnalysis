from unittest.mock import patch

import numpy as np

from tests.utils import DummyContext
from waveform_analysis.core.data.records_view import RecordsView
from waveform_analysis.core.plugins.builtin.cpu.waveform_width_integral import (
    WaveformWidthIntegralPlugin,
)
from waveform_analysis.core.processing.dtypes import create_record_dtype
from waveform_analysis.core.processing.records_builder import RECORDS_DTYPE


def _make_waveforms(n_events=1, wave_len=32):
    dtype = create_record_dtype(wave_len)
    data = np.zeros(n_events, dtype=dtype)
    data["baseline"] = 100.0
    data["timestamp"] = 123456
    data["channel"] = 1
    data["event_length"] = wave_len
    data["wave"] = 100
    return data


def _make_records_view():
    records = np.zeros(1, dtype=RECORDS_DTYPE)
    records["baseline"] = 100.0
    records["timestamp"] = 123456
    records["channel"] = 1
    records["event_length"] = 8
    records["wave_offset"] = 0
    wave_pool = np.array([100, 100, 80, 80, 80, 80, 100, 100], dtype=np.uint16)
    return RecordsView(records, wave_pool)


def test_waveform_width_integral_channel_metadata_overrides_auto_polarity():
    plugin = WaveformWidthIntegralPlugin()
    st = _make_waveforms()
    st[0]["wave"][10:14] = 80

    ctx = DummyContext(
        {
            "polarity": "auto",
            "channel_metadata": {
                "run_001": {
                    "1": {
                        "polarity": "positive",
                        "geometry": "detector_a",
                        "adc_bits": 14,
                    }
                }
            },
        },
        {"st_waveforms": st},
    )

    out = plugin.compute(ctx, "run_001")
    assert len(out) == 1
    assert float(out[0]["q_total"]) == 0.0


def test_waveform_width_integral_wave_source_records_depends_on_records():
    plugin = WaveformWidthIntegralPlugin()
    ctx = DummyContext({"wave_source": "records", "use_filtered": True}, {})
    assert plugin.resolve_depends_on(ctx) == ["records"]


def test_waveform_width_integral_reads_records_view_when_wave_source_records():
    plugin = WaveformWidthIntegralPlugin()
    ctx = DummyContext(
        {
            "wave_source": "records",
            "polarity": "negative",
            "q_low": 0.1,
            "q_high": 0.9,
            "sampling_rate": 0.5,
        },
        {},
    )
    rv = _make_records_view()

    with patch("waveform_analysis.core.records_view", return_value=rv) as mocked:
        out = plugin.compute(ctx, "run_001")

    assert mocked.call_count == 1
    assert len(out) == 1
    assert float(out[0]["q_total"]) > 0.0
