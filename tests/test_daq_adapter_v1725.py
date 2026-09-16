"""V1725 reader tests."""

from pathlib import Path
import time

import numpy as np

from tests.daq_adapter_helpers import make_v1725_single_wave_blob
from waveform_analysis.core.processing.records_builder import (
    RECORDS_DTYPE,
    _build_v1725_records_part_from_array_batches,
    _build_v1725_records_part_from_waves,
    _process_v1725_file_to_disk,
    build_records_from_v1725_files,
)
from waveform_analysis.utils.formats import RawTimestampMode, V1725Reader, get_adapter
from waveform_analysis.utils.formats.v1725_numba import parse_channel_headers_numba


def _make_multi_channel_event(*, event_id: int, channels: int, samples: int) -> bytes:
    event_header = bytearray(16)
    payload = bytearray()

    for channel in range(channels):
        # 采样值需落在 int16 范围内（event_id 可能超过 327，直接计算会溢出）
        values = np.full(samples, (event_id * 100 + channel) % 32768, dtype=np.int16)
        blob = make_v1725_single_wave_blob(
            channel=channel,
            timestamp=event_id * 1000 + channel,
            baseline=500 + channel,
            trunc=channel == channels - 1,
            samples=values,
        )
        event_header[4] |= blob[4]
        event_header[11] |= blob[11]
        payload.extend(blob[16:])

    return bytes(event_header + payload)


def _array_batch_rows(batches):
    for batch in batches:
        for idx in range(len(batch)):
            start = int(batch.waveform_offsets[idx])
            stop = start + int(batch.waveform_lengths[idx])
            yield (
                int(batch.boards[idx]),
                int(batch.channels[idx]),
                int(batch.timestamps[idx]),
                int(batch.baselines[idx]),
                bool(batch.truncs[idx]),
                batch.waveform_samples[start:stop],
            )


def _assert_array_batch_rows_match_waves(batches, waves):
    rows = list(_array_batch_rows(batches))
    assert len(rows) == len(waves)
    for row, wave in zip(rows, waves, strict=True):
        assert row[:5] == (wave.board, wave.channel, wave.timestamp, wave.baseline, wave.trunc)
        np.testing.assert_array_equal(row[5], wave.waveform.astype(np.uint16))


