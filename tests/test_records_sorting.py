from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

from waveform_analysis.core.foundation.utils import Profiler
from waveform_analysis.core.processing.dtypes import create_record_dtype
from waveform_analysis.core.processing.records_builder import (
    build_records_from_raw_files,
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


def test_build_records_from_raw_files_sorts_globally_without_materializing_st_waveforms():
    file_map = {
        "ch1_0.csv": np.array(
            [
                [0, 1, 3000, 0, 0, 0, 0, 1, 2, 3, 4],
                [0, 1, 1000, 0, 0, 0, 0, 5, 6, 7, 8],
            ],
            dtype=np.int64,
        ),
        "ch0_0.csv": np.array(
            [
                [0, 0, 2000, 0, 0, 0, 0, 9, 10, 11, 12],
            ],
            dtype=np.int64,
        ),
    }

    class MockReader:
        def __init__(self):
            self.calls = []

        def read_file(self, file_path, is_first_file=True):  # noqa: ARG002
            return file_map[str(file_path)]

        def read_files_generator(
            self,
            file_paths,
            chunk_size=1,
            **kwargs,
        ):  # noqa: ARG002
            self.calls.append({"file_paths": list(file_paths), "chunk_size": chunk_size, **kwargs})
            for idx, file_path in enumerate(file_paths):
                yield self.read_file(file_path, is_first_file=(idx == 0))

    reader = MockReader()
    mock_adapter = SimpleNamespace(
        format_reader=reader,
        format_spec=SimpleNamespace(
            columns=SimpleNamespace(
                board=0,
                channel=1,
                timestamp=2,
                samples_start=7,
                samples_end=None,
                baseline_start=7,
                baseline_end=9,
            ),
            normalize_timestamp_to_ps=lambda timestamps, dt_ns: timestamps,
        ),
    )

    with patch("waveform_analysis.utils.formats.get_adapter", return_value=mock_adapter):
        bundle = build_records_from_raw_files(
            [["ch1_0.csv"], ["ch0_0.csv"]],
            adapter_name="mock",
            default_dt_ns=2,
            part_size=1,
            epoch_ns=100,
            parse_engine="pyarrow",
            n_jobs=3,
            chunksize=512,
            use_process_pool=True,
        )

    np.testing.assert_array_equal(bundle.records["timestamp"], np.array([1000, 2000, 3000]))
    np.testing.assert_array_equal(bundle.records["channel"], np.array([1, 0, 1], dtype=np.int16))
    np.testing.assert_array_equal(bundle.records["record_id"], np.arange(3, dtype=np.int64))
    np.testing.assert_allclose(bundle.records["baseline"], np.array([5.5, 9.5, 1.5]))
    np.testing.assert_array_equal(bundle.records["time"], np.array([101, 102, 103], dtype=np.int64))
    np.testing.assert_array_equal(
        bundle.wave_pool,
        np.array([5, 6, 7, 8, 9, 10, 11, 12, 1, 2, 3, 4], dtype=np.uint16),
    )
    assert reader.calls[0]["parse_engine"] == "pyarrow"
    assert reader.calls[0]["n_jobs"] == 3
    assert reader.calls[0]["chunksize"] == 512
    assert reader.calls[0]["use_process_pool"] is True


def test_build_records_from_raw_files_does_not_use_python_wave_list_path():
    raw_arr = np.array(
        [
            [0, 0, 1000, 0, 0, 0, 0, 10, 11, 12, 13],
            [0, 0, 2000, 0, 0, 0, 0, 20, 21, 22, 23],
        ],
        dtype=np.int64,
    )

    class MockReader:
        def read_files_generator(self, file_paths, chunk_size=1, **kwargs):  # noqa: ARG002
            yield raw_arr

    mock_adapter = SimpleNamespace(
        format_reader=MockReader(),
        format_spec=SimpleNamespace(
            columns=SimpleNamespace(
                board=0,
                channel=1,
                timestamp=2,
                samples_start=7,
                samples_end=None,
                baseline_start=7,
                baseline_end=9,
            ),
            normalize_timestamp_to_ps=lambda timestamps, dt_ns: timestamps,
        ),
    )

    with patch("waveform_analysis.utils.formats.get_adapter", return_value=mock_adapter):
        with patch(
            "waveform_analysis.core.processing.records_builder._build_records_from_wave_list",
            side_effect=AssertionError("raw builder should not call _build_records_from_wave_list"),
        ):
            bundle = build_records_from_raw_files(
                [["ch0_0.csv"]],
                adapter_name="mock",
                default_dt_ns=2,
                part_size=None,
            )

    np.testing.assert_array_equal(
        bundle.records["timestamp"], np.array([1000, 2000], dtype=np.int64)
    )
    np.testing.assert_array_equal(
        bundle.wave_pool,
        np.array([10, 11, 12, 13, 20, 21, 22, 23], dtype=np.uint16),
    )


def test_build_records_from_raw_files_profiles_read_build_and_merge():
    raw_arr = np.array(
        [
            [0, 0, 3000, 0, 0, 0, 0, 1, 2],
            [0, 0, 1000, 0, 0, 0, 0, 3, 4],
            [0, 0, 2000, 0, 0, 0, 0, 5, 6],
        ],
        dtype=np.int64,
    )

    class MockReader:
        def read_files_generator(self, file_paths, chunk_size=1, **kwargs):  # noqa: ARG002
            yield raw_arr[:2]
            yield raw_arr[2:]

    mock_adapter = SimpleNamespace(
        format_reader=MockReader(),
        format_spec=SimpleNamespace(
            columns=SimpleNamespace(
                board=0,
                channel=1,
                timestamp=2,
                samples_start=7,
                samples_end=None,
                baseline_start=7,
                baseline_end=9,
            ),
            normalize_timestamp_to_ps=lambda timestamps, dt_ns: timestamps,
        ),
    )
    profiler = Profiler()

    with patch("waveform_analysis.utils.formats.get_adapter", return_value=mock_adapter):
        build_records_from_raw_files(
            [["ch0_0.csv"]],
            adapter_name="mock",
            default_dt_ns=2,
            part_size=2,
            profiler=profiler,
        )

    assert profiler.counts["records.read"] == 2
    assert profiler.counts["records.part_build"] == 2
    assert profiler.counts["records.merge"] == 1


def test_build_records_from_raw_files_supports_channel_parallelism():
    file_map = {
        "ch0_0.csv": np.array([[0, 0, 2000, 0, 0, 0, 0, 9, 10, 11, 12]], dtype=np.int64),
        "ch1_0.csv": np.array([[0, 1, 1000, 0, 0, 0, 0, 5, 6, 7, 8]], dtype=np.int64),
    }

    class MockReader:
        def read_files_generator(self, file_paths, chunk_size=1, **kwargs):  # noqa: ARG002
            for file_path in file_paths:
                yield file_map[str(file_path)]

    def make_adapter():
        return SimpleNamespace(
            format_reader=MockReader(),
            format_spec=SimpleNamespace(
                columns=SimpleNamespace(
                    board=0,
                    channel=1,
                    timestamp=2,
                    samples_start=7,
                    samples_end=None,
                    baseline_start=7,
                    baseline_end=9,
                ),
                normalize_timestamp_to_ps=lambda timestamps, dt_ns: timestamps,
            ),
        )

    profiler = Profiler()
    with patch(
        "waveform_analysis.utils.formats.get_adapter", side_effect=lambda name: make_adapter()
    ):
        bundle = build_records_from_raw_files(
            [["ch0_0.csv"], ["ch1_0.csv"]],
            adapter_name="mock",
            default_dt_ns=2,
            part_size=None,
            channel_workers=2,
            channel_executor="thread",
            profiler=profiler,
        )

    np.testing.assert_array_equal(
        bundle.records["timestamp"], np.array([1000, 2000], dtype=np.int64)
    )
    np.testing.assert_array_equal(bundle.records["channel"], np.array([1, 0], dtype=np.int16))
    np.testing.assert_array_equal(
        bundle.wave_pool,
        np.array([5, 6, 7, 8, 9, 10, 11, 12], dtype=np.uint16),
    )
    assert profiler.counts["records.read"] == 2
    assert profiler.counts["records.part_build"] == 2
    assert profiler.counts["records.merge"] == 1


def test_build_records_from_raw_files_handles_single_header_first_segment(tmp_path: Path):
    raw_dir = tmp_path / "RAW"
    raw_dir.mkdir()

    first = raw_dir / "DataR_CH0@VX2730_demo.CSV"
    first.write_text(
        """BOARD;CHANNEL;TIMETAG;ENERGY;ENERGYSHORT;FLAGS;PROBE_CODE;SAMPLES
0;0;1000;0;0;0x4000;1;10;11;12;13
0;0;2000;0;0;0x4000;1;20;21;22;23
""",
        encoding="utf-8",
    )
    second = raw_dir / "DataR_CH0@VX2730_demo_1.CSV"
    second.write_text(
        """0;0;3000;0;0;0x4000;1;30;31;32;33
0;0;4000;0;0;0x4000;1;40;41;42;43
""",
        encoding="utf-8",
    )

    bundle = build_records_from_raw_files(
        [[str(first), str(second)]],
        adapter_name="vx2730",
        default_dt_ns=2,
        part_size=None,
        show_progress=False,
    )

    np.testing.assert_array_equal(
        bundle.records["timestamp"],
        np.array([1000, 2000, 3000, 4000], dtype=np.int64),
    )
    np.testing.assert_array_equal(bundle.records["channel"], np.zeros(4, dtype=np.int16))
    np.testing.assert_array_equal(bundle.records["record_id"], np.arange(4, dtype=np.int64))
    np.testing.assert_array_equal(
        bundle.wave_pool,
        np.array(
            [10, 11, 12, 13, 20, 21, 22, 23, 30, 31, 32, 33, 40, 41, 42, 43],
            dtype=np.uint16,
        ),
    )
