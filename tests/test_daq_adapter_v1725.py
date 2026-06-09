"""V1725 reader tests."""

from pathlib import Path
import time

import numpy as np

from tests.daq_adapter_helpers import make_v1725_single_wave_blob
from waveform_analysis.core.processing.records_builder import build_records_from_v1725_files
from waveform_analysis.utils.formats import RawTimestampMode, V1725Reader, get_adapter
from waveform_analysis.utils.formats.v1725_numba import parse_channel_headers_numba


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
        """性能基准测试：验证优化效果。"""
        # 创建较大的测试文件
        raw = tmp_path / "test_raw_b0_seg0.bin"

        # 生成 2000 个波形（模拟中等规模文件）
        blobs = []
        for i in range(2000):
            blobs.append(
                make_v1725_single_wave_blob(
                    channel=i % 16, timestamp=i * 100, baseline=500 + i  # 16 个通道
                )
            )
        raw.write_bytes(b"".join(blobs))

        # 基准测试：原始实现
        reader_legacy = V1725Reader(use_optimized=False)
        start = time.perf_counter()
        waves_legacy = list(reader_legacy.iter_waves([raw]))
        time_legacy = time.perf_counter() - start

        # 基准测试：优化实现
        reader_optimized = V1725Reader(use_optimized=True)
        start = time.perf_counter()
        waves_optimized = list(reader_optimized.iter_waves([raw]))
        time_optimized = time.perf_counter() - start

        # 验证结果一致
        assert len(waves_optimized) == len(waves_legacy) == 2000

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
        print("\n注意：测试文件较小，实际大文件的性能提升会更显著")

        # 验证没有性能退化
        assert speedup >= 0.95, f"Performance regression detected: {speedup:.2f}x"
