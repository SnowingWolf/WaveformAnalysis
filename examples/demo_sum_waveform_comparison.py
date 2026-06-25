#!/usr/bin/env python3
"""
演示 sum waveform 修复：对比使用 peaklet waveform vs 手动累加

这个脚本展示了为什么 sum signal 应该使用 peaklet_waveforms：
1. Peaklet waveform 是在插件中正确计算的（考虑了时间对齐、插值等）
2. 手动从原始 records 累加可能因为采样率差异、时间对齐等问题导致不一致
3. Peaklet waveform 与 peak 特征（area, height）的计算使用相同的波形，确保一致性
"""

import matplotlib.pyplot as plt
import numpy as np


def create_demo_data():
    """
    创建演示数据，模拟两个通道的信号：
    - 通道 0: 采样率 2ns，信号幅度 100
    - 通道 1: 采样率 4ns，信号幅度 50
    """
    # 通道 0: 高采样率
    t0 = np.arange(0, 200, 2)  # 0-200ns, 每 2ns 采样
    signal0 = 100 * np.exp(-((t0 - 100) ** 2) / 200)  # 高斯峰

    # 通道 1: 低采样率
    t1 = np.arange(0, 200, 4)  # 0-200ns, 每 4ns 采样
    signal1 = 50 * np.exp(-((t1 - 100) ** 2) / 200)  # 高斯峰

    # 正确的 sum waveform（使用 peaklet 插件计算）
    # 插值到最小采样率（2ns），然后求和
    t_grid = np.arange(0, 200, 2)
    signal1_interp = np.interp(t_grid, t1, signal1)
    sum_correct = signal0 + signal1_interp

    return t0, signal0, t1, signal1, t_grid, sum_correct


def create_incorrect_sum_old_method(t0, signal0, t1, signal1):
    """
    旧方法：使用 round 映射到网格（错误的方法）
    """
    dt = 2  # 最小 dt
    t_min = 0
    t_max = 200
    t_grid = np.arange(t_min, t_max, dt)
    sum_incorrect = np.zeros_like(t_grid, dtype=np.float64)

    # 通道 0
    idx0 = np.round((t0 - t_min) / dt).astype(int)
    valid0 = (idx0 >= 0) & (idx0 < len(t_grid))
    np.add.at(sum_incorrect, idx0[valid0], signal0[valid0])

    # 通道 1
    idx1 = np.round((t1 - t_min) / dt).astype(int)
    valid1 = (idx1 >= 0) & (idx1 < len(t_grid))
    np.add.at(sum_incorrect, idx1[valid1], signal1[valid1])

    return t_grid, sum_incorrect


def main():
    """主函数"""
    print("=" * 60)
    print("Sum Waveform 修复演示")
    print("=" * 60)

    # 创建数据
    t0, signal0, t1, signal1, t_grid, sum_correct = create_demo_data()
    _, sum_incorrect = create_incorrect_sum_old_method(t0, signal0, t1, signal1)

    # 创建图形
    fig, axes = plt.subplots(4, 1, figsize=(12, 10))

    # 子图 1: 通道 0（高采样率）
    ax0 = axes[0]
    ax0.plot(t0, signal0, "o-", label="Channel 0 (dt=2ns)", color="C0")
    ax0.set_ylabel("Signal")
    ax0.set_title("Channel 0: High sampling rate (2ns)")
    ax0.grid(True, alpha=0.3)
    ax0.legend()

    # 子图 2: 通道 1（低采样率）
    ax1 = axes[1]
    ax1.plot(t1, signal1, "s-", label="Channel 1 (dt=4ns)", color="C1", markersize=8)
    ax1.set_ylabel("Signal")
    ax1.set_title("Channel 1: Low sampling rate (4ns)")
    ax1.grid(True, alpha=0.3)
    ax1.legend()

    # 子图 3: 正确的 sum（使用插值）
    ax2 = axes[2]
    ax2.plot(t_grid, sum_correct, "k-", linewidth=2, label="Correct sum (interpolation)")
    ax2.plot(t0, signal0, "o-", alpha=0.3, label="Ch0", color="C0", markersize=3)
    signal1_interp = np.interp(t_grid, t1, signal1)
    ax2.plot(
        t_grid, signal1_interp, "s-", alpha=0.3, label="Ch1 (interp)", color="C1", markersize=3
    )
    ax2.set_ylabel("Signal")
    ax2.set_title("✓ Correct: Sum using peaklet_waveforms (with interpolation)")
    ax2.grid(True, alpha=0.3)
    ax2.legend()

    # 子图 4: 错误的 sum（使用 round）
    ax3 = axes[3]
    ax3.plot(t_grid, sum_incorrect, "r-", linewidth=2, label="Incorrect sum (round mapping)")
    ax3.plot(t_grid, sum_correct, "k--", alpha=0.5, linewidth=1, label="Correct sum (reference)")
    ax3.set_ylabel("Signal")
    ax3.set_xlabel("Time (ns)")
    ax3.set_title("✗ Old method: Sum using round mapping (incorrect)")
    ax3.grid(True, alpha=0.3)
    ax3.legend()

    plt.tight_layout()

    # 保存图像
    from pathlib import Path

    output_dir = Path("examples/output")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "sum_waveform_comparison.png"
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    print(f"\n✓ 图像已保存至: {output_path}")

    # 计算误差
    error = np.abs(sum_incorrect - sum_correct)
    max_error = np.max(error)
    mean_error = np.mean(error)
    print("\n误差统计:")
    print(f"  最大误差: {max_error:.2f}")
    print(f"  平均误差: {mean_error:.2f}")
    print(f"  相对误差: {max_error / np.max(sum_correct) * 100:.1f}%")

    print("\n" + "=" * 60)
    print("关键点:")
    print("=" * 60)
    print("1. 旧方法使用 round 映射，导致:")
    print("   - 某些网格点可能有多个采样点映射（重复累加）")
    print("   - 某些网格点可能没有采样点映射（缺失数据）")
    print("   - 当采样率不同时，误差更明显")
    print("\n2. 新方法使用 peaklet_waveforms:")
    print("   - 插件中已经正确计算了插值和求和")
    print("   - 与 peak 特征（area, height）计算使用相同波形")
    print("   - 确保了一致性和正确性")
    print("=" * 60)

    plt.show()


if __name__ == "__main__":
    main()
