"""
基本功能测试
"""

import numpy as np
import pytest

from waveform_analysis import WaveformDataset, get_raw_files


def test_import():
    """测试包可以正常导入"""
    from waveform_analysis import (
        WaveformDataset,
        WaveformStruct,
        build_waveform_df,
        get_raw_files,
        get_waveforms,
        group_multi_channel_hits,
    )

    assert WaveformDataset is not None
    assert get_raw_files is not None


def test_waveform_struct():
    """测试波形结构化"""
    from waveform_analysis.core import WaveformStruct

    # 创建模拟数据
    mock_waveforms = [np.random.randn(100, 807), np.random.randn(100, 807)]

    struct = WaveformStruct(mock_waveforms)
    st_waveforms = struct.structrue_waveforms()

    assert len(st_waveforms) == 2
    assert len(st_waveforms[0]) == 100


def test_dataset_init():
    """测试数据集初始化"""
    try:
        dataset = WaveformDataset(char="test_dataset", n_channels=2, start_channel_slice=6)
        assert dataset.char == "test_dataset"
        assert dataset.n_channels == 2
    except FileNotFoundError:
        # 如果测试数据不存在，跳过
        pytest.skip("Test data not available")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
