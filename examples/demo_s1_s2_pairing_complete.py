"""S1-S2 配对完整流程演示

演示两层架构的协同工作:
1. S1S2PairCandidatesPlugin: 生成候选
2. S1S2PairSelectionPlugin: 选择最佳配对 (largest 模式)

Author: Claude Code
"""

import numpy as np

from waveform_analysis.core.plugins.builtin.cpu import (
    FLAG_CLOSE_COMPETITOR,
    FLAG_MULTI_S1_CANDIDATE,
    LABEL_S1,
    LABEL_S2,
    S1S2PairCandidatesPlugin,
    S1S2PairSelectionPlugin,
)
from waveform_analysis.core.plugins.builtin.cpu.peak_classification import (
    PEAK_CLASSIFICATION_DTYPE,
)
from waveform_analysis.core.plugins.builtin.cpu.peaklets import PEAKS_DTYPE


def create_demo_peak(peak_id, time_ns, area, width_ns=100, n_channels=5):
    """创建演示 peak"""
    time_ps = int(time_ns * 1000)
    width_ps = int(width_ns * 1000)

    peak = np.zeros(1, dtype=PEAKS_DTYPE)[0]
    peak["peak_id"] = peak_id
    peak["center_time"] = time_ps
    peak["time_start"] = time_ps - width_ps // 2
    peak["time_peak"] = time_ps
    peak["time_end"] = time_ps + width_ps // 2
    peak["area"] = area
    peak["height"] = area / 10.0
    peak["width"] = width_ps
    peak["n_channels"] = n_channels

    return peak


def create_label(peak_id, label):
    """创建 S1/S2 标签"""
    row = np.zeros(1, dtype=PEAK_CLASSIFICATION_DTYPE)[0]
    row["peak_id"] = peak_id
    row["label"] = label
    return row


class SimpleContext:
    """简单的 Mock Context"""

    def __init__(self):
        self._data = {}
        self._config = {}

    def get_data(self, run_id, data_name):
        return self._data.get((run_id, data_name))

    def set_data(self, run_id, data_name, data):
        self._data[(run_id, data_name)] = data

    def get_config(self, plugin, option_name):
        key = (plugin.__class__.__name__, option_name)
        if key in self._config:
            return self._config[key]
        return plugin.options[option_name].default

    def set_config(self, config, plugin_name=None):
        for key, value in config.items():
            self._config[(plugin_name or "Unknown", key)] = value


