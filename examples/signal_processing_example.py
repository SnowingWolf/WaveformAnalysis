#!/usr/bin/env python
"""
信号处理插件使用示例

展示如何使用 FilteredWaveformsPlugin 和 SignalPeaksPlugin
进行波形滤波和峰值检测。

功能说明：
1. 注册信号处理插件（滤波和寻峰）
2. 配置滤波参数（Butterworth 或 Savitzky-Golay）
3. 配置峰值检测参数
4. 执行分析并获取结果
5. 可视化滤波和峰值检测结果
"""

import matplotlib.pyplot as plt

from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import (
    FilteredWaveformsPlugin,
    RawFilesPlugin,
    SignalPeaksPlugin,
    StWaveformsPlugin,
    WaveformsPlugin,
)


def example_basic_usage():
    """
    基本使用示例 - 使用 Context API 进行信号处理
    """
    print("=" * 60)
    print("示例 1: 基本信号处理流程")
    print("=" * 60)

    # 创建 Context 实例
    ctx = Context(storage_dir="./strax_data")

    # 注册标准插件
    ctx.register_plugin_(RawFilesPlugin())
    ctx.register_plugin_(WaveformsPlugin())
    ctx.register_plugin_(StWaveformsPlugin())

    # 注册信号处理插件
    ctx.register_plugin_(FilteredWaveformsPlugin())
    ctx.register_plugin_(SignalPeaksPlugin())

    # 设置全局配置
    ctx.set_config(
        {
            "data_root": "DAQ",
            "n_channels": 2,
            "start_channel_slice": 6,
            "show_progress": True,
        }
    )

    # 配置滤波插件（使用 Savitzky-Golay 滤波器）
    ctx.set_config(
        {
            "filter_type": "SG",  # 'SG' 或 'BW'
            "sg_window_size": 11,
            "sg_poly_order": 2,
        },
        plugin_name="filtered_waveforms",
    )

    # 配置峰值检测插件
    ctx.set_config(
        {
            "use_derivative": True,  # 使用导数进行峰值检测
            "height": 30.0,  # 最小峰高
            "distance": 2,  # 最小峰间距
            "prominence": 0.7,  # 最小显著性
            "width": 4,  # 最小宽度
            "height_method": "minmax",  # 峰高计算方法
        },
        plugin_name="signal_peaks",
    )

    # 指定运行名称
    run_id = "50V_OV_circulation_20thr"

    print(f"\n处理运行: {run_id}")

    # 获取滤波后的波形
    print("\n步骤 1: 获取滤波后的波形...")
    filtered_waveforms = ctx.get_data(run_id, "filtered_waveforms")
    print(f"通道数: {len(filtered_waveforms)}")
    for ch_idx, filtered_ch in enumerate(filtered_waveforms):
        if len(filtered_ch) > 0:
            print(f"通道 {ch_idx}: {len(filtered_ch)} 个事件, 形状: {filtered_ch.shape}")

    # 获取峰值检测结果
    print("\n步骤 2: 获取峰值检测结果...")
    signal_peaks = ctx.get_data(run_id, "signal_peaks")
    print(f"通道数: {len(signal_peaks)}")
    for ch_idx, peaks_ch in enumerate(signal_peaks):
        print(f"通道 {ch_idx}: {len(peaks_ch)} 个峰值")
        if len(peaks_ch) > 0:
            print(f"  峰值字段: {peaks_ch.dtype.names}")
            print(f"  示例峰值: {peaks_ch[0]}")

    print("\n✓ 基本使用示例完成")

    return ctx, run_id, filtered_waveforms, signal_peaks


def example_butterworth_filter():
    """
    示例 2: 使用 Butterworth 带通滤波器
    """
    print("\n" + "=" * 60)
    print("示例 2: 使用 Butterworth 带通滤波器")
    print("=" * 60)

    ctx = Context(storage_dir="./strax_data")

    # 注册插件
    ctx.register_plugin_(RawFilesPlugin())
    ctx.register_plugin_(WaveformsPlugin())
    ctx.register_plugin_(StWaveformsPlugin())
    ctx.register_plugin_(FilteredWaveformsPlugin())

    # 全局配置
    ctx.set_config(
        {
            "data_root": "DAQ",
            "n_channels": 2,
            "start_channel_slice": 6,
        }
    )

    # 配置 Butterworth 滤波器
    ctx.set_config(
        {
            "filter_type": "BW",
            "lowcut": 0.05,  # 低频截止
            "highcut": 0.8,  # 高频截止
            "fs": 1.0,  # 采样率
            "filter_order": 4,  # 滤波器阶数
        },
        plugin_name="filtered_waveforms",
    )

    run_id = "50V_OV_circulation_20thr"

    print(f"\n使用 Butterworth 带通滤波器处理运行: {run_id}")
    filtered_waveforms = ctx.get_data(run_id, "filtered_waveforms")

    print(f"通道数: {len(filtered_waveforms)}")
    for ch_idx, filtered_ch in enumerate(filtered_waveforms):
        if len(filtered_ch) > 0:
            print(f"通道 {ch_idx}: {len(filtered_ch)} 个事件")

    print("\n✓ Butterworth 滤波器示例完成")

    return ctx, run_id, filtered_waveforms