class TestV1725Reader:
    def test_v1725_spec_marks_sample_index_timestamps(self):
        assert get_adapter("v1725").format_spec.raw_timestamp_mode == RawTimestampMode.SAMPLE_INDEX

    def test_iter_waves_extracts_board_from_bseg_filename(self, tmp_path: Path):
        raw = tmp_path / "test_raw_b7_seg0.bin"
        raw.write_bytes(make_v1725_single_wave_blob(channel=1, timestamp=77, baseline=555))

        waves = list(V1725Reader().iter_waves([raw]))

        assert len(waves) == 1
        assert waves[0].board == 7
        assert waves[0].channel == 1
        assert waves[0].timestamp == 77
        assert waves[0].baseline == 555

    def test_internal_array_batches_expose_primitive_columns_and_wave_views(self, tmp_path: Path):
        raw = tmp_path / "test_raw_b6_seg0.bin"
        blobs = [
            make_v1725_single_wave_blob(
                channel=channel,
                timestamp=timestamp,
                baseline=baseline,
                trunc=trunc,
                samples=np.array(samples, dtype=np.int16),
            )
            for channel, timestamp, baseline, trunc, samples in [
                (1, 30, 101, False, [1, -2]),
                (0, 10, 202, True, [-32768, 5, 6, 7]),
                (3, 20, 303, False, [6, 7, 8, 9, 10, 11]),
            ]
        ]
        raw.write_bytes(b"".join(blobs))

        reader = V1725Reader(buffer_size=48)
        batches = list(reader._iter_wave_array_batches([raw]))
        waves = list(reader.iter_waves([raw]))

        assert sum(len(batch) for batch in batches) == len(waves) == 3
        for batch in batches:
            assert batch.timestamps.ndim == 1
            assert batch.boards.dtype == np.int16
            assert batch.channels.dtype == np.int16
            assert batch.baselines.dtype == np.uint16
            assert batch.truncs.dtype == np.bool_
            assert batch.waveform_offsets.dtype == np.int64
            assert batch.waveform_lengths.dtype == np.int32

        actual = []
        for batch in batches:
            for idx in range(len(batch)):
                start = int(batch.waveform_offsets[idx])
                stop = start + int(batch.waveform_lengths[idx])
                actual.append(
                    (
                        int(batch.boards[idx]),
                        int(batch.channels[idx]),
                        int(batch.timestamps[idx]),
                        int(batch.baselines[idx]),
                        bool(batch.truncs[idx]),
                        batch.waveform_samples[start:stop],
                    )
                )

        assert [row[:5] for row in actual] == [
            (w.board, w.channel, w.timestamp, w.baseline, w.trunc) for w in waves
        ]
        for row, wave in zip(actual, waves, strict=True):
            np.testing.assert_array_equal(row[5], wave.waveform.astype(np.uint16))

    def test_iter_waves_legacy_name_defaults_board_zero(self, tmp_path: Path):
        raw = tmp_path / "CH1_0.bin"
        raw.write_bytes(make_v1725_single_wave_blob(channel=1, timestamp=88, baseline=444))

        waves = list(V1725Reader().iter_waves([raw]))

        assert len(waves) == 1
        assert waves[0].board == 0

    def test_build_records_from_v1725_files_keeps_board_from_filename(self, tmp_path: Path):
        raw0 = tmp_path / "test_raw_b3_seg0.bin"
        raw1 = tmp_path / "test_raw_b4_seg1.bin"
        raw0.write_bytes(make_v1725_single_wave_blob(channel=0, timestamp=10, baseline=100))
        raw1.write_bytes(make_v1725_single_wave_blob(channel=1, timestamp=20, baseline=200))

        bundle = build_records_from_v1725_files([str(raw0), str(raw1)], dt_ns=4)

        assert len(bundle.records) == 2
        np.testing.assert_array_equal(bundle.records["board"], np.array([3, 4], dtype=np.int16))
        np.testing.assert_array_equal(bundle.records["channel"], np.array([0, 1], dtype=np.int16))

    def test_optimized_vs_legacy_correctness(self, tmp_path: Path):
        """验证优化路径和原始路径输出一致。"""
        # 创建测试文件，包含多个事件
        raw = tmp_path / "test_raw_b0_seg0.bin"

        # 生成多个波形的二进制数据
        blobs = []
        for i in range(50):  # 50 个事件
            blobs.append(
                make_v1725_single_wave_blob(
                    channel=i % 8, timestamp=i * 100, baseline=500 + i  # 8 个通道
                )
            )
        raw.write_bytes(b"".join(blobs))

        # 使用优化路径读取
        reader_optimized = V1725Reader(use_optimized=True)
        waves_optimized = list(reader_optimized.iter_waves([raw]))

        # 使用原始路径读取
        reader_legacy = V1725Reader(use_optimized=False)
        waves_legacy = list(reader_legacy.iter_waves([raw]))

        # 验证数量一致
        assert len(waves_optimized) == len(waves_legacy)

        # 验证每个波形的数据一致
        for w_opt, w_leg in zip(waves_optimized, waves_legacy, strict=False):
            assert w_opt.board == w_leg.board
            assert w_opt.channel == w_leg.channel
            assert w_opt.timestamp == w_leg.timestamp
            assert w_opt.baseline == w_leg.baseline
            assert w_opt.trunc == w_leg.trunc
            np.testing.assert_array_equal(w_opt.waveform, w_leg.waveform)

    def test_all_optimized_reader_interfaces_consume_full_windows_without_rewinds(
        self, tmp_path: Path, monkeypatch
    ):
        raw = tmp_path / "test_raw_b0_seg0.bin"
        event_count = 2_500
        events = [
            make_v1725_single_wave_blob(
                channel=0,
                timestamp=i,
                samples=np.array([i, -i], dtype=np.int16),
            )
            for i in range(event_count)
        ]
        raw_bytes = b"".join(events)
        raw.write_bytes(raw_bytes)
        events_per_window = 1_200
        buffer_size = len(events[0]) * events_per_window
        assert len(raw_bytes) > 2 * buffer_size

        original_open = Path.open
        opened_readers = []

        class CountingReader:
            def __init__(self, path: Path, file_obj):
                self.path = path
                self.file_obj = file_obj
                self.bytes_read = 0
                self.read_calls = 0
                self.seek_calls = 0

            def __enter__(self):
                self.file_obj.__enter__()
                return self

            def __exit__(self, exc_type, exc_value, traceback):
                return self.file_obj.__exit__(exc_type, exc_value, traceback)

            def read(self, size=-1):
                data = self.file_obj.read(size)
                self.bytes_read += len(data)
                self.read_calls += 1
                return data

            def tell(self):
                return self.file_obj.tell()

            def seek(self, offset, whence=0):
                self.seek_calls += 1
                return self.file_obj.seek(offset, whence)

        def counted_open(path, *args, **kwargs):
            reader = CountingReader(path, original_open(path, *args, **kwargs))
            opened_readers.append(reader)
            return reader

        monkeypatch.setattr(Path, "open", counted_open)

        def run_without_rewind(read):
            reader_start = len(opened_readers)
            result = read()
            raw_readers = [item for item in opened_readers[reader_start:] if item.path == raw]
            assert len(raw_readers) == 1
            assert raw_readers[0].read_calls == 4  # Three windows plus EOF.
            assert raw_readers[0].bytes_read == len(raw_bytes)
            assert raw_readers[0].seek_calls == 0
            return result

        waves = run_without_rewind(
            lambda: list(V1725Reader(buffer_size=buffer_size).iter_waves([raw]))
        )
        wave_batches = run_without_rewind(
            lambda: list(
                V1725Reader(buffer_size=buffer_size).iter_waves_batched([raw], batch_size=257)
            )
        )
        array_batches = run_without_rewind(
            lambda: list(
                V1725Reader(buffer_size=buffer_size)._iter_wave_array_batches([raw], batch_size=257)
            )
        )

        expected_timestamps = np.arange(event_count, dtype=np.uint64)
        assert len(waves) == event_count
        np.testing.assert_array_equal(
            np.fromiter((wave.timestamp for wave in waves), dtype=np.uint64),
            expected_timestamps,
        )
        assert all(0 < len(batch) <= 257 for batch in wave_batches)
        flattened_wave_batches = [wave for batch in wave_batches for wave in batch]
        np.testing.assert_array_equal(
            np.fromiter((wave.timestamp for wave in flattened_wave_batches), dtype=np.uint64),
            expected_timestamps,
        )
        assert all(0 < len(batch) <= 257 for batch in array_batches)
        _assert_array_batch_rows_match_waves(array_batches, waves)

    def test_iter_waves_batched_legacy_fallback_preserves_order(self, tmp_path: Path):
        raw = tmp_path / "test_raw_b0_seg0.bin"
        blobs = [
            make_v1725_single_wave_blob(
                channel=index % 2,
                timestamp=timestamp,
                samples=np.array([index, -index], dtype=np.int16),
            )
            for index, timestamp in enumerate([30, 10, 20, 0, 40])
        ]
        raw.write_bytes(b"".join(blobs))

        reader = V1725Reader(use_optimized=False)
        batches = list(reader.iter_waves_batched([raw], batch_size=2))
        waves = list(V1725Reader(use_optimized=False).iter_waves([raw]))
        flattened = [wave for batch in batches for wave in batch]

        assert [len(batch) for batch in batches] == [2, 2, 1]
        assert [wave.timestamp for wave in flattened] == [wave.timestamp for wave in waves]
        for actual, expected in zip(flattened, waves, strict=True):
            assert actual.channel == expected.channel
            assert actual.waveform.tobytes() == expected.waveform.tobytes()

    def test_empty_file_yields_no_waves_or_batches(self, tmp_path: Path):
        raw = tmp_path / "empty_raw_b0_seg0.bin"
        raw.touch()

        assert list(V1725Reader().iter_waves([raw])) == []
        assert list(V1725Reader().iter_waves_batched([raw], batch_size=10)) == []

    def test_optimized_reader_preserves_multi_channel_events_across_buffer_boundaries(
        self, tmp_path: Path
    ):
        raw = tmp_path / "test_raw_b5_seg0.bin"
        events = [_make_multi_channel_event(event_id=i, channels=7, samples=1500) for i in range(4)]
        raw.write_bytes(b"".join(events))

        # One event fits, but the second event crosses this read boundary.
        buffer_size = len(events[0]) + len(events[0]) // 2
        optimized = list(V1725Reader(buffer_size=buffer_size).iter_waves([raw]))
        optimized_batched = [
            wave
            for batch in V1725Reader(buffer_size=buffer_size).iter_waves_batched(
                [raw], batch_size=2
            )
            for wave in batch
        ]
        array_batches = list(V1725Reader(buffer_size=buffer_size)._iter_wave_array_batches([raw]))
        legacy = list(V1725Reader(use_optimized=False).iter_waves([raw]))

        assert len(optimized) == len(optimized_batched) == len(legacy) == 28
        _assert_array_batch_rows_match_waves(array_batches, legacy)
        for actual_waves in (optimized, optimized_batched):
            for actual, expected in zip(actual_waves, legacy, strict=True):
                assert actual.board == expected.board
                assert actual.channel == expected.channel
                assert actual.timestamp == expected.timestamp
                assert actual.baseline == expected.baseline
                assert actual.trunc == expected.trunc
                np.testing.assert_array_equal(actual.waveform, expected.waveform)

    def test_optimized_reader_grows_window_for_event_larger_than_buffer(self, tmp_path: Path):
        raw = tmp_path / "test_raw_b2_seg0.bin"
        events = [
            _make_multi_channel_event(event_id=0, channels=1, samples=2),
            _make_multi_channel_event(event_id=1, channels=7, samples=15_000),
            _make_multi_channel_event(event_id=2, channels=1, samples=2),
        ]
        raw.write_bytes(b"".join(events))

        optimized = list(V1725Reader(buffer_size=64 * 1024).iter_waves([raw]))
        array_batches = list(V1725Reader(buffer_size=64 * 1024)._iter_wave_array_batches([raw]))
        legacy = list(V1725Reader(use_optimized=False).iter_waves([raw]))

        assert len(events[1]) > 64 * 1024
        assert len(optimized) == len(legacy) == 9
        _assert_array_batch_rows_match_waves(array_batches, legacy)
        for actual, expected in zip(optimized, legacy, strict=True):
            assert actual.timestamp == expected.timestamp
            np.testing.assert_array_equal(actual.waveform, expected.waveform)

    def test_optimized_reader_discards_truncated_final_event(self, tmp_path: Path, caplog):
        raw = tmp_path / "test_raw_b0_seg0.bin"
        complete = _make_multi_channel_event(event_id=0, channels=2, samples=10)
        truncated = _make_multi_channel_event(event_id=1, channels=2, samples=10)[:-5]
        raw.write_bytes(complete + truncated)

        waves = list(V1725Reader(buffer_size=len(complete) + 8).iter_waves([raw]))
        array_batches = list(
            V1725Reader(buffer_size=len(complete) + 8)._iter_wave_array_batches([raw])
        )

        assert len(waves) == 2
        assert sum(len(batch) for batch in array_batches) == 2
        _assert_array_batch_rows_match_waves(array_batches, waves)
        assert "Truncated V1725 event" in caplog.text

    def test_array_reader_empty_file_emits_no_rows(self, tmp_path: Path):
        raw = tmp_path / "empty_raw_b0_seg0.bin"
        raw.write_bytes(b"")

        assert list(V1725Reader()._iter_wave_array_batches([raw])) == []

    def test_numba_channel_header_parser_matches_expected_values(self):
        header0 = make_v1725_single_wave_blob(
            channel=0,
            timestamp=0x010203040506,
            baseline=0x0A0B,
            trunc=True,
            samples=np.array([1, 2, 3, 4], dtype=np.int16),
        )[16:28]
        header1 = make_v1725_single_wave_blob(
            channel=1,
            timestamp=123,
            baseline=456,
            trunc=False,
            samples=np.array([5, 6], dtype=np.int16),
        )[16:28]
        headers = np.frombuffer(header0 + header1, dtype=np.uint8).reshape(2, 12)

        ch_sizes, timestamps, truncs, baselines = parse_channel_headers_numba(headers)

        np.testing.assert_array_equal(ch_sizes, np.array([5, 4], dtype=np.uint32))
        np.testing.assert_array_equal(
            timestamps,
            np.array([0x010203040506, 123], dtype=np.uint64),
        )
        np.testing.assert_array_equal(truncs, np.array([True, False], dtype=np.bool_))
        np.testing.assert_array_equal(baselines, np.array([0x0A0B, 456], dtype=np.uint16))

    def test_v1725_records_small_part_size_matches_legacy_reader(self, tmp_path: Path):
        raw = tmp_path / "test_raw_b2_seg0.bin"
        blobs = []
        expected_waves = []
        for i, timestamp in enumerate([300, 100, 200, 100]):
            samples = np.array([i * 10 + 1, i * 10 + 2], dtype=np.int16)
            blobs.append(
                make_v1725_single_wave_blob(
                    channel=i % 2,
                    timestamp=timestamp,
                    baseline=400 + i,
                    trunc=i == 2,
                    samples=samples,
                )
            )
            expected_waves.append(samples.astype(np.uint16))
        raw.write_bytes(b"".join(blobs))

        bundle = build_records_from_v1725_files([str(raw)], dt_ns=4, v1725_part_size=2)

        assert len(bundle.records) == 4
        np.testing.assert_array_equal(
            bundle.records["timestamp"], np.array([400_000, 400_000, 800_000, 1_200_000])
        )
        np.testing.assert_array_equal(bundle.records["record_id"], np.arange(4, dtype=np.int64))
        np.testing.assert_array_equal(bundle.records["wave_offset"], np.array([0, 2, 4, 6]))
        np.testing.assert_array_equal(
            bundle.records["flags"], np.array([0, 0, 1, 0], dtype=np.uint32)
        )
        np.testing.assert_array_equal(
            bundle.wave_pool,
            np.concatenate(
                [
                    expected_waves[1],
                    expected_waves[3],
                    expected_waves[2],
                    expected_waves[0],
                ]
            ),
        )

    def test_array_records_builder_matches_wave_object_builder_byte_for_byte(
        self, tmp_path: Path, monkeypatch
    ):
        raw = tmp_path / "test_raw_b2_seg0.bin"
        blobs = []
        for channel, timestamp, baseline, trunc, samples in [
            (1, 300, 400, False, [-1, 2, 3, 4]),
            (0, 100, 401, False, [4, -5]),
            (1, 200, 402, True, [-32768, 7, 8, 9]),
            (0, 100, 403, False, [10, 11]),
        ]:
            blobs.append(
                make_v1725_single_wave_blob(
                    channel=channel,
                    timestamp=timestamp,
                    baseline=baseline,
                    trunc=trunc,
                    samples=np.array(samples, dtype=np.int16),
                )
            )
        raw.write_bytes(b"".join(blobs))

        expected_waves = list(V1725Reader().iter_waves([raw]))
        expected = _build_v1725_records_part_from_waves(expected_waves, default_dt_ns=4)

        array_batches = list(V1725Reader(buffer_size=48)._iter_wave_array_batches([raw]))
        actual_part = _build_v1725_records_part_from_array_batches(array_batches, default_dt_ns=4)
        assert actual_part.records.dtype == RECORDS_DTYPE
        assert actual_part.records.tobytes() == expected.records.tobytes()
        assert actual_part.wave_pool.tobytes() == expected.wave_pool.tobytes()

        refs = _process_v1725_file_to_disk(
            str(raw),
            V1725Reader(),
            dt_ns=4,
            part_dir=tmp_path / "array-parts",
            part_idx=0,
            part_size=2,
        )
        assert [part.n_records for part in refs] == [2, 2]

        def reject_wave_object_path(*args, **kwargs):
            raise AssertionError("array fast path constructed V1725Wave objects")

        monkeypatch.setattr(V1725Reader, "_process_channel_batch", reject_wave_object_path)
        actual = build_records_from_v1725_files(
            [str(raw)], dt_ns=4, n_jobs=1, keep_on_disk=False, v1725_part_size=2
        )
        assert actual.records.dtype == expected.records.dtype
        assert actual.records.tobytes() == expected.records.tobytes()
        assert actual.wave_pool.tobytes() == expected.wave_pool.tobytes()

    def test_v1725_file_builder_falls_back_to_iter_waves_reader(self, tmp_path: Path):
        raw = tmp_path / "test_raw_b1_seg0.bin"
        raw.write_bytes(
            make_v1725_single_wave_blob(
                channel=2,
                timestamp=9,
                baseline=25,
                trunc=True,
                samples=np.array([-3, 4], dtype=np.int16),
            )
        )

        class LegacyOnlyReader:
            def __init__(self):
                self._delegate = V1725Reader()

            def iter_waves(self, file_paths):
                return self._delegate.iter_waves(file_paths)

        expected = _build_v1725_records_part_from_waves(
            list(V1725Reader().iter_waves([raw])), default_dt_ns=2
        )
        refs = _process_v1725_file_to_disk(
            str(raw),
            LegacyOnlyReader(),
            dt_ns=2,
            part_dir=tmp_path / "fallback-parts",
            part_idx=0,
            part_size=0,
        )

        assert len(refs) == 1
        actual_records = np.memmap(
            refs[0].records_path, dtype=RECORDS_DTYPE, mode="r", shape=(refs[0].n_records,)
        )
        actual_wave_pool = np.memmap(
            refs[0].wave_pool_path,
            dtype=np.uint16,
            mode="r",
            shape=(refs[0].n_samples,),
        )
        assert actual_records.tobytes() == expected.records.tobytes()
        assert actual_wave_pool.tobytes() == expected.wave_pool.tobytes()

    def test_records_builder_uses_legacy_reader_when_optimization_is_disabled(self, tmp_path: Path):
        raw = tmp_path / "test_raw_b2_seg0.bin"
        raw.write_bytes(
            b"".join(
                [
                    make_v1725_single_wave_blob(
                        channel=1,
                        timestamp=30,
                        samples=np.array([-1, 2], dtype=np.int16),
                    ),
                    make_v1725_single_wave_blob(
                        channel=0,
                        timestamp=10,
                        samples=np.array([3, -4, 5], dtype=np.int16),
                    ),
                    make_v1725_single_wave_blob(
                        channel=1,
                        timestamp=20,
                        trunc=True,
                        samples=np.array([6, -7], dtype=np.int16),
                    ),
                ]
            )
        )

        legacy_waves = list(V1725Reader(use_optimized=False).iter_waves([raw]))
        optimized_waves = list(V1725Reader(use_optimized=True).iter_waves([raw]))
        assert [wave.timestamp for wave in legacy_waves] == [
            wave.timestamp for wave in optimized_waves
        ]
        expected = _build_v1725_records_part_from_waves(optimized_waves, default_dt_ns=2)

        refs = _process_v1725_file_to_disk(
            str(raw),
            V1725Reader(use_optimized=False),
            dt_ns=2,
            part_dir=tmp_path / "optimized-disabled-parts",
            part_idx=0,
            part_size=0,
        )

        assert len(refs) == 1
        actual_records = np.memmap(
            refs[0].records_path, dtype=RECORDS_DTYPE, mode="r", shape=(refs[0].n_records,)
        )
        actual_wave_pool = np.memmap(
            refs[0].wave_pool_path,
            dtype=np.uint16,
            mode="r",
            shape=(refs[0].n_samples,),
        )
        assert actual_records.tobytes() == expected.records.tobytes()
        assert actual_wave_pool.tobytes() == expected.wave_pool.tobytes()

    def test_v1725_records_multi_file_parallel_keeps_global_order(self, tmp_path: Path):
        raw0 = tmp_path / "test_raw_b3_seg0.bin"
        raw1 = tmp_path / "test_raw_b4_seg0.bin"
        raw0.write_bytes(
            b"".join(
                [
                    make_v1725_single_wave_blob(channel=1, timestamp=30, baseline=100),
                    make_v1725_single_wave_blob(channel=0, timestamp=10, baseline=101),
                ]
            )
        )
        raw1.write_bytes(make_v1725_single_wave_blob(channel=2, timestamp=20, baseline=200))

        bundle = build_records_from_v1725_files(
            [str(raw0), str(raw1)],
            dt_ns=4,
            n_jobs=2,
            v1725_part_size=1,
        )

        np.testing.assert_array_equal(
            bundle.records["timestamp"], np.array([40_000, 80_000, 120_000])
        )
        np.testing.assert_array_equal(bundle.records["board"], np.array([3, 4, 3], dtype=np.int16))
        np.testing.assert_array_equal(
            bundle.records["channel"], np.array([0, 2, 1], dtype=np.int16)
        )

    def test_optimized_performance_benchmark(self, tmp_path: Path):
        """性能基准测试：验证优化效果（测量稳态性能，不含一次性 JIT 编译）。"""
        # 构造接近真实规模的测试数据：500 个事件 × 16 通道 × 2048 采样点
        # （约 33MB，8000 条波形）。真实 V1725 波形为多通道、数千采样点；
        # 过小的数据（如单通道 2 采样点的小 blob）无法体现批量 I/O 与
        # 向量化解析的优势，且优化路径每波形的固定开销会主导耗时。
        raw = tmp_path / "test_raw_b0_seg0.bin"
        events = [
            _make_multi_channel_event(event_id=i, channels=16, samples=2048) for i in range(500)
        ]
        raw.write_bytes(b"".join(events))

        reader_legacy = V1725Reader(use_optimized=False)
        reader_optimized = V1725Reader(use_optimized=True)

        # 预热优化路径：首次调用包含 numba JIT 编译（一次性 ~250ms 固定开销），
        # 属于启动成本而非稳态性能，不应计入基准。
        list(reader_optimized.iter_waves([raw]))

        def _bench(reader):
            # best-of-3 取最快一次，降低机器噪声对基准的影响
            best = float("inf")
            waves = []
            for _ in range(3):
                start = time.perf_counter()
                waves = list(reader.iter_waves([raw]))
                best = min(best, time.perf_counter() - start)
            return best, waves

        time_legacy, waves_legacy = _bench(reader_legacy)
        time_optimized, waves_optimized = _bench(reader_optimized)

        assert len(waves_optimized) == len(waves_legacy) == 500 * 16
        for w_opt, w_leg in zip(waves_optimized, waves_legacy, strict=False):
            assert w_opt.board == w_leg.board
            assert w_opt.channel == w_leg.channel
            assert w_opt.timestamp == w_leg.timestamp
            assert w_opt.baseline == w_leg.baseline
            assert w_opt.trunc == w_leg.trunc
            np.testing.assert_array_equal(w_opt.waveform, w_leg.waveform)

        # 计算加速比
        speedup = time_legacy / time_optimized

        # 输出性能信息
        print("\n性能基准测试结果:")
        print(f"  事件数: {len(waves_optimized)}")
        print(f"  原始实现: {time_legacy*1000:.2f} ms")
        print(f"  优化实现: {time_optimized*1000:.2f} ms")
        print(f"  加速比: {speedup:.2f}x")
        print(f"  吞吐量: {len(waves_optimized)/time_optimized:.1f} events/s (优化)")
        print(f"  吞吐量: {len(waves_legacy)/time_legacy:.1f} events/s (原始)")
        print("\n已实现优化:")
        print("  ✓ 阶段 1: 批量 I/O（减少系统调用 ~100x）")
        print("  ✓ 阶段 2: 向量化解析（NumPy 批量处理通道头）")
        print("  ✓ 基准测量稳态性能：预热 numba JIT（一次性编译）后取 best-of-3")

        # 验证没有性能退化（稳态加速比实测 ~1.2-1.4x，阈值 0.95 留有余量）
        assert speedup >= 0.95, f"Performance regression detected: {speedup:.2f}x"