def main():
    print("=" * 80)
    print("S1-S2 配对完整流程演示 (两层架构)")
    print("=" * 80)

    # 创建演示数据: 3 个 S1, 2 个 S2
    peaks = np.array(
        [
            create_demo_peak(peak_id=1, time_ns=1000, area=80, n_channels=4),  # S1_A (小)
            create_demo_peak(peak_id=2, time_ns=2000, area=200, n_channels=8),  # S1_B (大)
            create_demo_peak(peak_id=3, time_ns=3000, area=120, n_channels=6),  # S1_C (中)
            create_demo_peak(peak_id=10, time_ns=20000, area=5000, n_channels=15),  # S2_X
            create_demo_peak(peak_id=11, time_ns=25000, area=6000, n_channels=18),  # S2_Y
        ]
    )

    labels = np.array(
        [
            create_label(peak_id=1, label=LABEL_S1),
            create_label(peak_id=2, label=LABEL_S1),
            create_label(peak_id=3, label=LABEL_S1),
            create_label(peak_id=10, label=LABEL_S2),
            create_label(peak_id=11, label=LABEL_S2),
        ]
    )

    print("\n输入数据:")
    print("  S1 峰:")
    print("    - S1_A (id=1): time=1μs, area=80")
    print("    - S1_B (id=2): time=2μs, area=200 ⭐ 最大")
    print("    - S1_C (id=3): time=3μs, area=120")
    print("  S2 峰:")
    print("    - S2_X (id=10): time=20μs, area=5000")
    print("    - S2_Y (id=11): time=25μs, area=6000")

    # 初始化 context
    ctx = SimpleContext()
    ctx.set_data("demo_run", "peaks", peaks)
    ctx.set_data("demo_run", "peak_classification", labels)

    # ========================================================================
    # Phase 1: 候选生成
    # ========================================================================
    print("\n" + "=" * 80)
    print("Phase 1: 候选生成 (S1S2PairCandidatesPlugin)")
    print("=" * 80)

    plugin_cand = S1S2PairCandidatesPlugin()
    ctx.set_config(
        {
            "max_drift_time": 50000.0,  # 50 μs
            "min_drift_time": 0.0,
        },
        plugin_name="S1S2PairCandidatesPlugin",
    )

    candidates = plugin_cand.compute(ctx, "demo_run")

    print(f"\n生成 {len(candidates)} 个候选对:")
    for i, cand in enumerate(candidates):
        print(f"\n  候选 #{i+1}:")
        print(f"    S1: id={cand['s1_peak_id']}, area={cand['s1_area']:.0f}")
        print(f"    S2: id={cand['s2_peak_id']}, area={cand['s2_area']:.0f}")
        print(f"    漂移时间: {cand['drift_time_ns']/1000:.1f} μs")
        print(f"    S2/S1: {10**cand['log10_s2_s1']:.1f}")
        print(f"    Ambiguity: S2 有 {cand['n_s1_candidates_for_s2']} 个 S1 候选")

    # ========================================================================
    # Phase 2: 选择最佳配对
    # ========================================================================
    print("\n" + "=" * 80)
    print("Phase 2: 选择最佳配对 (S1S2PairSelectionPlugin)")
    print("=" * 80)

    plugin_sel = S1S2PairSelectionPlugin()
    ctx.set_data("demo_run", "s1_s2_pair_candidates", candidates)
    ctx.set_config(
        {
            "selection_mode": "largest",  # 选择面积最大的 S1
            "close_competitor_threshold": 0.1,
        },
        plugin_name="S1S2PairSelectionPlugin",
    )

    pairs = plugin_sel.compute(ctx, "demo_run")

    print("\n选择模式: largest (选择面积最大的 S1)")
    print("\n选中的配对:")

    selected = pairs[pairs["selected"]]
    for pair in selected:
        print(f"\n  S2 {pair['s2_peak_id']} ← S1 {pair['s1_peak_id']}")
        print(f"    S1 面积: {pair['s1_area']:.0f}")
        print(f"    S1 质量分数: {pair['score_s1_quality']:.3f}")
        print(f"    总分: {pair['score_total']:.3f}")
        print(f"    排名: {pair['rank_for_s2']}")
        print(f"    与次优分数差: {pair['delta_score_to_next_best']:.3f}")

        if pair["flags"] & FLAG_CLOSE_COMPETITOR:
            print("    ⚠️  竞争激烈 (次优候选分数接近)")

    # ========================================================================
    # 分析结果
    # ========================================================================
    print("\n" + "=" * 80)
    print("分析: 为什么选择这些配对?")
    print("=" * 80)

    # 按 S2 分组显示所有候选
    for s2_id in [10, 11]:
        s2_cands = pairs[pairs["s2_peak_id"] == s2_id]
        print(f"\nS2 {s2_id} 的所有候选 (按分数排序):")

        sorted_cands = sorted(s2_cands, key=lambda c: c["score_total"], reverse=True)
        for cand in sorted_cands:
            selected_mark = "✓ 选中" if cand["selected"] else "  未选"
            print(
                f"  {selected_mark} - S1 {cand['s1_peak_id']}: "
                f"area={cand['s1_area']:.0f}, "
                f"score={cand['score_total']:.3f}, "
                f"rank={cand['rank_for_s2']}"
            )

    # ========================================================================
    # 统计信息
    # ========================================================================
    print("\n" + "=" * 80)
    print("统计信息")
    print("=" * 80)

    print("\n候选统计:")
    print(f"  - 总候选数: {len(candidates)}")
    print(f"  - 选中配对数: {len(selected)}")
    print(
        f"  - 多候选 S2: {np.sum(candidates['n_s1_candidates_for_s2'] > 1)}/{len(np.unique(candidates['s2_peak_id']))}"
    )
    print(f"  - 竞争激烈配对: {np.sum(selected['delta_score_to_next_best'] < 0.1)}")

    print("\n分数统计:")
    print(f"  - 最高分: {np.max(pairs['score_total']):.3f}")
    print(f"  - 最低分: {np.min(pairs['score_total']):.3f}")
    print(f"  - 平均分: {np.mean(pairs['score_total']):.3f}")

    print("\n" + "=" * 80)
    print("✓ 演示完成!")
    print("=" * 80)

    print("\n设计亮点:")
    print("  1. 两层架构: 候选生成 ↔ 选择逻辑分离")
    print("  2. 完整诊断: 保留所有候选,不仅是最终结果")
    print("  3. 可扩展: largest 模式只是开始,可以添加 nearest、best_score 等")
    print("  4. Ambiguity 量化: delta_score 判断选择可靠性")
    print("  5. 排名信息: rank_for_s2 显示每个候选的相对质量")


if __name__ == "__main__":
    main()
