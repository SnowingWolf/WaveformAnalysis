"""绘制 S1-S2 配对波形示例

展示如何使用 S1S2PairAccessor 获取并可视化配对的波形。
"""

import matplotlib.pyplot as plt
import numpy as np

from waveform_analysis.core import Context
from waveform_analysis.utils import S1S2PairAccessor


def plot_pair_waveforms(accessor, pair_id, ax=None, show_info=True):
    """绘制单个配对的 S1 和 S2 波形

    参数
    ----
    accessor : S1S2PairAccessor
        配对访问器
    pair_id : int
        配对 ID
    ax : matplotlib.axes.Axes, optional
        绘图轴，如果为 None 则创建新图
    show_info : bool, default=True
        是否显示配对信息

    返回
    ----
    ax : matplotlib.axes.Axes
        绘图轴
    """
    # 获取配对信息
    pair = accessor.pair(pair_id)
    if pair is None:
        raise ValueError(f"Pair {pair_id} not found")

    # 获取波形
    s1_wf, s2_wf = accessor.pair_waveforms(pair)

    # 创建图形
    if ax is None:
        fig, ax = plt.subplots(figsize=(12, 5))

    # 绘制 S1
    s1_time = s1_wf["time_ns"]
    s1_data = s1_wf["waveform"]
    ax.plot(
        s1_time, s1_data, label=f"S1 (peak_id={pair['s1_peak_id']})", color="blue", linewidth=1.5
    )

    # 绘制 S2
    s2_time = s2_wf["time_ns"]
    s2_data = s2_wf["waveform"]
    ax.plot(
        s2_time, s2_data, label=f"S2 (peak_id={pair['s2_peak_id']})", color="red", linewidth=1.5
    )

    # 标记峰值位置
    ax.axvline(pair["s1_time"] / 1000, color="blue", linestyle="--", alpha=0.5, label="S1 time")
    ax.axvline(pair["s2_time"] / 1000, color="red", linestyle="--", alpha=0.5, label="S2 time")

    # 设置标签
    ax.set_xlabel("Time (ns)")
    ax.set_ylabel("Amplitude")
    ax.set_title(f"S1-S2 Pair {pair_id}")
    ax.legend()
    ax.grid(True, alpha=0.3)

    # 显示配对信息
    if show_info:
        info_text = (
            f"Drift time: {pair['drift_time_ns']:.1f} ns\n"
            f"S1 area: {pair['s1_area']:.1f}\n"
            f"S2 area: {pair['s2_area']:.1f}\n"
            f"log10(S2/S1): {pair['log10_s2_s1']:.2f}"
        )
        ax.text(
            0.02,
            0.98,
            info_text,
            transform=ax.transAxes,
            verticalalignment="top",
            fontsize=9,
            bbox={"boxstyle": "round", "facecolor": "wheat", "alpha": 0.5},
        )

    return ax


def plot_multiple_pairs(accessor, pair_ids, ncols=2):
    """绘制多个配对的波形

    参数
    ----
    accessor : S1S2PairAccessor
        配对访问器
    pair_ids : list of int
        配对 ID 列表
    ncols : int, default=2
        列数

    返回
    ----
    fig : matplotlib.figure.Figure
        图形对象
    """
    n_pairs = len(pair_ids)
    nrows = (n_pairs + ncols - 1) // ncols

    fig, axes = plt.subplots(nrows, ncols, figsize=(12 * ncols, 5 * nrows))
    axes = np.atleast_1d(axes).ravel()

    for i, pair_id in enumerate(pair_ids):
        try:
            plot_pair_waveforms(accessor, pair_id, ax=axes[i], show_info=True)
        except Exception as e:
            axes[i].text(
                0.5,
                0.5,
                f"Error loading pair {pair_id}:\n{e}",
                ha="center",
                va="center",
                transform=axes[i].transAxes,
            )
            axes[i].set_title(f"Pair {pair_id} (Error)")

    # 隐藏多余的子图
    for i in range(n_pairs, len(axes)):
        axes[i].set_visible(False)

    plt.tight_layout()
    return fig


def plot_pair_comparison(accessor, pair_ids, normalize=True):
    """对比绘制多个配对的波形（叠加在一起）

    参数
    ----
    accessor : S1S2PairAccessor
        配对访问器
    pair_ids : list of int
        配对 ID 列表
    normalize : bool, default=True
        是否归一化波形

    返回
    ----
    fig : matplotlib.figure.Figure
        图形对象
    """
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 5))

    colors = plt.cm.viridis(np.linspace(0, 1, len(pair_ids)))

    for i, pair_id in enumerate(pair_ids):
        pair = accessor.pair(pair_id)
        if pair is None:
            continue

        s1_wf, s2_wf = accessor.pair_waveforms(pair)

        # S1 波形
        s1_data = s1_wf["waveform"]
        if normalize:
            s1_data = s1_data / np.max(np.abs(s1_data))
        ax1.plot(s1_wf["time_ns"], s1_data, label=f"Pair {pair_id}", color=colors[i], alpha=0.7)

        # S2 波形
        s2_data = s2_wf["waveform"]
        if normalize:
            s2_data = s2_data / np.max(np.abs(s2_data))
        ax2.plot(s2_wf["time_ns"], s2_data, label=f"Pair {pair_id}", color=colors[i], alpha=0.7)

    ax1.set_xlabel("Time (ns)")
    ax1.set_ylabel("Normalized Amplitude" if normalize else "Amplitude")
    ax1.set_title("S1 Waveforms Comparison")
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    ax2.set_xlabel("Time (ns)")
    ax2.set_ylabel("Normalized Amplitude" if normalize else "Amplitude")
    ax2.set_title("S2 Waveforms Comparison")
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    return fig


# ============================================================================
# 使用示例
# ============================================================================

if __name__ == "__main__":
    # 初始化 context
    ctx = Context()
    ctx.register_all()
    run_id = "00195"

    # 创建 accessor
    accessor = S1S2PairAccessor(ctx, run_id=run_id)

    # 示例 1: 绘制单个配对
    pair_id = accessor.pairs[0]["pair_id"]  # 取第一个配对
    fig1 = plt.figure(figsize=(12, 5))
    plot_pair_waveforms(accessor, pair_id)
    plt.savefig("pair_waveform_single.png", dpi=150)
    plt.show()

    # 示例 2: 绘制多个配对
    pair_ids = [p["pair_id"] for p in accessor.pairs[:4]]  # 前 4 个配对
    fig2 = plot_multiple_pairs(accessor, pair_ids, ncols=2)
    plt.savefig("pair_waveforms_multiple.png", dpi=150)
    plt.show()

    # 示例 3: 对比绘制
    pair_ids = [p["pair_id"] for p in accessor.pairs[:5]]  # 前 5 个配对
    fig3 = plot_pair_comparison(accessor, pair_ids, normalize=True)
    plt.savefig("pair_waveforms_comparison.png", dpi=150)
    plt.show()
