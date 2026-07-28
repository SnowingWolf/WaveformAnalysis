"""Notebook 中快速绘制 S1-S2 配对波形的辅助函数"""

import matplotlib.pyplot as plt
import numpy as np


def quick_plot_pair(accessor, pair_id):
    """快速绘制一个配对的波形（适合 notebook）

    用法：
    >>> from waveform_analysis.utils import S1S2PairAccessor
    >>> accessor = S1S2PairAccessor(ctx, run_id)
    >>> quick_plot_pair(accessor, pair_id=0)
    """
    pair = accessor.pair(pair_id)
    s1_wf, s2_wf = accessor.pair_waveforms(pair)

    fig, ax = plt.subplots(figsize=(14, 6))

    # 绘制波形
    ax.plot(
        s1_wf["time_ns"],
        s1_wf["waveform"],
        label=f'S1 (id={pair["s1_peak_id"]}, area={pair["s1_area"]:.0f})',
        color="blue",
        linewidth=1.5,
    )
    ax.plot(
        s2_wf["time_ns"],
        s2_wf["waveform"],
        label=f'S2 (id={pair["s2_peak_id"]}, area={pair["s2_area"]:.0f})',
        color="red",
        linewidth=1.5,
    )

    # 标记时间
    ax.axvline(pair["s1_time"] / 1000, color="blue", ls="--", alpha=0.3)
    ax.axvline(pair["s2_time"] / 1000, color="red", ls="--", alpha=0.3)

    ax.set_xlabel("Time (ns)", fontsize=12)
    ax.set_ylabel("Amplitude", fontsize=12)
    ax.set_title(
        f'Pair {pair_id}: Drift={pair["drift_time_ns"]:.1f}ns, '
        f'log10(S2/S1)={pair["log10_s2_s1"]:.2f}',
        fontsize=13,
    )
    ax.legend(fontsize=11)
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    return fig


def plot_pair_grid(accessor, n_pairs=4, selected_only=True):
    """绘制多个配对的网格图

    用法：
    >>> plot_pair_grid(accessor, n_pairs=6)
    """
    pairs = accessor.pairs
    if selected_only and "selected" in pairs.dtype.names:
        pairs = pairs[pairs["selected"]]

    n = min(n_pairs, len(pairs))
    ncols = 2
    nrows = (n + 1) // 2

    fig, axes = plt.subplots(nrows, ncols, figsize=(14, 5 * nrows))
    axes = axes.ravel() if n > 1 else [axes]

    for i in range(n):
        pair = pairs[i]
        s1_wf, s2_wf = accessor.pair_waveforms(pair)

        ax = axes[i]
        ax.plot(s1_wf["time_ns"], s1_wf["waveform"], "b-", label="S1", lw=1.2)
        ax.plot(s2_wf["time_ns"], s2_wf["waveform"], "r-", label="S2", lw=1.2)
        ax.set_title(f'Pair {i}: drift={pair["drift_time_ns"]:.0f}ns', fontsize=11)
        ax.legend(fontsize=9)
        ax.grid(True, alpha=0.3)
        ax.set_xlabel("Time (ns)", fontsize=10)

    # 隐藏多余子图
    for i in range(n, len(axes)):
        axes[i].set_visible(False)

    plt.tight_layout()
    return fig


def plot_s2_candidates(accessor, s2_peak_id, max_candidates=10):
    """绘制某个 S2 的多个 S1 候选波形

    用法：
    >>> # 需要使用 candidates source
    >>> accessor = S1S2PairAccessor(ctx, run_id, source='candidates')
    >>> plot_s2_candidates(accessor, s2_peak_id=123)
    """
    candidates = accessor.pairs_for_s2(s2_peak_id)

    if len(candidates) == 0:
        print(f"No candidates found for S2 {s2_peak_id}")
        return

    # 按 score 排序
    sorted_idx = np.argsort(-candidates["score_total"])
    candidates = candidates[sorted_idx[:max_candidates]]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))

    # 获取 S2 波形（只需一次）
    s2_wf = accessor.waveform(s2_peak_id)
    ax2.plot(s2_wf["time_ns"], s2_wf["waveform"], "r-", linewidth=2, label=f"S2 {s2_peak_id}")

    # 绘制所有 S1 候选
    colors = plt.cm.viridis(np.linspace(0, 1, len(candidates)))
    for i, cand in enumerate(candidates):
        s1_wf = accessor.waveform(int(cand["s1_peak_id"]))
        is_selected = cand.get("selected", False)
        lw = 2 if is_selected else 1
        alpha = 1.0 if is_selected else 0.6
        label = f"S1 {cand['s1_peak_id']} (rank={cand['rank_for_s2']})" + (
            " ✓" if is_selected else ""
        )
        ax1.plot(
            s1_wf["time_ns"],
            s1_wf["waveform"],
            color=colors[i],
            linewidth=lw,
            alpha=alpha,
            label=label,
        )

    ax1.set_title(f"S1 Candidates for S2 {s2_peak_id} (top {len(candidates)})")
    ax1.set_xlabel("Time (ns)")
    ax1.set_ylabel("Amplitude")
    ax1.legend(fontsize=9)
    ax1.grid(True, alpha=0.3)

    ax2.set_title(f"S2 Peak {s2_peak_id}")
    ax2.set_xlabel("Time (ns)")
    ax2.set_ylabel("Amplitude")
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    return fig
