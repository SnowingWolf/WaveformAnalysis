#!/usr/bin/env python3
"""
PeakChannelAccessor 使用示例

演示如何使用 PeakChannelAccessor 访问 per-channel 数据和绘制波形
"""

import numpy as np

from waveform_analysis.utils.peak_channel_accessor import PeakChannelAccessor


def demo_feature_access(accessor, peak_id=0):
    """演示特征访问（不加载波形）"""
    print("\n" + "=" * 60)
    print("1. 特征访问（快速，不加载 wave_pool）")
    print("=" * 60)

    channels = accessor.get_peak_channels(peak_id)

    print(f"\nPeak {peak_id} 有 {len(channels)} 个通道:")
    for ch in channels:
        print(f"  Board {ch['board']}, Channel {ch['channel']}:")
        print(f"    Area: {ch['area']:.1f}")
        print(f"    Height: {ch['height']:.1f}")
        print(f"    Width: {ch['width']:.1f} ns")
        print(f"    Rise time: {ch['rise_time']:.1f} ns")
        print(f"    Single record: {ch['is_single_record']}")


def demo_waveform_access(accessor, peak_id=0):
    """演示波形访问"""
    print("\n" + "=" * 60)
    print("2. 波形访问（延迟加载 wave_pool）")
    print("=" * 60)

    # 获取特征 + 波形
    channels = accessor.get_peak_channel_data(peak_id, include_waveform=True)

    print(f"\nPeak {peak_id} 的通道波形:")
    for ch in channels:
        print(f"  Board {ch['board']}, Channel {ch['channel']}:")
        print(f"    Waveform shape: {ch['waveform'].shape}")
        print(f"    Time range: {ch['time_ns'][0]:.1f} - {ch['time_ns'][-1]:.1f} ns")
        print(f"    Segments: {len(ch['segments'])}")
        print(f"    dt: {ch['dt']} ns")


def demo_sum_waveform(accessor, peak_id=0):
    """演示 sum waveform 访问"""
    print("\n" + "=" * 60)
    print("3. Sum Waveform 访问")
    print("=" * 60)

    sum_data = accessor.get_sum_waveform(peak_id)

    if sum_data:
        print(f"\nPeak {peak_id} Sum Waveform:")
        print(f"  Shape: {sum_data['waveform'].shape}")
        print(f"  Time start: {sum_data['time_start']/1000:.1f} ns")
        print(f"  Time end: {sum_data['time_end']/1000:.1f} ns")
        print(f"  dt: {sum_data['dt']} ns")
        print(f"  Max value: {np.max(sum_data['waveform']):.1f}")


def demo_visualization(accessor, peak_id=0):
    """演示可视化功能"""
    print("\n" + "=" * 60)
    print("4. 可视化功能")
    print("=" * 60)

    # 绘制单个 peak
    print(f"\n绘制 peak {peak_id}...")
    fig, axes = accessor.plot(peak_id, show_sum=True)

    if fig:
        print(f"  ✓ 成功创建图形，共 {len(axes)} 个子图")

        # 保存
        from pathlib import Path

        output_dir = Path("examples/output")
        output_dir.mkdir(parents=True, exist_ok=True)
        save_path = output_dir / f"peak_channel_demo_{peak_id}.png"
        fig.savefig(save_path, dpi=150, bbox_inches="tight")
        print(f"  ✓ 保存至: {save_path}")

        import matplotlib.pyplot as plt

        plt.close(fig)


def demo_channel_comparison(accessor, peak_id=0):
    """演示通道对比绘图"""
    print("\n" + "=" * 60)
    print("5. 通道对比绘图")
    print("=" * 60)

    # 筛选 area > 平均值的通道
    channels = accessor.get_peak_channels(peak_id)
    avg_area = np.mean([ch["area"] for ch in channels])

    print(f"\n筛选条件: area > {avg_area:.1f}")

    fig, ax = accessor.plot_channel_comparison(
        peak_id, channel_selector=lambda ch: ch["area"] > avg_area
    )

    if fig:
        print("  ✓ 成功创建对比图")

        from pathlib import Path

        output_dir = Path("examples/output")
        save_path = output_dir / f"channel_comparison_{peak_id}.png"
        fig.savefig(save_path, dpi=150, bbox_inches="tight")
        print(f"  ✓ 保存至: {save_path}")

        import matplotlib.pyplot as plt

        plt.close(fig)


def demo_sum_vs_channels(accessor, peak_id=0):
    """演示 sum vs channels 对比"""
    print("\n" + "=" * 60)
    print("6. Sum vs Channels 对比")
    print("=" * 60)

    fig, axes = accessor.plot_sum_vs_channels(peak_id)

    if fig:
        print("  ✓ 成功创建对比图")

        from pathlib import Path

        output_dir = Path("examples/output")
        save_path = output_dir / f"sum_vs_channels_{peak_id}.png"
        fig.savefig(save_path, dpi=150, bbox_inches="tight")
        print(f"  ✓ 保存至: {save_path}")

        import matplotlib.pyplot as plt

        plt.close(fig)


def demo_batch_plot(accessor, peak_ids):
    """演示批量绘图"""
    print("\n" + "=" * 60)
    print("7. 批量绘图")
    print("=" * 60)

    accessor.batch_plot(peak_ids, output_dir="examples/output/batch_peaks")
    print("  ✓ 完成批量绘图")


def main():
    """主函数"""
    print("=" * 60)
    print("PeakChannelAccessor 功能演示")
    print("=" * 60)

    # 注意：这里需要实际的 context 和 run_id
    # 以下是伪代码示例

    print("\n使用方法:")
    print("-" * 60)
    print(
        """
# 1. 创建访问器
from waveform_analysis.utils.peak_channel_accessor import PeakChannelAccessor

accessor = PeakChannelAccessor(context, run_id)

# 2. 只访问特征（快速，不加载 wave_pool）
channels = accessor.get_peak_channels(peak_id=42)
print(f"Peak 42 有 {len(channels)} 个通道")

# 3. 访问特征 + 波形
channels = accessor.get_peak_channel_data(peak_id=42, include_waveform=True)
for ch in channels:
    print(f"Channel {ch['channel']}: area={ch['area']:.1f}, waveform shape={ch['waveform'].shape}")

# 4. 获取 sum waveform
sum_data = accessor.get_sum_waveform(peak_id=42)

# 5. 绘制波形
fig, axes = accessor.plot(peak_id=42)

# 6. 批量绘制
accessor.batch_plot([42, 43, 44], output_dir="output")

# 7. 通道对比
fig, ax = accessor.plot_channel_comparison(
    peak_id=42,
    channel_selector=lambda ch: ch['area'] > 100
)

# 8. Sum vs Channels 对比
fig, axes = accessor.plot_sum_vs_channels(peak_id=42)

# 9. 清理缓存
accessor.clear_waveform_cache(release_wave_pool=True)
    """
    )

    print("\n关键优势:")
    print("-" * 60)
    print("✓ 分层加载：默认只加载特征，按需加载波形")
    print("✓ 索引优化：O(1) 查找，避免高频布尔筛选")
    print("✓ 统一接口：数据访问和可视化在同一个类")
    print("✓ 缓存控制：可以随时释放波形层数据")
    print("✓ 保留 segments：跨 record 波形保留原始片段信息")

    print("\n" + "=" * 60)
    print("如需运行完整演示，请提供实际的 context 和 run_id")
    print("=" * 60)


if __name__ == "__main__":
    main()
