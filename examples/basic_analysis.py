"""
基础数据分析示例

展示如何使用 waveform_analysis 包进行完整的数据处理流程。
"""

import matplotlib.pyplot as plt
import numpy as np

from waveform_analysis import WaveformDataset


def main():
    """主函数 - 完整数据处理流程示例"""

    print("=" * 60)
    print("波形数据分析示例")
    print("=" * 60)

    # 1. 创建数据集实例
    print("\n1. 创建数据集...")
    dataset = WaveformDataset(char="50V_OV_circulation_20thr", n_channels=2, start_channel_slice=6)

    # 2. 执行完整处理流程（链式调用）
    print("\n2. 执行数据处理流程...")
    try:
        (
            dataset.load_raw_data()
            .extract_waveforms()
            .structure_waveforms()
            .build_waveform_features(peaks_range=(40, 90), charge_range=(60, 400))
            .build_dataframe()
            .group_events(time_window_ns=100)
            .pair_events()
            .save_results()
        )

        print("\n✅ 数据处理完成！")
    except FileNotFoundError as e:
        print(f"\n❌ 数据文件未找到: {e}")
        print("请确保 DAQ 数据目录存在")
        return

    # 3. 获取处理结果
    print("\n3. 获取处理结果...")
    df_paired = dataset.get_paired_events()
    print(f"   - 成功配对的事件数: {len(df_paired)}")

    if len(df_paired) == 0:
        print("   ⚠️  没有配对事件，退出")
        return

    # 4. 数据摘要
    print("\n4. 数据摘要:")
    summary = dataset.summary()
    for key, value in summary.items():
        print(f"   - {key}: {value}")

    # 5. 基本可视化
    print("\n5. 生成可视化...")

    # 5.1 峰值分布
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))

    axes[0].hist(df_paired["peak_ch6"], bins=50, alpha=0.7, label="CH6")
    axes[0].hist(df_paired["peak_ch7"], bins=50, alpha=0.7, label="CH7")
    axes[0].set_xlabel("Peak [ADC]")
    axes[0].set_ylabel("Count")
    axes[0].set_title("峰值分布")
    axes[0].legend()
    axes[0].set_yscale("log")

    # 5.2 时间差分布
    axes[1].hist(df_paired["delta_t"], bins=50, alpha=0.7)
    axes[1].set_xlabel("Time Difference [ns]")
    axes[1].set_ylabel("Count")
    axes[1].set_title("通道间时间差分布")

    plt.tight_layout()
    plt.savefig("outputs/basic_analysis.png", dpi=150)
    print("   ✅ 图像已保存到 outputs/basic_analysis.png")

    # 6. 获取单个波形示例
    print("\n6. 获取波形示例...")
    result = dataset.get_waveform_at(event_idx=0, channel=0)
    if result:
        wave, baseline = result
        wave_mv = (wave - baseline) * 0.024
        print(f"   - 波形长度: {len(wave)}")
        print(f"   - 基线: {baseline:.2f} ADC")
        print(f"   - 幅度范围: {wave_mv.min():.2f} ~ {wave_mv.max():.2f} mV")

    print("\n" + "=" * 60)
    print("分析完成！")
    print("=" * 60)


def plot_example_waveforms(dataset, n_examples=4):
    """绘制示例波形"""
    df_paired = dataset.get_paired_events()

    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    axes = axes.flatten()

    for i in range(min(n_examples, len(df_paired))):
        ax = axes[i]

        result_ch6 = dataset.get_waveform_at(event_idx=i, channel=0)
        result_ch7 = dataset.get_waveform_at(event_idx=i, channel=1)

        if result_ch6 and result_ch7:
            wave6, baseline6 = result_ch6
            wave7, baseline7 = result_ch7

            wave6_mv = (wave6 - baseline6) * 0.024
            wave7_mv = (wave7 - baseline7) * 0.024

            event = df_paired.iloc[i]

            ax.plot(wave6_mv, label="CH6", alpha=0.8)
            ax.plot(wave7_mv, label="CH7", alpha=0.8)
            ax.set_title(f"Event {event['event_id']}: Δt={event['delta_t']:.2f}ns")
            ax.set_xlabel("Sample")
            ax.set_ylabel("Amplitude [mV]")
            ax.legend()
            ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig("outputs/example_waveforms.png", dpi=150)
    print("示例波形已保存到 outputs/example_waveforms.png")


if __name__ == "__main__":
    main()