def example_visualize_results(ctx, run_id, event_idx=0, channel_idx=0):
    """
    示例 3: 可视化滤波和峰值检测结果
    """
    print("\n" + "=" * 60)
    print("示例 3: 可视化滤波和峰值检测结果")
    print("=" * 60)

    # 获取原始波形、滤波波形和峰值
    st_waveforms = ctx.get_data(run_id, "st_waveforms")
    filtered_waveforms = ctx.get_data(run_id, "filtered_waveforms")
    signal_peaks = ctx.get_data(run_id, "signal_peaks")

    # 检查数据是否存在
    if len(st_waveforms) <= channel_idx or len(st_waveforms[channel_idx]) <= event_idx:
        print(f"警告: 通道 {channel_idx} 或事件 {event_idx} 不存在")
        return

    # 提取数据
    original_waveform = st_waveforms[channel_idx][event_idx]["wave"]
    filtered_waveform = filtered_waveforms[channel_idx][event_idx]

    # 提取此事件的峰值（如果有）
    event_peaks = signal_peaks[channel_idx][signal_peaks[channel_idx]["event_index"] == event_idx]

    print(f"\n可视化通道 {channel_idx}, 事件 {event_idx}")
    print(f"原始波形长度: {len(original_waveform)}")
    print(f"滤波波形长度: {len(filtered_waveform)}")
    print(f"检测到的峰值数: {len(event_peaks)}")

    # 创建图形
    fig, axes = plt.subplots(3, 1, figsize=(12, 10))

    # 子图 1: 原始波形
    axes[0].plot(original_waveform, label="原始波形", color="blue", alpha=0.7)
    axes[0].set_title(f"原始波形 - 通道 {channel_idx}, 事件 {event_idx}")
    axes[0].set_xlabel("采样点")
    axes[0].set_ylabel("幅度")
    axes[0].legend()
    axes[0].grid(True, alpha=0.3)

    # 子图 2: 滤波波形
    axes[1].plot(filtered_waveform, label="滤波波形", color="green", alpha=0.7)
    axes[1].set_title("滤波后的波形")
    axes[1].set_xlabel("采样点")
    axes[1].set_ylabel("幅度")
    axes[1].legend()
    axes[1].grid(True, alpha=0.3)

    # 子图 3: 滤波波形 + 峰值标记
    axes[2].plot(filtered_waveform, label="滤波波形", color="green", alpha=0.7)

    # 标记峰值
    if len(event_peaks) > 0:
        peak_positions = event_peaks["position"]
        peak_heights = filtered_waveform[peak_positions]

        axes[2].scatter(
            peak_positions,
            peak_heights,
            color="red",
            s=100,
            marker="x",
            label=f"检测到的峰值 ({len(event_peaks)})",
            zorder=5,
        )

        # 标记峰值边缘
        for peak in event_peaks:
            edge_start = int(peak["edge_start"])
            edge_end = int(peak["edge_end"])
            axes[2].axvline(edge_start, color="orange", linestyle="--", alpha=0.5, linewidth=1)
            axes[2].axvline(edge_end, color="orange", linestyle="--", alpha=0.5, linewidth=1)

    axes[2].set_title("滤波波形 + 峰值检测")
    axes[2].set_xlabel("采样点")
    axes[2].set_ylabel("幅度")
    axes[2].legend()
    axes[2].grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig("signal_processing_example.png", dpi=150)
    print("\n✓ 可视化结果已保存到 signal_processing_example.png")
    plt.show()


