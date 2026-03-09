import numpy as np
import pytest

from tests.utils import DummyContext
from waveform_analysis.core.plugins.builtin.cpu.filtering import FilteredWaveformsPlugin
from waveform_analysis.core.processing.dtypes import create_record_dtype


def _make_st_waveforms(n_events=96, n_samples=128, n_channels=4, seed=42):
    dtype = create_record_dtype(n_samples)
    st_waveforms = np.zeros(n_events, dtype=dtype)
    st_waveforms["channel"] = np.arange(n_events, dtype=np.int16) % np.int16(n_channels)
    st_waveforms["timestamp"] = np.arange(n_events, dtype=np.int64) * 1000
    st_waveforms["baseline"] = 0.0
    st_waveforms["event_length"] = n_samples
    st_waveforms["dt"] = 1

    rng = np.random.default_rng(seed)
    st_waveforms["wave"] = rng.integers(-200, 200, size=(n_events, n_samples), dtype=np.int16)
    return st_waveforms


@pytest.mark.parametrize(
    "config",
    [
        {"filter_type": "SG", "sg_window_size": 11, "sg_poly_order": 2},
        {"filter_type": "BW", "lowcut": 0.05, "highcut": 0.2, "fs": 1.0, "filter_order": 4},
    ],
    ids=["sg", "bw"],
)
def test_batch_size_matches_non_batch(config):
    st_waveforms = _make_st_waveforms()

    ctx_no_batch = DummyContext(
        {**config, "batch_size": 0, "max_workers": 1},
        {"st_waveforms": st_waveforms},
    )
    ctx_batch = DummyContext(
        {**config, "batch_size": 8, "max_workers": 1},
        {"st_waveforms": st_waveforms},
    )

    no_batch = FilteredWaveformsPlugin().compute(ctx_no_batch, "run_001")
    batch = FilteredWaveformsPlugin().compute(ctx_batch, "run_001")

    np.testing.assert_array_equal(batch, no_batch)


@pytest.mark.parametrize(
    "config",
    [
        {"filter_type": "SG", "sg_window_size": 11, "sg_poly_order": 2},
        {"filter_type": "BW", "lowcut": 0.05, "highcut": 0.2, "fs": 1.0, "filter_order": 4},
    ],
    ids=["sg", "bw"],
)
def test_parallel_matches_serial_with_batching(config):
    st_waveforms = _make_st_waveforms(n_events=128, n_samples=256, n_channels=8)

    ctx_serial = DummyContext(
        {**config, "batch_size": 8, "max_workers": 1},
        {"st_waveforms": st_waveforms},
    )
    ctx_parallel = DummyContext(
        {**config, "batch_size": 8, "max_workers": 4},
        {"st_waveforms": st_waveforms},
    )

    serial = FilteredWaveformsPlugin().compute(ctx_serial, "run_001")
    parallel = FilteredWaveformsPlugin().compute(ctx_parallel, "run_001")

    np.testing.assert_array_equal(parallel, serial)


def test_negative_batch_size_raises():
    st_waveforms = _make_st_waveforms()
    ctx = DummyContext(
        {"filter_type": "SG", "sg_window_size": 11, "sg_poly_order": 2, "batch_size": -1},
        {"st_waveforms": st_waveforms},
    )
    with pytest.raises(ValueError, match="batch_size"):
        FilteredWaveformsPlugin().compute(ctx, "run_001")
