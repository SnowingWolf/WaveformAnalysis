"""
WaveformWidthPlugin 使用示例

演示如何使用波形宽度插件计算上升/下降时间。
"""

import numpy as np

from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import (
    FilteredWaveformsPlugin,
    SignalPeaksPlugin,
    StWaveformsPlugin,
    WaveformsPlugin,
    WaveformWidthPlugin,
)


def example_basic_usage():
    """基本使用示例"""
    print("=" * 60)
    print("示例 1: 基本使用 - 计算波形宽度")
    print("=" * 60)

    # 创建 Context 并注册插件
    ctx = Context(config={"data_root": "DAQ", "n_channels": 2})

    # 注册必要的插件
    ctx.register(WaveformsPlugin())
    ctx.register(StWaveformsPlugin())
    ctx.register(FilteredWaveformsPlugin())  # 可选，用于滤波
    ctx.register(SignalPeaksPlugin())  # 必需，提供峰值检测
    ctx.register(WaveformWidthPlugin())  # 波形宽度插件

    # 配置插件参数
    ctx.set_config(
        {
            "sampling_rate": 0.5,  # 0.5 GHz 采样率
            "rise_low": 0.1,  # 10% 阈值
            "rise_high": 0.9,  # 90% 阈值
            "interpolation": True,  # 使用插值提高精度
        },
        plugin_name="waveform_width",
    )

    # 配置峰值检测参数
    ctx.set_config(
        {
            "height": 30.0,
            "prominence": 0.7,
            "use_derivative": True,
        },
        plugin_name="signal_peaks",
    )

    print("\n配置完成，插件链:")
    print("  WaveformsPlugin → StWaveformsPlugin → FilteredWaveformsPlugin")
    print("  → SignalPeaksPlugin → WaveformWidthPlugin")

    # 获取数据（假设有数据文件）
    try:
        run_id = "50V_OV_circulation_20thr"
        widths = ctx.get_data(run_id, "waveform_width")

        print("\n成功计算波形宽度！")
        print(f"通道数: {len(widths)}")

        for ch_idx, ch_widths in enumerate(widths):
            if len(ch_widths) > 0:
                print(f"\n通道 {ch_idx}:")
                print(f"  峰值数量: {len(ch_widths)}")
                print(f"  平均上升时间: {np.mean(ch_widths['rise_time']):.2f} ns")
                print(f"  平均下降时间: {np.mean(ch_widths['fall_time']):.2f} ns")
                print(f"  平均总宽度: {np.mean(ch_widths['total_width']):.2f} ns")
                print(
                    f"  上升时间范围: [{np.min(ch_widths['rise_time']):.2f}, {np.max(ch_widths['rise_time']):.2f}] ns"
                )
                print(
                    f"  下降时间范围: [{np.min(ch_widths['fall_time']):.2f}, {np.max(ch_widths['fall_time']):.2f}] ns"
                )

    except FileNotFoundError:
        print("\n注意: 未找到数据文件，跳过实际数据处理")
        print("请确保 DAQ 目录中有对应的运行数据")


def example_with_filtered_waveforms():
    """使用滤波波形的示例"""
    print("\n" + "=" * 60)
    print("示例 2: 使用滤波波形计算宽度")
    print("=" * 60)

    ctx = Context(config={"data_root": "DAQ", "n_channels": 2})

    # 注册插件
    ctx.register(WaveformsPlugin())
    ctx.register(StWaveformsPlugin())
    ctx.register(FilteredWaveformsPlugin())
    ctx.register(SignalPeaksPlugin())
    ctx.register(WaveformWidthPlugin())

    # 配置滤波参数
    ctx.set_config(
        {
            "filter_type": "butterworth",
            "lowcut": 0.01,
            "highcut": 0.3,
            "order": 4,
        },
        plugin_name="filtered_waveforms",
    )

    # 配置波形宽度插件使用滤波波形
    ctx.set_config(
        {
            "use_filtered": True,  # 使用滤波后的波形
            "sampling_rate": 0.5,
            "interpolation": True,
        },
        plugin_name="waveform_width",
    )

    print("\n配置: 使用 Butterworth 滤波器 + 滤波波形计算宽度")
    print("  滤波参数: lowcut=0.01, highcut=0.3, order=4")
    print("  use_filtered=True")

    try:
        run_id = "50V_OV_circulation_20thr"
        widths = ctx.get_data(run_id, "waveform_width")
        print("\n成功使用滤波波形计算宽度！")
        print(f"通道 0 峰值数: {len(widths[0])}")

    except FileNotFoundError:
        print("\n注意: 未找到数据文件")


