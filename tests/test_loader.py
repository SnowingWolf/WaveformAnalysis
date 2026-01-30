"""
数据加载测试
"""

from pathlib import Path

import pytest

from waveform_analysis.core.processing.loader import WaveformLoaderCSV, get_waveforms


def test_raw_file_loader():
    """测试原始文件加载器初始化"""
    loader = WaveformLoaderCSV(n_channels=8, char="test")
    assert loader.n_channels == 8
    assert loader.base_dir.name == "RAW"


def test_raw_file_loader_extract():
    """测试文件名解析"""
    loader = WaveformLoaderCSV(n_channels=6, char="test")

    # 正常文件名
    result = loader._extract("DataR_CH0@VX2730_53013_test_0.CSV")
    assert result == (0, 0)

    result = loader._extract("DataR_CH5@VX2730_53013_test_123.CSV")
    assert result == (5, 123)

    # 无通道信息
    result = loader._extract("invalid_file.csv")
    assert result is None


def test_get_raw_files_empty_dir(tmp_path):
    """空目录下返回空通道列表（默认适配器）"""
    raw_dir = tmp_path / "DAQ" / "empty_run" / "RAW"
    raw_dir.mkdir(parents=True)

    loader = WaveformLoaderCSV(n_channels=2, char="empty_run", data_root=str(tmp_path / "DAQ"))

    raw_filess = loader.get_raw_files()
    assert len(raw_filess) == 2
    assert raw_filess == [[], []]


def test_get_raw_files_with_data(tmp_path, make_csv_fn):
    """有文件时返回按通道分组的列表（默认适配器）"""
    raw_dir = tmp_path / "DAQ" / "test_run" / "RAW"
    raw_dir.mkdir(parents=True)

    # 创建测试文件
    make_csv_fn(raw_dir, ch=0, idx=0, start_tag=1000, end_tag=2000)
    make_csv_fn(raw_dir, ch=0, idx=1, start_tag=2001, end_tag=3000)
    make_csv_fn(raw_dir, ch=1, idx=0, start_tag=1000, end_tag=2000)

    loader = WaveformLoaderCSV(n_channels=2, char="test_run", data_root=str(tmp_path / "DAQ"))

    raw_filess = loader.get_raw_files()
    assert len(raw_filess) == 2
    assert [Path(p).name for p in raw_filess[0]] == ["RUN_CH0_0.CSV", "RUN_CH0_1.CSV"]
    assert [Path(p).name for p in raw_filess[1]] == ["RUN_CH1_0.CSV"]


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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
