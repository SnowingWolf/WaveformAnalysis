import numpy as np
import pytest
from scipy.signal import butter, savgol_filter, sosfiltfilt

from tests.utils import FakeContext, make_records
from waveform_analysis.core.plugins.builtin.wave_pool_filtered import WavePoolFilteredPlugin
from waveform_analysis.core.processing.dtypes import RECORDS_DTYPE


def _legacy_reference(raw_wave_pool: np.ndarray, config: dict) -> np.ndarray:
    waves = raw_wave_pool.astype(np.float64)
    if config["filter_type"] == "SG":
        filtered = savgol_filter(
            waves,
            window_length=int(config["sg_window_size"]),
            polyorder=int(config["sg_poly_order"]),
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
            filtered = sosfiltfilt(sos, waves)
        except ValueError:
            return raw_wave_pool.astype(np.float32)
    return filtered.astype(np.float32)


@pytest.mark.parametrize(
    "config",
    [
        {"filter_type": "SG", "sg_window_size": 5, "sg_poly_order": 2},
        {"filter_type": "BW", "lowcut": 0.05, "highcut": 0.2, "fs": 1.0, "filter_order": 4},
    ],
    ids=["sg", "bw"],
)
def test_wave_pool_filtered_plugin_builds_float32_pool(config):
    records = make_records(
        n_records=2, record_id=[1, 2], timestamp=[10, 20], channel=[0, 1], event_length=7, dt=0
    )
    raw_wave_pool = np.array(
        [
            100,
            90,
            80,
            70,
            80,
            90,
            100,
            100,
            100,
            95,
            90,
            95,
            100,
            100,
        ],
        dtype=np.uint16,
    )
    ctx = FakeContext(
        config=config,
        data={"records": records, "wave_pool": raw_wave_pool},
    )
    plugin = WavePoolFilteredPlugin()

    filtered = plugin.compute(ctx, "run_001")
    reference = np.zeros_like(raw_wave_pool, dtype=np.float32)
    reference[:7] = _legacy_reference(raw_wave_pool[:7], config)
    reference[7:] = _legacy_reference(raw_wave_pool[7:], config)

    assert filtered.dtype == np.float32
    assert filtered.shape == raw_wave_pool.shape
    if config["filter_type"] == "SG":
        assert not np.allclose(filtered, raw_wave_pool.astype(np.float32))
    else:
        np.testing.assert_allclose(filtered, raw_wave_pool.astype(np.float32))
    np.testing.assert_allclose(filtered, reference, rtol=1e-4, atol=1e-3)


def test_wave_pool_filtered_plugin_handles_empty_wave_pool():
    records = np.zeros(0, dtype=RECORDS_DTYPE)
    ctx = FakeContext(
        config={"filter_type": "SG", "sg_window_size": 5, "sg_poly_order": 2},
        data={"records": records, "wave_pool": np.zeros(0, dtype=np.uint16)},
    )
    plugin = WavePoolFilteredPlugin()

    filtered = plugin.compute(ctx, "run_001")

    assert filtered.dtype == np.float32
    assert filtered.size == 0


def test_wave_pool_filtered_parallel_matches_serial_with_batching():
    records = np.zeros(4, dtype=RECORDS_DTYPE)
    records["record_id"] = np.arange(4, dtype=np.int64)
    records["timestamp"] = np.arange(4, dtype=np.int64)
    records["board"] = 0
    records["channel"] = np.array([0, 0, 1, 1], dtype=np.int16)
    records["baseline"] = 100.0
    records["wave_offset"] = np.array([0, 9, 18, 27], dtype=np.int64)
    records["event_length"] = 9
    wave_pool = np.tile(np.array([100, 100, 80, 60, 40, 60, 80, 100, 100], dtype=np.uint16), 4)

    serial_ctx = FakeContext(
        config={
            "filter_type": "SG",
            "sg_window_size": 5,
            "sg_poly_order": 2,
            "batch_size": 1,
            "max_workers": 1,
        },
        data={"records": records, "wave_pool": wave_pool},
    )
    parallel_ctx = FakeContext(
        config={
            "filter_type": "SG",
            "sg_window_size": 5,
            "sg_poly_order": 2,
            "batch_size": 1,
            "max_workers": 2,
        },
        data={"records": records, "wave_pool": wave_pool},
    )

    plugin = WavePoolFilteredPlugin()
    serial = plugin.compute(serial_ctx, "run_001")
    parallel = plugin.compute(parallel_ctx, "run_001")

    np.testing.assert_allclose(parallel, serial)


def test_wave_pool_filtered_channel_config_overrides_filter():
    records = np.zeros(2, dtype=RECORDS_DTYPE)
    records["record_id"] = np.arange(2, dtype=np.int64)
    records["timestamp"] = np.arange(2, dtype=np.int64)
    records["board"] = 0
    records["channel"] = np.array([0, 1], dtype=np.int16)
    records["baseline"] = 100.0
    records["wave_offset"] = np.array([0, 9], dtype=np.int64)
    records["event_length"] = 9
    wave_pool = np.tile(np.array([100, 100, 80, 60, 40, 60, 80, 100, 100], dtype=np.uint16), 2)

    ctx = FakeContext(
        config={
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
        data={"records": records, "wave_pool": wave_pool},
    )

    filtered = WavePoolFilteredPlugin().compute(ctx, "run_001")

    assert filtered.dtype == np.float32
    assert not np.allclose(filtered[:9], filtered[9:])
