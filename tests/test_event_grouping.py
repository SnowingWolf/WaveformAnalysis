# -*- coding: utf-8 -*-
"""
processing 模块测试
"""

import numpy as np
import pandas as pd
import pytest

from waveform_analysis.core.processing.event_grouping import group_multi_channel_hits
from waveform_analysis.core.processing.waveform_struct import RECORD_DTYPE, WaveformStruct


class TestWaveformStruct:
    """WaveformStruct 类测试"""

    def test_init(self):
        """测试初始化"""
        waveforms = [np.random.randn(10, 807)]
        struct = WaveformStruct(waveforms)
        assert struct.waveforms is waveforms
        assert struct.event_length is None
        assert struct.waveform_structureds is None

    def test_structure_waveform_empty(self):
        """测试空波形结构化"""
        struct = WaveformStruct([])
        result = struct._structure_waveform()
        assert len(result) == 0
        assert result.dtype.names == np.dtype(RECORD_DTYPE).names

    def test_structure_waveform_with_data(self):
        """测试带数据的波形结构化"""
        # 创建模拟数据：807 列 (BOARD, CHANNEL, TIMETAG, ... + 800 samples)
        n_rows = 5
        waveforms = [np.random.randn(n_rows, 807)]
        # 设置 BOARD 列 (第0列)
        waveforms[0][:, 0] = 0
        # 设置 CHANNEL 列 (第1列)
        waveforms[0][:, 1] = 0
        # 设置 timestamp 列 (第2列，索引2)
        waveforms[0][:, 2] = np.arange(1000, 1000 + n_rows)

        struct = WaveformStruct(waveforms)
        # 创建通道映射：{(0, 0): 0}
        channel_mapping = {(0, 0): 0}
        result = struct._structure_waveform(waveforms[0], channel_mapping=channel_mapping)

        assert len(result) == n_rows
        assert "baseline" in result.dtype.names
        assert "timestamp" in result.dtype.names
        assert "channel" in result.dtype.names
        assert "wave" in result.dtype.names
        # 检查 channel 字段（应该从映射得到 0）
        assert np.all(result["channel"] == 0)

    def test_structure_waveforms(self):
        """测试多通道波形结构化"""
        n_rows = 10
        waveforms = [
            np.random.randn(n_rows, 807),
            np.random.randn(n_rows, 807),
        ]
        # 设置 BOARD 和 CHANNEL 列
        # 第一个通道：(0, 0) -> 映射到 0
        waveforms[0][:, 0] = 0  # BOARD
        waveforms[0][:, 1] = 0  # CHANNEL
        # 第二个通道：(0, 1) -> 映射到 1
        waveforms[1][:, 0] = 0  # BOARD
        waveforms[1][:, 1] = 1  # CHANNEL
        # 设置 timestamp 列
        for w in waveforms:
            w[:, 2] = np.arange(1000, 1000 + n_rows)

        struct = WaveformStruct(waveforms)
        result = struct.structure_waveforms(start_channel_slice=0)

        assert len(result) == 2
        assert len(result[0]) == n_rows
        # 检查 channel 字段（应该从 (BOARD, CHANNEL) 映射得到）
        assert np.all(result[0]["channel"] == 0)  # (0, 0) -> 0
        assert np.all(result[1]["channel"] == 1)  # (0, 1) -> 1
        assert len(result[1]) == n_rows

    def test_get_event_length_even(self):
        """测试偶数通道的事件长度（每个通道使用自己的长度）"""
        waveforms = [
            np.random.randn(100, 807),
            np.random.randn(80, 807),
            np.random.randn(90, 807),
            np.random.randn(85, 807),
        ]
        struct = WaveformStruct(waveforms)
        event_len = struct.get_event_length()

        assert len(event_len) == 4
        # 每个通道使用自己的实际长度（不再配对）
        assert event_len[0] == 100
        assert event_len[1] == 80
        assert event_len[2] == 90
        assert event_len[3] == 85

    def test_get_event_length_odd(self):
        """测试奇数通道的事件长度（每个通道使用自己的长度）"""
        waveforms = [
            np.random.randn(100, 807),
            np.random.randn(80, 807),
            np.random.randn(90, 807),
        ]
        struct = WaveformStruct(waveforms)
        event_len = struct.get_event_length()

        assert len(event_len) == 3
        # 每个通道使用自己的实际长度
        assert event_len[0] == 100
        assert event_len[1] == 80
        assert event_len[2] == 90


class TestGroupMultiChannelHits:
    """group_multi_channel_hits 函数测试"""

    def test_empty_df(self):
        """测试空 DataFrame"""
        df = pd.DataFrame(columns=["timestamp", "area", "height", "channel"])
        result = group_multi_channel_hits(df, time_window_ns=100)

        assert len(result) == 0
        assert "event_id" in result.columns

    def test_single_cluster(self):
        """测试单个事件簇"""
        df = pd.DataFrame({
            "timestamp": [1000000, 1000010, 1000020],  # 在 100ns 窗口内
            "area": [100, 200, 300],
            "height": [10, 20, 30],
            "channel": [0, 1, 0],
        })

        result = group_multi_channel_hits(df, time_window_ns=100)

        assert len(result) == 1
        assert result.iloc[0]["n_hits"] == 3

    def test_multiple_clusters(self):
        """测试多个事件簇"""
        df = pd.DataFrame({
            "timestamp": [1000000, 1000010, 2000000, 2000010],  # 两个簇
            "area": [100, 200, 300, 400],
            "height": [10, 20, 30, 40],
            "channel": [0, 1, 0, 1],
        })

        result = group_multi_channel_hits(df, time_window_ns=100)

        assert len(result) == 2
        assert result.iloc[0]["n_hits"] == 2
        assert result.iloc[1]["n_hits"] == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
