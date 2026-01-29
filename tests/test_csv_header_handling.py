"""
CSV 表头处理测试

测试 CSV 文件读取时的表头处理逻辑：
- 每个通道的第一个文件包含表头，需要跳过
- 后续文件不包含表头，不需要跳过
"""

import numpy as np
import pytest

from tests.utils import make_csv_with_header, make_csv_without_header
from waveform_analysis.utils.io import parse_and_stack_files, parse_files_generator


def test_parse_and_stack_files_with_mixed_headers(tmp_path):
    """测试 parse_and_stack_files 正确处理混合表头情况"""
    raw_dir = tmp_path / "RAW"
    raw_dir.mkdir(parents=True)
    
    # 创建第一个文件（带表头）
    make_csv_with_header(raw_dir, ch=0, idx=0, start_tag=1000, end_tag=2000, n_samples=10)
    
    # 创建后续文件（不带表头）
    make_csv_without_header(raw_dir, ch=0, idx=1, start_tag=2001, end_tag=3000, n_samples=10)
    make_csv_without_header(raw_dir, ch=0, idx=2, start_tag=3001, end_tag=4000, n_samples=10)
    
    files = [
        str(raw_dir / "RUN_CH0_0.CSV"),
        str(raw_dir / "RUN_CH0_1.CSV"),
        str(raw_dir / "RUN_CH0_2.CSV"),
    ]
    
    result = parse_and_stack_files(files, skiprows=2, delimiter=";")
    
    # 应该读取所有文件的数据行（每个文件3行，共9行）
    assert result.shape[0] == 9, f"Expected 9 rows, got {result.shape[0]}"
    assert result.shape[1] >= 13, f"Expected at least 13 columns (3 metadata + 10 samples), got {result.shape[1]}"
    
    # 验证时间戳列（第3列，索引为2）包含所有期望的值
    timestamps = result[:, 2].astype(int)
    expected_timestamps = [1000, 1500, 2000, 2001, 2500, 3000, 3001, 3500, 4000]
    assert len(timestamps) == len(expected_timestamps)
    assert np.allclose(timestamps, expected_timestamps), f"Timestamps mismatch: {timestamps} vs {expected_timestamps}"


def test_parse_and_stack_files_single_file_with_header(tmp_path):
    """测试单个文件（带表头）的情况"""
    raw_dir = tmp_path / "RAW"
    raw_dir.mkdir(parents=True)
    
    make_csv_with_header(raw_dir, ch=0, idx=0, start_tag=1000, end_tag=2000, n_samples=10)
    
    files = [str(raw_dir / "RUN_CH0_0.CSV")]
    
    result = parse_and_stack_files(files, skiprows=2, delimiter=";")
    
    # 应该读取3行数据（跳过了2行：元数据和表头）
    assert result.shape[0] == 3, f"Expected 3 rows, got {result.shape[0]}"


def test_parse_and_stack_files_multiple_files_no_header(tmp_path):
    """测试多个文件但都不带表头的情况（边界情况）"""
    raw_dir = tmp_path / "RAW"
    raw_dir.mkdir(parents=True)
    
    # 创建多个不带表头的文件
    make_csv_without_header(raw_dir, ch=0, idx=0, start_tag=1000, end_tag=2000, n_samples=10)
    make_csv_without_header(raw_dir, ch=0, idx=1, start_tag=2001, end_tag=3000, n_samples=10)
    
    files = [
        str(raw_dir / "RUN_CH0_0.CSV"),
        str(raw_dir / "RUN_CH0_1.CSV"),
    ]
    
    result = parse_and_stack_files(files, skiprows=2, delimiter=";")
    
    # 第一个文件会被跳过2行（但文件本身没有表头，所以会跳过数据行）
    # 第二个文件不跳过
    # 这个测试主要验证不会因为错误的skiprows导致崩溃
    assert result.shape[0] >= 3, f"Expected at least 3 rows, got {result.shape[0]}"