def example_compare_filters():
    """
    示例 4: 比较不同滤波方法的效果
    """
    print("\n" + "=" * 60)
    print("示例 4: 比较 Butterworth 和 Savitzky-Golay 滤波器")
    print("=" * 60)

    run_id = "50V_OV_circulation_20thr"
    event_idx = 0
    channel_idx = 0

    # 获取原始波形
    ctx_original = Context(storage_dir="./strax_data")
    ctx_original.register_plugin_(RawFilesPlugin())
    ctx_original.register_plugin_(WaveformsPlugin())
    ctx_original.register_plugin_(StWaveformsPlugin())
    ctx_original.set_config({"data_root": "DAQ", "n_channels": 2, "start_channel_slice": 6})
    st_waveforms = ctx_original.get_data(run_id, "st_waveforms")
    original_waveform = st_waveforms[channel_idx][event_idx]["wave"]

    # 使用 SG 滤波器
    ctx_sg = Context(storage_dir="./strax_data_sg")
    ctx_sg.register_plugin_(RawFilesPlugin())
    ctx_sg.register_plugin_(WaveformsPlugin())
    ctx_sg.register_plugin_(StWaveformsPlugin())
    ctx_sg.register_plugin_(FilteredWaveformsPlugin())
    ctx_sg.set_config({"data_root": "DAQ", "n_channels": 2, "start_channel_slice": 6})
    ctx_sg.set_config(
        {"filter_type": "SG", "sg_window_size": 11, "sg_poly_order": 2},
        plugin_name="filtered_waveforms",
    )
    filtered_sg = ctx_sg.get_data(run_id, "filtered_waveforms")
    sg_waveform = filtered_sg[channel_idx][event_idx]

    # 使用 BW 滤波器
    ctx_bw = Context(storage_dir="./strax_data_bw")
    ctx_bw.register_plugin_(RawFilesPlugin())
    ctx_bw.register_plugin_(WaveformsPlugin())
    ctx_bw.register_plugin_(StWaveformsPlugin())
    ctx_bw.register_plugin_(FilteredWaveformsPlugin())
    ctx_bw.set_config({"data_root": "DAQ", "n_channels": 2, "start_channel_slice": 6})
    ctx_bw.set_config(
        {
            "filter_type": "BW",
            "lowcut": 0.05,
            "highcut": 0.8,
            "fs": 1.0,
            "filter_order": 4,
        },
        plugin_name="filtered_waveforms",
    )
    filtered_bw = ctx_bw.get_data(run_id, "filtered_waveforms")
    bw_waveform = filtered_bw[channel_idx][event_idx]

    # 可视化比较
    fig, axes = plt.subplots(3, 1, figsize=(12, 10))

    # 原始波形
    axes[0].plot(original_waveform, label="原始波形", color="blue", alpha=0.7)
    axes[0].set_title("原始波形")
    axes[0].set_ylabel("幅度")
    axes[0].legend()
    axes[0].grid(True, alpha=0.3)

    # SG 滤波
    axes[1].plot(sg_waveform, label="Savitzky-Golay 滤波", color="green", alpha=0.7)
    axes[1].set_title("Savitzky-Golay 滤波器")
    axes[1].set_ylabel("幅度")
    axes[1].legend()
    axes[1].grid(True, alpha=0.3)

    # BW 滤波
    axes[2].plot(bw_waveform, label="Butterworth 滤波", color="red", alpha=0.7)
    axes[2].set_title("Butterworth 带通滤波器")
    axes[2].set_xlabel("采样点")
    axes[2].set_ylabel("幅度")
    axes[2].legend()
    axes[2].grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig("filter_comparison.png", dpi=150)
    print("\n✓ 滤波器比较结果已保存到 filter_comparison.png")
    plt.show()


def main():
    """
    主函数 - 运行所有示例
    """
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 58 + "║")
    print("║" + "   信号处理插件使用示例   ".center(58) + "║")
    print("║" + " " * 58 + "║")
    print("╚" + "=" * 58 + "╝")

    try:
        # 示例 1: 基本使用
        ctx, run_id, filtered_waveforms, signal_peaks = example_basic_usage()

        # 示例 2: Butterworth 滤波器
        example_butterworth_filter()

        # 示例 3: 可视化结果（需要 matplotlib）
        try:
            example_visualize_results(ctx, run_id, event_idx=0, channel_idx=0)
        except Exception as e:
            print(f"\n注意: 可视化示例跳过 (可能缺少数据或 matplotlib): {e}")

        # 示例 4: 比较滤波器（需要 matplotlib）
        try:
            example_compare_filters()
        except Exception as e:
            print(f"\n注意: 滤波器比较示例跳过: {e}")

        print("\n" + "=" * 60)
        print("所有示例运行完成!")
        print("=" * 60)

    except FileNotFoundError as e:
        print(f"\n错误: 找不到数据文件 - {e}")
        print("请确保 DAQ 目录和运行数据存在")
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
