"""
数据加载测试
"""

import os
from pathlib import Path

import numpy as np
import pytest

from waveform_analysis.core import get_raw_files, get_waveforms
from waveform_analysis.utils.loader import (
    RawFileLoader,
    build_filetime_index,
    get_files_before,
    get_files_by_filetime,
)


def test_raw_file_loader():
    """测试原始文件加载器初始化"""
    loader = RawFileLoader(n_channels=8, char="test")
    assert loader.n_channels == 8
    assert loader.base_dir.name == "RAW"


def test_raw_file_loader_extract():
    """测试文件名解析"""
    loader = RawFileLoader(n_channels=6, char="test")

    # 正常文件名
    result = loader._extract("DataR_CH0@VX2730_53013_test_0.CSV")
    assert result == (0, 0)

    result = loader._extract("DataR_CH5@VX2730_53013_test_123.CSV")
    assert result == (5, 123)

    # 无通道信息
    result = loader._extract("invalid_file.csv")
    assert result is None


def test_get_raw_files_empty_dir(tmp_path):
    """测试空目录返回空列表"""
    raw_dir = tmp_path / "DAQ" / "empty_run" / "RAW"
    raw_dir.mkdir(parents=True)

    loader = RawFileLoader(n_channels=2, char="empty_run")
    loader.base_dir = raw_dir

    files = loader.get_raw_files()
    assert len(files) == 2
    assert all(len(ch_files) == 0 for ch_files in files)


def test_get_raw_files_with_data(tmp_path, make_csv_fn):
    """测试带数据文件的加载"""
    raw_dir = tmp_path / "DAQ" / "test_run" / "RAW"
    raw_dir.mkdir(parents=True)

    # 创建测试文件
    make_csv_fn(raw_dir, ch=0, idx=0, start_tag=1000, end_tag=2000)
    make_csv_fn(raw_dir, ch=0, idx=1, start_tag=2001, end_tag=3000)
    make_csv_fn(raw_dir, ch=1, idx=0, start_tag=1000, end_tag=2000)

    loader = RawFileLoader(n_channels=2, char="test_run")
    loader.base_dir = raw_dir
    loader.pattern = "RUN_CH*_*.CSV"

    files = loader.get_raw_files()
    assert len(files) == 2
    assert len(files[0]) == 2  # CH0 有两个文件
    assert len(files[1]) == 1  # CH1 有一个文件


def test_get_waveforms_empty():
    """测试空输入返回空数组"""
    result = get_waveforms([[]])
    assert len(result) == 1
    assert result[0].size == 0


def test_get_waveforms_with_data(tmp_path, make_csv_fn):
    """测试波形数据加载"""
    raw_dir = tmp_path / "RAW"
    raw_dir.mkdir(parents=True)

    make_csv_fn(raw_dir, ch=0, idx=0, start_tag=1000, end_tag=2000, n_samples=50)

    files = [str(raw_dir / "RUN_CH0_0.CSV")]
    result = get_waveforms([files])

    assert len(result) == 1
    assert result[0].shape[0] == 3  # 3 行数据


def test_build_filetime_index(tmp_path, make_csv_fn):
    """测试文件时间索引构建"""
    raw_dir = tmp_path / "RAW"
    raw_dir.mkdir(parents=True)

    make_csv_fn(raw_dir, ch=0, idx=0, start_tag=1000, end_tag=2000)
    make_csv_fn(raw_dir, ch=0, idx=1, start_tag=2001, end_tag=3000)

    files = [[str(raw_dir / "RUN_CH0_0.CSV"), str(raw_dir / "RUN_CH0_1.CSV")]]
    index = build_filetime_index(files)

    assert len(index) == 1
    assert len(index[0]) == 2


def test_get_files_before():
    """测试获取指定文件之前的所有文件"""
    raw_filess = [["file0.csv", "file1.csv", "file2.csv"]]
    files_by_time = {0: "file1.csv"}

    result = get_files_before(raw_filess, files_by_time)
    assert result[0] == ["file0.csv", "file1.csv"]


def test_get_files_before_not_found():
    """测试目标文件不在列表中的情况"""
    raw_filess = [["file0.csv", "file1.csv"]]
    files_by_time = {0: "file_not_exist.csv"}

    result = get_files_before(raw_filess, files_by_time)
    assert result[0] == ["file_not_exist.csv"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
