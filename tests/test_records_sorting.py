from pathlib import Path

import numpy as np

from waveform_analysis.core.processing.dtypes import create_record_dtype
from waveform_analysis.core.processing.records_builder import (
    build_records_from_st_waveforms,
    build_records_from_st_waveforms_sharded,
    build_records_from_v1725_files,
)


def _make_st_waveforms() -> np.ndarray:
    dtype = create_record_dtype(4)
    data = np.zeros(6, dtype=dtype)
    data["board"] = [0, 0, 0, 1, 1, 1]
    data["channel"] = [1, 0, 1, 0, 1, 0]
    data["timestamp"] = [300, 100, 100, 250, 100, 200]
    data["baseline"] = 0.0
    data["record_id"] = [30, 10, 11, 25, 12, 20]
    data["event_length"] = [4, 4, 4, 4, 4, 4]
    data["wave"] = np.arange(4, dtype=np.int16)
    return data


def _make_v1725_single_wave_blob(
    *,
    channel: int,
    timestamp: int,
    baseline: int = 0,
    trunc: bool = False,
    samples: np.ndarray | None = None,
) -> bytes:
    if samples is None:
        samples = np.array([11, 12, 13, 14], dtype=np.int16)
    payload = np.asarray(samples, dtype=np.int16).tobytes()

    event_header = bytearray(16)
    channel_mask = 1 << int(channel)
    event_header[4] = channel_mask & 0xFF
    event_header[11] = (channel_mask >> 8) & 0xFF

    ch_header = bytearray(12)
    ch_size = 3 + (len(payload) // 4)
    ch_header[0] = ch_size & 0xFF
    ch_header[1] = (ch_size >> 8) & 0xFF
    ch_header[2] = (ch_size >> 16) & 0x3F
    if trunc:
        ch_header[3] |= 0x40
    ch_header[4:10] = int(timestamp).to_bytes(6, byteorder="little", signed=False)
    ch_header[10:12] = int(baseline).to_bytes(2, byteorder="little", signed=False)
    return bytes(event_header + ch_header + payload)


def test_build_records_from_st_waveforms_sorts_globally_by_timestamp():
    bundle = build_records_from_st_waveforms(_make_st_waveforms(), default_dt_ns=2)

    np.testing.assert_array_equal(
        bundle.records["timestamp"], np.array([100, 100, 100, 200, 250, 300])
    )
    np.testing.assert_array_equal(
        bundle.records["board"], np.array([0, 0, 1, 1, 1, 0], dtype=np.int16)
    )
    np.testing.assert_array_equal(
        bundle.records["channel"], np.array([0, 1, 1, 0, 0, 1], dtype=np.int16)
    )
    np.testing.assert_array_equal(
        bundle.records["record_id"], np.array([10, 11, 12, 20, 25, 30], dtype=np.int64)
    )


def test_build_records_from_st_waveforms_sharded_keeps_global_timestamp_order():
    st_waveforms = _make_st_waveforms()

    baseline = build_records_from_st_waveforms(st_waveforms, default_dt_ns=2)
    sharded = build_records_from_st_waveforms_sharded(st_waveforms, part_size=2, default_dt_ns=2)

    np.testing.assert_array_equal(sharded.records["timestamp"], baseline.records["timestamp"])
    np.testing.assert_array_equal(sharded.records["board"], baseline.records["board"])
    np.testing.assert_array_equal(sharded.records["channel"], baseline.records["channel"])
    np.testing.assert_array_equal(sharded.records["record_id"], baseline.records["record_id"])
    np.testing.assert_array_equal(sharded.wave_pool, baseline.wave_pool)


def test_build_records_from_v1725_files_sorts_approximately_ordered_input(tmp_path: Path):
    raw0 = tmp_path / "test_raw_b3_seg0.bin"
    raw1 = tmp_path / "test_raw_b4_seg1.bin"
    raw0.write_bytes(_make_v1725_single_wave_blob(channel=1, timestamp=30, baseline=100))
    raw1.write_bytes(_make_v1725_single_wave_blob(channel=0, timestamp=10, baseline=200))

    bundle = build_records_from_v1725_files([str(raw0), str(raw1)], dt_ns=4)

    np.testing.assert_array_equal(
        bundle.records["timestamp"], np.array([40_000, 120_000], dtype=np.int64)
    )
    np.testing.assert_array_equal(bundle.records["board"], np.array([4, 3], dtype=np.int16))
    np.testing.assert_array_equal(bundle.records["channel"], np.array([0, 1], dtype=np.int16))
    np.testing.assert_array_equal(bundle.records["record_id"], np.arange(2, dtype=np.int64))
