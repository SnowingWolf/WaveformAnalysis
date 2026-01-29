#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
双 Baseline 功能使用示例

演示如何使用 baseline 和 baseline_upstream 字段。
"""

import numpy as np
from waveform_analysis.core.processing.waveform_struct import WaveformStruct


def example_1_without_upstream():
    """示例 1: 不使用上游 baseline（默认行为）"""
    print("=" * 60)
    print("示例 1: 不使用上游 baseline")
    print("=" * 60)

    # 创建测试数据（模拟 VX2730 CSV 格式）
    n_events = 5
    wave_length = 800
    test_data = np.zeros((n_events, 807))

    # 填充元数据
    test_data[:, 0] = 0  # BOARD
    test_data[:, 1] = 0  # CHANNEL
    test_data[:, 2] = wave_length
    test_data[:, 3] = np.arange(n_events) * 1000  # TIMESTAMP
    test_data[:, 6] = 0  # BASELINE_START
    test_data[:, 7] = 50  # BASELINE_END

    # 填充波形数据（基线约为 100）
    test_data[:, 7:] = np.random.randn(n_events, wave_length) + 100

    waveforms = [test_data]

    # 创建 WaveformStruct（不提供 upstream_baselines）
    struct = WaveformStruct(waveforms)
    st_waveforms = struct.structure_waveforms()

    st_ch = st_waveforms[0]

    print(f"\n事件数: {len(st_ch)}")
    print(f"\nbaseline (WaveformStruct 计算):")
    print(f"  前 5 个值: {st_ch['baseline'][:5]}")
    print(f"  平均值: {np.mean(st_ch['baseline']):.2f}")

    print(f"\nbaseline_upstream (上游插件):")
    print(f"  前 5 个值: {st_ch['baseline_upstream'][:5]}")
    print(f"  是否全为 NaN: {np.all(np.isnan(st_ch['baseline_upstream']))}")

    print("\n✓ 默认行为：baseline_upstream 为 NaN\n")


def example_2_with_upstream():
    """示例 2: 使用上游 baseline"""
    print("=" * 60)
    print("示例 2: 使用上游 baseline")
    print("=" * 60)

    # 创建测试数据
    n_events = 5
    wave_length = 800
    test_data = np.zeros((n_events, 807))

    test_data[:, 0] = 0
    test_data[:, 1] = 0
    test_data[:, 2] = wave_length
    test_data[:, 3] = np.arange(n_events) * 1000
    test_data[:, 6] = 0
    test_data[:, 7] = 50
    test_data[:, 7:] = np.random.randn(n_events, wave_length) + 100

    waveforms = [test_data]

    # 模拟上游插件计算的 baseline（使用中位数而非平均值）
    upstream_baselines = [np.median(test_data[:, 7:57], axis=1)]

    # 创建 WaveformStruct（提供 upstream_baselines）
    struct = WaveformStruct(waveforms, upstream_baselines=upstream_baselines)
    st_waveforms = struct.structure_waveforms()

    st_ch = st_waveforms[0]

    print(f"\n事件数: {len(st_ch)}")
    print(f"\nbaseline (平均值算法):")
    print(f"  前 5 个值: {st_ch['baseline'][:5]}")
    print(f"  平均值: {np.mean(st_ch['baseline']):.2f}")

    print(f"\nbaseline_upstream (中位数算法):")
    print(f"  前 5 个值: {st_ch['baseline_upstream'][:5]}")
    print(f"  平均值: {np.mean(st_ch['baseline_upstream']):.2f}")

    # 对比两种算法
    diff = st_ch['baseline'] - st_ch['baseline_upstream']
    print(f"\n差异统计:")
    print(f"  平均差异: {np.mean(diff):.3f}")
    print(f"  最大差异: {np.max(np.abs(diff)):.3f}")

    print("\n✓ 成功保存两个 baseline 字段\n")


def example_3_multiple_channels():
    """示例 3: 多通道情况"""
    print("=" * 60)
    print("示例 3: 多通道情况")
    print("=" * 60)

    n_events = 5
    wave_length = 800
    n_channels = 3

    waveforms = []
    upstream_baselines = []

    for ch in range(n_channels):
        test_data = np.zeros((n_events, 807))
        test_data[:, 0] = 0
        test_data[:, 1] = ch
        test_data[:, 2] = wave_length
        test_data[:, 3] = np.arange(n_events) * 1000
        test_data[:, 6] = 0
        test_data[:, 7] = 50
        # 每个通道使用不同的基线值
        test_data[:, 7:] = np.random.randn(n_events, wave_length) + (100 + ch * 10)

        waveforms.append(test_data)

        # 每个通道使用不同的上游 baseline
        upstream_baselines.append(np.ones(n_events) * (95 + ch * 10))

    struct = WaveformStruct(waveforms, upstream_baselines=upstream_baselines)
    st_waveforms = struct.structure_waveforms()

    print(f"\n通道数: {len(st_waveforms)}")

    for ch in range(n_channels):
        st_ch = st_waveforms[ch]
        print(f"\n通道 {ch}:")
        print(f"  baseline 平均值: {np.mean(st_ch['baseline']):.2f}")
        print(f"  baseline_upstream 平均值: {np.mean(st_ch['baseline_upstream']):.2f}")

    print("\n✓ 每个通道使用对应的上游 baseline\n")


if __name__ == "__main__":
    print("\n双 Baseline 功能使用示例\n")

    example_1_without_upstream()
    example_2_with_upstream()
    example_3_multiple_channels()

    print("=" * 60)
    print("所有示例运行完成！")
    print("=" * 60)
