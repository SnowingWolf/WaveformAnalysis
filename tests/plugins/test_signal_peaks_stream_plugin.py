import numpy as np
import pytest

from tests.utils import DummyContext, make_st_waveforms
from waveform_analysis.core.plugins.builtin.cpu.peak_finding import HIT_DTYPE
from waveform_analysis.core.plugins.builtin.streaming.cpu.signal_peaks import (
    SignalPeaksStreamPlugin,
)


def test_signal_peaks_stream_prefers_input_dt_over_deprecated_config():
    plugin = SignalPeaksStreamPlugin()
    st = make_st_waveforms(
        n_events=1,
        n_samples=32,
        baseline=100.0,
        timestamp=1_000_000,
        board=3,
        channel=7,
        record_id=True,
        dt=4,
        wave_fill=100,
    )
    filtered = make_st_waveforms(
        n_events=1,
        n_samples=32,
        baseline=100.0,
        timestamp=1_000_000,
        board=3,
        channel=7,
        record_id=True,
        dt=4,
        wave_fill=100,
    )
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
