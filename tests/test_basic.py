"""
基本功能测试
"""

import numpy as np
import pytest

from waveform_analysis import WaveformDataset, get_raw_files


def test_import():
    """测试包可以正常导入"""
    from waveform_analysis import (
        DAQAnalyzer,
        DAQRun,
        WaveformDataset,
        WaveformStruct,
        build_waveform_df,
        get_raw_files,
        get_waveforms,
        group_multi_channel_hits,
    )

    assert WaveformDataset is not None
    assert get_raw_files is not None
    assert DAQRun is not None
    assert DAQAnalyzer is not None


def test_waveform_struct():
    """测试波形结构化"""
    from waveform_analysis.core import WaveformStruct

    # 创建模拟数据
    mock_waveforms = [np.random.randn(100, 807), np.random.randn(100, 807)]

    struct = WaveformStruct(mock_waveforms)
    st_waveforms = struct.structure_waveforms()

    assert len(st_waveforms) == 2
    assert len(st_waveforms[0]) == 100


def test_waveform_struct_empty():
    """测试空波形结构化"""
    from waveform_analysis.core import WaveformStruct

    mock_waveforms = [np.array([]).reshape(0, 807), np.array([]).reshape(0, 807)]
    struct = WaveformStruct(mock_waveforms)
    st_waveforms = struct.structure_waveforms()

    assert len(st_waveforms) == 2
    assert len(st_waveforms[0]) == 0


def test_dataset_init():
    """测试数据集初始化"""
    try:
        dataset = WaveformDataset(run_name="test_dataset", n_channels=2, start_channel_slice=6)
        assert dataset.run_name == "test_dataset"
        assert dataset.n_channels == 2
        assert dataset.start_channel_slice == 6
        assert dataset.load_waveforms is True  # 默认值
    except FileNotFoundError:
        # 如果测试数据不存在，跳过
        pytest.skip("Test data not available")


def test_dataset_init_skip_waveforms():
    """测试数据集初始化（跳过波形加载）"""
    try:
        dataset = WaveformDataset(run_name="test_dataset", n_channels=2, load_waveforms=False)
        assert dataset.load_waveforms is False
    except FileNotFoundError:
        pytest.skip("Test data not available")


def test_dataset_attributes():
    """测试数据集属性初始化"""
    try:
        dataset = WaveformDataset(run_name="test", n_channels=2)

        # 检查容器初始化
        assert dataset.raw_files == []
        assert dataset.waveforms == []
        assert dataset.st_waveforms == []
        assert dataset.df is None
        assert dataset.df_events is None
        assert dataset.df_paired is None

        # 检查默认参数
        assert dataset.peaks_range == (40, 90)
        assert dataset.charge_range == (60, 400)
        assert dataset.time_window_ns == 100
    except FileNotFoundError:
        pytest.skip("Test data not available")


def test_dataset_step_tracking():
    """测试步骤状态跟踪"""
    try:
        dataset = WaveformDataset(char="test", n_channels=2)

        # 检查步骤跟踪初始化
        assert dataset._step_errors == {}
        assert dataset._step_status == {}
        assert dataset._last_failed_step is None
        assert dataset.raise_on_error is False
    except FileNotFoundError:
        pytest.skip("Test data not available")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
