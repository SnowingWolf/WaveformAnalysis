"""测试 VX2730 适配器的采集时间计算修复

这个测试确保 DAQRun 正确处理 VX2730 的绝对时间戳，
而不是错误地将其当作相对时间戳。
"""

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from waveform_analysis.utils.daq import DAQRun


def test_vx2730_acquisition_time_calculation(tmp_path):
    """测试 VX2730 采集时间的正确计算

    VX2730 使用绝对时间戳（从设备启动开始累积），
    因此采集时长应该是 (max_timestamp - min_timestamp)，
    而不是简单的 max_timestamp。
    """
    # 创建测试文件结构
    run_name = "test_run"
    raw_dir = tmp_path / run_name / "RAW"
    raw_dir.mkdir(parents=True)

    # 创建测试数据文件
    # 模拟一个持续 100 秒的采集，时间戳从 5秒开始
    test_file = raw_dir / "DataR_CH0@VX2730_12345_test_run.CSV"

    start_timestamp_ps = 5_000_000_000_000  # 5 秒（绝对时间戳）
    end_timestamp_ps = 105_000_000_000_000  # 105 秒（绝对时间戳）
    expected_duration_s = 100.0  # 实际采集时长 = 105 - 5 = 100 秒

    # 写入测试数据
    with open(test_file, "w") as f:
        f.write("BOARD;CHANNEL;TIMETAG;ENERGY;ENERGYSHORT;FLAGS;PROBE_CODE;SAMPLES\n")
        # 第一个事件
        f.write(f"0;0;{start_timestamp_ps};100;100;0x4000;1;8000;8010;8020\n")
        # 中间事件
        f.write("0;0;50000000000000;100;100;0x4000;1;8000;8010;8020\n")
        # 最后一个事件
        f.write(f"0;0;{end_timestamp_ps};100;100;0x4000;1;8000;8010;8020\n")

    # 创建 DAQRun 实例
    run = DAQRun(run_name, tmp_path / run_name, daq_adapter="vx2730")

    # 计算采集时间
    stats = run.compute_acquisition_times()
    start_time, end_time = run.get_run_acquisition_window()

    # 验证时间戳范围
    assert stats[0]["start_time_ps"] == start_timestamp_ps
    assert stats[0]["end_time_ps"] == end_timestamp_ps

    # 验证采集时长
    assert abs(stats[0]["duration_s"] - expected_duration_s) < 0.001

    # 验证运行级别的时间窗口
    assert start_time is not None
    assert end_time is not None

    actual_duration = (end_time - start_time).total_seconds()
    assert abs(actual_duration - expected_duration_s) < 0.001

    # 验证结束时间是通过相对时间差计算的
    # 而不是使用绝对时间戳（如果使用绝对时间戳，结果会是 105 秒）
    assert actual_duration < 101.0  # 应该接近 100 秒，而不是 105 秒


def test_vx2730_multi_channel_consistency(tmp_path):
    """测试多通道的时间计算一致性"""
    run_name = "test_multi_channel"
    raw_dir = tmp_path / run_name / "RAW"
    raw_dir.mkdir(parents=True)

    # 创建两个通道的文件，使用相同的时间范围
    start_ps = 10_000_000_000_000  # 10 秒
    end_ps = 110_000_000_000_000  # 110 秒
    expected_duration = 100.0

    for ch in [0, 1]:
        test_file = raw_dir / f"DataR_CH{ch}@VX2730_12345_test_multi_channel.CSV"
        with open(test_file, "w") as f:
            f.write("BOARD;CHANNEL;TIMETAG;ENERGY;ENERGYSHORT;FLAGS;PROBE_CODE;SAMPLES\n")
            f.write(f"0;{ch};{start_ps};100;100;0x4000;1;8000;8010;8020\n")
            f.write(f"0;{ch};{end_ps};100;100;0x4000;1;8000;8010;8020\n")

    run = DAQRun(run_name, tmp_path / run_name, daq_adapter="vx2730")
    stats = run.compute_acquisition_times()

    # 验证两个通道的时长一致
    assert abs(stats[0]["duration_s"] - expected_duration) < 0.001
    assert abs(stats[1]["duration_s"] - expected_duration) < 0.001

    # 验证运行级别的时长
    start_time, end_time = run.get_run_acquisition_window()
    actual_duration = (end_time - start_time).total_seconds()
    assert abs(actual_duration - expected_duration) < 0.001


def test_vx2730_segmented_files(tmp_path):
    """测试分段文件的时间计算"""
    run_name = "test_segmented"
    raw_dir = tmp_path / run_name / "RAW"
    raw_dir.mkdir(parents=True)

    # 创建3个分段文件，每个覆盖不同的时间范围
    segments = [
        (0, 5_000_000_000_000, 55_000_000_000_000),  # 5-55 秒
        (1, 55_100_000_000_000, 105_000_000_000_000),  # 55.1-105 秒
        (2, 105_200_000_000_000, 155_000_000_000_000),  # 105.2-155 秒
    ]

    for idx, start_ps, end_ps in segments:
        test_file = raw_dir / f"DataR_CH0@VX2730_12345_test_segmented_{idx}.CSV"
        with open(test_file, "w") as f:
            if idx == 0:
                f.write("BOARD;CHANNEL;TIMETAG;ENERGY;ENERGYSHORT;FLAGS;PROBE_CODE;SAMPLES\n")
            f.write(f"0;0;{start_ps};100;100;0x4000;1;8000;8010;8020\n")
            f.write(f"0;0;{end_ps};100;100;0x4000;1;8000;8010;8020\n")

    run = DAQRun(run_name, tmp_path / run_name, daq_adapter="vx2730")
    stats = run.compute_acquisition_times()

    # 验证总时长：从第一个文件的开始到最后一个文件的结束
    # 155 - 5 = 150 秒
    expected_duration = 150.0
    assert abs(stats[0]["duration_s"] - expected_duration) < 0.001

    start_time, end_time = run.get_run_acquisition_window()
    actual_duration = (end_time - start_time).total_seconds()
    assert abs(actual_duration - expected_duration) < 0.001


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