def test_parse_files_generator_with_mixed_headers(tmp_path):
    """测试 parse_files_generator 正确处理混合表头情况"""
    raw_dir = tmp_path / "RAW"
    raw_dir.mkdir(parents=True)
    
    # 创建第一个文件（带表头）
    make_csv_with_header(raw_dir, ch=0, idx=0, start_tag=1000, end_tag=2000, n_samples=10)
    
    # 创建后续文件（不带表头）
    make_csv_without_header(raw_dir, ch=0, idx=1, start_tag=2001, end_tag=3000, n_samples=10)
    
    files = [
        str(raw_dir / "RUN_CH0_0.CSV"),
        str(raw_dir / "RUN_CH0_1.CSV"),
    ]
    
    chunks = list(parse_files_generator(files, skiprows=2, delimiter=";", chunksize=1000))
    
    # 合并所有chunks
    if chunks:
        result = np.vstack(chunks)
        # 应该读取所有文件的数据行（每个文件3行，共6行）
        assert result.shape[0] == 6, f"Expected 6 rows, got {result.shape[0]}"
        
        # 验证时间戳
        timestamps = result[:, 2].astype(int)
        expected_timestamps = [1000, 1500, 2000, 2001, 2500, 3000]
        assert len(timestamps) == len(expected_timestamps)
        assert np.allclose(timestamps, expected_timestamps), f"Timestamps mismatch: {timestamps} vs {expected_timestamps}"


def test_parse_and_stack_files_parallel_processing(tmp_path):
    """测试并行处理时表头处理是否正确"""
    raw_dir = tmp_path / "RAW"
    raw_dir.mkdir(parents=True)
    
    # 创建多个文件
    make_csv_with_header(raw_dir, ch=0, idx=0, start_tag=1000, end_tag=2000, n_samples=10)
    make_csv_without_header(raw_dir, ch=0, idx=1, start_tag=2001, end_tag=3000, n_samples=10)
    make_csv_without_header(raw_dir, ch=0, idx=2, start_tag=3001, end_tag=4000, n_samples=10)
    
    files = [
        str(raw_dir / "RUN_CH0_0.CSV"),
        str(raw_dir / "RUN_CH0_1.CSV"),
        str(raw_dir / "RUN_CH0_2.CSV"),
    ]
    
    # 使用并行处理
    result_parallel = parse_and_stack_files(files, skiprows=2, delimiter=";", n_jobs=2)

    # 使用串行处理
    result_serial = parse_and_stack_files(files, skiprows=2, delimiter=";", n_jobs=1)

    # 结果应该相同
    assert result_parallel.shape == result_serial.shape
    # 由于数组可能包含字符串列，使用 array_equal 而不是 allclose
    assert np.array_equal(result_parallel, result_serial), "Parallel and serial results should match"


def test_parse_and_stack_files_channel_independence(tmp_path):
    """测试不同通道的表头处理是独立的"""
    raw_dir = tmp_path / "RAW"
    raw_dir.mkdir(parents=True)
    
    # 通道0：第一个文件带表头，后续不带
    make_csv_with_header(raw_dir, ch=0, idx=0, start_tag=1000, end_tag=2000, n_samples=10)
    make_csv_without_header(raw_dir, ch=0, idx=1, start_tag=2001, end_tag=3000, n_samples=10)
    
    # 通道1：第一个文件带表头，后续不带
    make_csv_with_header(raw_dir, ch=1, idx=0, start_tag=5000, end_tag=6000, n_samples=10)
    make_csv_without_header(raw_dir, ch=1, idx=1, start_tag=6001, end_tag=7000, n_samples=10)
    
    files_ch0 = [
        str(raw_dir / "RUN_CH0_0.CSV"),
        str(raw_dir / "RUN_CH0_1.CSV"),
    ]
    
    files_ch1 = [
        str(raw_dir / "RUN_CH1_0.CSV"),
        str(raw_dir / "RUN_CH1_1.CSV"),
    ]
    
    result_ch0 = parse_and_stack_files(files_ch0, skiprows=2, delimiter=";")
    result_ch1 = parse_and_stack_files(files_ch1, skiprows=2, delimiter=";")
    
    # 每个通道应该独立处理，都读取6行数据
    assert result_ch0.shape[0] == 6, f"Channel 0: Expected 6 rows, got {result_ch0.shape[0]}"
    assert result_ch1.shape[0] == 6, f"Channel 1: Expected 6 rows, got {result_ch1.shape[0]}"
    
    # 验证时间戳不同
    timestamps_ch0 = result_ch0[:, 2].astype(int)
    timestamps_ch1 = result_ch1[:, 2].astype(int)
    assert not np.array_equal(timestamps_ch0, timestamps_ch1), "Different channels should have different timestamps"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

