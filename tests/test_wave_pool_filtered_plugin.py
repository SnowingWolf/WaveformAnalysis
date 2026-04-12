import numpy as np
import pytest
from scipy.signal import butter, savgol_filter, sosfiltfilt

from tests.utils import FakeContext
from waveform_analysis.core.plugins.builtin.cpu.records import WavePoolFilteredPlugin
from waveform_analysis.core.processing.dtypes import RECORDS_DTYPE


def _make_records() -> np.ndarray:
    records = np.zeros(2, dtype=RECORDS_DTYPE)
    records["record_id"] = np.array([1, 2], dtype=np.int64)
    records["timestamp"] = np.array([10, 20], dtype=np.int64)
    records["board"] = 0
    records["channel"] = np.array([0, 1], dtype=np.int16)
    records["baseline"] = 100.0
    records["wave_offset"] = np.array([0, 7], dtype=np.int64)
    records["event_length"] = np.array([7, 7], dtype=np.int32)
    return records


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
    records = _make_records()
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