def example_custom_thresholds():
    """自定义阈值的示例"""
    print("\n" + "=" * 60)
    print("示例 3: 自定义上升/下降阈值")
    print("=" * 60)

    ctx = Context(config={"data_root": "DAQ", "n_channels": 2})

    ctx.register(WaveformsPlugin())
    ctx.register(StWaveformsPlugin())
    ctx.register(SignalPeaksPlugin())
    ctx.register(WaveformWidthPlugin())

    # 使用 20%-80% 阈值（而不是默认的 10%-90%）
    ctx.set_config(
        {
            "rise_low": 0.2,  # 20% 阈值
            "rise_high": 0.8,  # 80% 阈值
            "fall_high": 0.8,
            "fall_low": 0.2,
            "sampling_rate": 0.5,
        },
        plugin_name="waveform_width",
    )

    print("\n配置: 使用 20%-80% 阈值计算上升/下降时间")
    print("  rise_low=0.2, rise_high=0.8")
    print("  fall_high=0.8, fall_low=0.2")

    try:
        run_id = "50V_OV_circulation_20thr"
        widths = ctx.get_data(run_id, "waveform_width")
        print(f"\n成功计算！通道 0 峰值数: {len(widths[0])}")

    except FileNotFoundError:
        print("\n注意: 未找到数据文件")


def example_data_analysis():
    """数据分析示例"""
    print("\n" + "=" * 60)
    print("示例 4: 波形宽度数据分析")
    print("=" * 60)

    ctx = Context(config={"data_root": "DAQ", "n_channels": 2})

    ctx.register(WaveformsPlugin())
    ctx.register(StWaveformsPlugin())
    ctx.register(SignalPeaksPlugin())
    ctx.register(WaveformWidthPlugin())

    ctx.set_config({"sampling_rate": 0.5}, plugin_name="waveform_width")

    try:
        run_id = "50V_OV_circulation_20thr"
        widths = ctx.get_data(run_id, "waveform_width")

        print("\n详细数据分析:")

        for ch_idx, ch_widths in enumerate(widths):
            if len(ch_widths) == 0:
                continue

            print(f"\n通道 {ch_idx} 统计:")
            print(f"  总峰值数: {len(ch_widths)}")

            # 上升时间统计
            rise_times = ch_widths["rise_time"]
            print("\n  上升时间 (10%-90%):")
            print(f"    平均值: {np.mean(rise_times):.2f} ns")
            print(f"    中位数: {np.median(rise_times):.2f} ns")
            print(f"    标准差: {np.std(rise_times):.2f} ns")
            print(f"    范围: [{np.min(rise_times):.2f}, {np.max(rise_times):.2f}] ns")

            # 下降时间统计
            fall_times = ch_widths["fall_time"]
            print("\n  下降时间 (90%-10%):")
            print(f"    平均值: {np.mean(fall_times):.2f} ns")
            print(f"    中位数: {np.median(fall_times):.2f} ns")
            print(f"    标准差: {np.std(fall_times):.2f} ns")
            print(f"    范围: [{np.min(fall_times):.2f}, {np.max(fall_times):.2f}] ns")

            # 总宽度统计
            total_widths = ch_widths["total_width"]
            print("\n  总宽度:")
            print(f"    平均值: {np.mean(total_widths):.2f} ns")
            print(f"    中位数: {np.median(total_widths):.2f} ns")
            print(f"    标准差: {np.std(total_widths):.2f} ns")

            # 峰值高度统计
            peak_heights = ch_widths["peak_height"]
            print("\n  峰值高度:")
            print(f"    平均值: {np.mean(peak_heights):.2f}")
            print(f"    范围: [{np.min(peak_heights):.2f}, {np.max(peak_heights):.2f}]")

    except FileNotFoundError:
        print("\n注意: 未找到数据文件")


if __name__ == "__main__":
    print("\nWaveformWidthPlugin 使用示例\n")

    # 运行所有示例
    example_basic_usage()
    example_with_filtered_waveforms()
    example_custom_thresholds()
    example_data_analysis()

    print("\n" + "=" * 60)
    print("所有示例完成！")
    print("=" * 60)
