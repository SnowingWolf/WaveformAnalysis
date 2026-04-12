import numpy as np
import pytest
from scipy.signal import butter, savgol_filter, sosfiltfilt

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


def _legacy_filtered_waveforms_reference(st_waveforms: np.ndarray, config: dict) -> np.ndarray:
    output = np.zeros(
        len(st_waveforms),
        dtype=[
            (
                (
                    name,
                    np.float32,
                    st_waveforms.dtype.fields[name][0].subdtype[1],
                )
                if name == "wave"
                else (
                    (
                        name,
                        st_waveforms.dtype.fields[name][0].subdtype[0],
                        st_waveforms.dtype.fields[name][0].subdtype[1],
                    )
                    if st_waveforms.dtype.fields[name][0].subdtype is not None
                    else (name, st_waveforms.dtype.fields[name][0])
                )
            )
            for name in st_waveforms.dtype.names
        ],
    )
    for field in st_waveforms.dtype.names:
        if field != "wave":
            output[field] = st_waveforms[field]
    waves_f64 = st_waveforms["wave"].astype(np.float64)

    if config["filter_type"] == "SG":
        window = min(int(config["sg_window_size"]), waves_f64.shape[1])
        if window % 2 == 0:
            window -= 1
        if window <= int(config["sg_poly_order"]):
            return output
        filtered = savgol_filter(
            waves_f64,
            window_length=window,
            polyorder=int(config["sg_poly_order"]),
            axis=-1,
            mode="interp",
        )
    else:
        sos = butter(
            int(config["filter_order"]),
            [float(config["lowcut"]), float(config["highcut"])],
            btype="band",
            output="sos",
            fs=float(config["fs"]),
        )
        try:
            filtered = sosfiltfilt(sos, waves_f64, axis=-1)
        except ValueError:
            return output

    output["wave"] = filtered.astype(np.float32, copy=False)
    return output


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


@pytest.mark.parametrize(
    "config",
    [
        {"filter_type": "SG", "sg_window_size": 11, "sg_poly_order": 2},
        {"filter_type": "BW", "lowcut": 0.05, "highcut": 0.2, "fs": 1.0, "filter_order": 4},
    ],
    ids=["sg", "bw"],
)
def test_float32_path_matches_legacy_reference_with_tolerance(config):
    st_waveforms = _make_st_waveforms(n_events=96, n_samples=128, n_channels=4)
    ctx = DummyContext(
        {**config, "batch_size": 8, "max_workers": 1},
        {"st_waveforms": st_waveforms},
    )

    result = FilteredWaveformsPlugin().compute(ctx, "run_001")
    reference = _legacy_filtered_waveforms_reference(st_waveforms, config)

    for field in st_waveforms.dtype.names:
        if field == "wave":
            continue
        np.testing.assert_array_equal(result[field], reference[field])
    assert result["wave"].dtype == np.float32
    np.testing.assert_allclose(result["wave"], reference["wave"], atol=1e-4, rtol=1e-4)


def test_contiguous_channel_batches_prefer_slice_selectors():
    plugin = FilteredWaveformsPlugin()
    boards = np.zeros(8, dtype=np.int16)
    channels = np.array([0, 0, 0, 0, 1, 1, 1, 1], dtype=np.int16)

    batches = plugin._build_channel_batches(boards, channels, batch_size=2)

    assert len(batches) == 4
    assert all(isinstance(selector, slice) for _channel, selector in batches)


def test_interleaved_channel_batches_fall_back_to_indices_without_batching():
    plugin = FilteredWaveformsPlugin()
    boards = np.zeros(6, dtype=np.int16)
    channels = np.array([0, 1, 0, 1, 0, 1], dtype=np.int16)

    batches = plugin._build_channel_batches(boards, channels, batch_size=0)

    assert len(batches) == 2
    assert all(isinstance(selector, np.ndarray) for _channel, selector in batches)
    np.testing.assert_array_equal(batches[0][1], np.array([0, 2, 4]))
    np.testing.assert_array_equal(batches[1][1], np.array([1, 3, 5]))


def test_sg_short_wave_returns_original_wave_and_preserves_metadata():
    st_waveforms = _make_st_waveforms(n_events=6, n_samples=3, n_channels=2)
    ctx = DummyContext(
        {
            "filter_type": "SG",
            "sg_window_size": 5,
            "sg_poly_order": 3,
            "batch_size": 0,
            "max_workers": 1,
        },
        {"st_waveforms": st_waveforms},
    )

    result = FilteredWaveformsPlugin().compute(ctx, "run_001")

    np.testing.assert_array_equal(result["wave"], st_waveforms["wave"].astype(np.float32))
    for field in st_waveforms.dtype.names:
        if field == "wave":
            continue
        np.testing.assert_array_equal(result[field], st_waveforms[field])


def test_output_wave_dtype_is_float32_and_metadata_preserved():
    st_waveforms = _make_st_waveforms(n_events=4, n_samples=16, n_channels=2)
    ctx = DummyContext(
        {"filter_type": "SG", "sg_window_size": 5, "sg_poly_order": 2},
        {"st_waveforms": st_waveforms},
    )

    result = FilteredWaveformsPlugin().compute(ctx, "run_001")

    assert result["wave"].dtype == np.float32
    assert result.dtype != st_waveforms.dtype
    for field in st_waveforms.dtype.names:
        if field == "wave":
            continue
        np.testing.assert_array_equal(result[field], st_waveforms[field])


def test_channel_config_overrides_filter_per_hardware_channel():
    st_waveforms = _make_st_waveforms(n_events=4, n_samples=9, n_channels=2)
    st_waveforms["board"] = np.array([0, 0, 0, 0], dtype=np.int16)
    st_waveforms["channel"] = np.array([0, 0, 1, 1], dtype=np.int16)
    st_waveforms["wave"][0] = np.array([100, 100, 60, 40, 20, 40, 60, 100, 100], dtype=np.int16)
    st_waveforms["wave"][1] = st_waveforms["wave"][0]
    st_waveforms["wave"][2] = st_waveforms["wave"][0]
    st_waveforms["wave"][3] = st_waveforms["wave"][0]

    ctx = DummyContext(
        {
            "filter_type": "SG",
            "sg_window_size": 5,
            "sg_poly_order": 2,
            "channel_config": {
                "channels": {
                    "0:1": {
                        "filter_type": "SG",
                        "sg_window_size": 7,
                        "sg_poly_order": 3,
                    }
                }
            },
        },
        {"st_waveforms": st_waveforms},
    )

    result = FilteredWaveformsPlugin().compute(ctx, "run_001")

    np.testing.assert_allclose(result["wave"][0], result["wave"][1])
    np.testing.assert_allclose(result["wave"][2], result["wave"][3])
    assert not np.allclose(result["wave"][0], result["wave"][2])
