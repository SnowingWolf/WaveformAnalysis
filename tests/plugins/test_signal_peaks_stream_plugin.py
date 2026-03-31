import numpy as np
import pytest

from tests.utils import DummyContext
from waveform_analysis.core.plugins.builtin.cpu.peak_finding import HIT_DTYPE
from waveform_analysis.core.plugins.builtin.streaming.cpu.signal_peaks import (
    SignalPeaksStreamPlugin,
)
from waveform_analysis.core.processing.dtypes import create_record_dtype


def _make_waveforms(n_events=1, wave_len=32, *, dt=4):
    dtype = create_record_dtype(wave_len)
    data = np.zeros(n_events, dtype=dtype)
    data["baseline"] = 100.0
    data["timestamp"] = 1_000_000
    data["board"] = 3
    data["channel"] = 7
    data["record_id"] = np.arange(n_events, dtype=np.int64)
    data["event_length"] = wave_len
    data["dt"] = dt
    data["wave"] = 100
    return data


def test_signal_peaks_stream_prefers_input_dt_over_deprecated_config():
    plugin = SignalPeaksStreamPlugin()
    st = _make_waveforms(dt=4)
    filtered = _make_waveforms(dt=4)
    filtered[0]["wave"][10:13] = np.array([80, 60, 80], dtype=filtered[0]["wave"].dtype)

    ctx = DummyContext(
        {
            "use_derivative": False,
            "height": 10.0,
            "distance": 1,
            "prominence": 1.0,
            "width": 1,
            "height_method": "minmax",
            "sampling_interval_ns": 2.0,
        },
        {
            "st_waveforms": st,
            "filtered_waveforms": filtered,
        },
    )

    with pytest.warns(DeprecationWarning, match="sampling_interval_ns"):
        plugin._load_config(ctx)

    chunks = list(plugin._get_input_chunks(ctx, "run_001"))
    assert len(chunks) == 1

    result_chunk = plugin.compute_chunk(chunks[0], ctx, "run_001")
    assert result_chunk is not None
    assert result_chunk.data.dtype == HIT_DTYPE
    assert len(result_chunk.data) == 1
    assert int(result_chunk.data[0]["dt"]) == 4
    assert int(result_chunk.data[0]["board"]) == 3
    assert int(result_chunk.data[0]["channel"]) == 7
    assert int(result_chunk.data[0]["timestamp"]) == 1_000_000 + 11 * 4 * 1000
