"""Shared helpers for BasicFeaturesPlugin tests."""

from unittest.mock import patch

import numpy as np

from tests.utils import FakeContext
from waveform_analysis.core.data.records_view import RecordsView
from waveform_analysis.core.processing.records_builder import RECORDS_DTYPE


def make_basic_feature_waveforms(n=4, wave_length=100, n_channels=2):
    """Create a minimal structured waveform array for BasicFeatures tests."""
    dtype = np.dtype(
        [
            ("baseline", "f8"),
            ("polarity", "U8"),
            ("timestamp", "i8"),
            ("channel", "i2"),
            ("wave", "i2", (wave_length,)),
        ]
    )
    data = np.zeros(n, dtype=dtype)
    for i in range(n):
        data[i]["baseline"] = 100.0
        data[i]["timestamp"] = i * 1000
        data[i]["channel"] = i % n_channels
        wave = np.full(wave_length, 90, dtype="i2")
        mid = wave_length // 2
        wave[mid] = 80
        if mid + 1 < wave_length:
            wave[mid + 1] = 95
        data[i]["wave"] = wave
    return data


def make_basic_feature_context(waveform_data, config=None, use_filtered=False):
    """Build a FakeContext with sensible defaults for short test waveforms."""
    cfg = {"height_range": (0, None), "area_range": (0, None)}
    if config:
        cfg.update(config)
    data_key = "filtered_waveforms" if use_filtered else "st_waveforms"
    return FakeContext(config=cfg, data={data_key: waveform_data})


def make_records_view():
    records = np.zeros(2, dtype=RECORDS_DTYPE)
    records["timestamp"] = [10, 20]
    records["pid"] = 0
    records["board"] = [3, 4]
    records["channel"] = [0, 1]
    records["record_id"] = [10, 11]
    records["baseline"] = [100.0, 100.0]
    records["wave_offset"] = [0, 4]
    records["event_length"] = [4, 4]
    records["time"] = [0, 0]
    wave_pool = np.array([90, 80, 95, 90, 90, 85, 90, 90], dtype=np.uint16)
    return RecordsView(records, wave_pool)


def make_records_and_pools():
    records = np.zeros(2, dtype=RECORDS_DTYPE)
    records["timestamp"] = [10, 20]
    records["pid"] = 0
    records["board"] = [3, 4]
    records["channel"] = [0, 1]
    records["record_id"] = [10, 11]
    records["baseline"] = [100.0, 100.0]
    records["wave_offset"] = [0, 4]
    records["event_length"] = [4, 4]
    records["time"] = [0, 0]
    wave_pool = np.array([90, 80, 95, 90, 90, 85, 90, 90], dtype=np.uint16)
    wave_pool_filtered = np.full(8, 95, dtype=np.float32)
    return records, wave_pool, wave_pool_filtered


def patch_records_view(records_view):
    """Patch the records_view helper used by BasicFeaturesPlugin."""
    return patch("waveform_analysis.core.records_view", return_value=records_view)
