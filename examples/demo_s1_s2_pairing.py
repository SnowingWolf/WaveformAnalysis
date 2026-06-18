"""S1-S2 配对插件使用示例

演示如何使用 S1S2PairCandidatesPlugin 生成配对候选。

Author: Claude Code
"""

import numpy as np

from waveform_analysis.core.plugins.builtin.cpu import (
    LABEL_S1,
    LABEL_S2,
    PeakletS1S2ClassifierPlugin,
    S1S2PairCandidatesPlugin,
)
from waveform_analysis.core.plugins.builtin.cpu.peaklet_s1_s2_classifier import (
    PEAKLET_S1_S2_CLASSIFIER_DTYPE,
)
from waveform_analysis.core.plugins.builtin.cpu.peaklets import PEAKS_DTYPE


def create_demo_data():
    """创建演示数据: 2 个 S1, 3 个 S2"""
    # 创建 peaks
    peaks = np.zeros(5, dtype=PEAKS_DTYPE)

    # S1_1: time=1000 ns, area=100
    peaks[0]["peak_id"] = 1
    peaks[0]["center_time"] = 1000 * 1000  # ns -> ps
    peaks[0]["area"] = 100
    peaks[0]["width"] = 50 * 1000  # ns -> ps
    peaks[0]["n_channels"] = 5

    # S1_2: time=2000 ns, area=150
    peaks[1]["peak_id"] = 2
    peaks[1]["center_time"] = 2000 * 1000
    peaks[1]["area"] = 150
    peaks[1]["width"] = 60 * 1000
    peaks[1]["n_channels"] = 6

    # S2_A: time=20000 ns, area=5000
    peaks[2]["peak_id"] = 10
    peaks[2]["center_time"] = 20000 * 1000
    peaks[2]["area"] = 5000
    peaks[2]["width"] = 200 * 1000
    peaks[2]["n_channels"] = 15

    # S2_B: time=25000 ns, area=6000
    peaks[3]["peak_id"] = 11
    peaks[3]["center_time"] = 25000 * 1000
    peaks[3]["area"] = 6000
    peaks[3]["width"] = 250 * 1000
    peaks[3]["n_channels"] = 18

    # S2_C: time=100000 ns, area=8000 (很远,可能与前面 S1 无关)
    peaks[4]["peak_id"] = 12
    peaks[4]["center_time"] = 100000 * 1000
    peaks[4]["area"] = 8000
    peaks[4]["width"] = 300 * 1000
    peaks[4]["n_channels"] = 20

    # 创建 S1/S2 标签
    labels = np.zeros(5, dtype=PEAKLET_S1_S2_CLASSIFIER_DTYPE)
    labels[0] = (1, LABEL_S1)
    labels[1] = (2, LABEL_S1)
    labels[2] = (10, LABEL_S2)
    labels[3] = (11, LABEL_S2)
    labels[4] = (12, LABEL_S2)

    return peaks, labels


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
            self._config[(plugin_name or "S1S2PairCandidatesPlugin", key)] = value


def main():
    print("=" * 70)
    print("S1-S2 配对候选生成演示")
    print("=" * 70)

    # 创建演示数据
    peaks, labels = create_demo_data()

    print("\n输入数据:")
    print("  - 2 个 S1: peak_id=[1, 2], time=[1000, 2000] ns")
    print("  - 3 个 S2: peak_id=[10, 11, 12], time=[20000, 25000, 100000] ns")

    # 初始化插件
    plugin = S1S2PairCandidatesPlugin()
    ctx = SimpleContext()
    ctx.set_data("demo_run", "peaks", peaks)
    ctx.set_data("demo_run", "peaklet_s1_s2", labels)

    # 设置配置
    ctx.set_config(
        {
            "max_drift_time": 50000.0,  # 50 μs
            "min_drift_time": 0.0,
        }
    )

    print("\n配置:")
    print("  - max_drift_time: 50 μs")
    print("  - min_drift_time: 0 μs")

    # 生成候选
    candidates = plugin.compute(ctx, "demo_run")

    print(f"\n生成候选对: {len(candidates)} 个")
    print("\n" + "=" * 70)
    print("候选详情:")
    print("=" * 70)

    for i, cand in enumerate(candidates):
        print(f"\n候选 #{i+1}:")
        print(f"  S1: peak_id={cand['s1_peak_id']}, area={cand['s1_area']:.1f}")
        print(f"  S2: peak_id={cand['s2_peak_id']}, area={cand['s2_area']:.1f}")
        print(f"  漂移时间: {cand['drift_time_ns']:.0f} ns ({cand['drift_time_ns']/1000:.1f} μs)")
        print(f"  S2/S1 比值: {10**cand['log10_s2_s1']:.1f} (log10={cand['log10_s2_s1']:.2f})")
        print("  Ambiguity:")
        print(f"    - 该 S2 有 {cand['n_s1_candidates_for_s2']} 个 S1 候选")
        print(f"    - 该 S1 有 {cand['n_s2_candidates_for_s1']} 个 S2 候选")

    # 分析结果
    print("\n" + "=" * 70)
    print("分析:")
    print("=" * 70)

    # 按 S2 分组
    s2_groups = {}
    for cand in candidates:
        s2_id = cand["s2_peak_id"]
        if s2_id not in s2_groups:
            s2_groups[s2_id] = []
        s2_groups[s2_id].append(cand)

    for s2_id, cands in s2_groups.items():
        print(f"\nS2 {s2_id} 的候选:")
        for cand in sorted(cands, key=lambda c: c["drift_time_ns"]):
            print(
                f"  - S1 {cand['s1_peak_id']}: "
                f"drift={cand['drift_time_ns']/1000:.1f} μs, "
                f"S2/S1={10**cand['log10_s2_s1']:.1f}"
            )

    # 检查是否有 S2 超出时间窗口
    s2_without_candidates = []
    for peak in peaks:
        if peak["peak_id"] in [10, 11, 12]:  # S2
            has_cand = any(c["s2_peak_id"] == peak["peak_id"] for c in candidates)
            if not has_cand:
                s2_without_candidates.append(peak["peak_id"])

    if s2_without_candidates:
        print(f"\n⚠️  孤立 S2 (无候选): {s2_without_candidates}")
        print("   (可能超出 max_drift_time 或在 S1 之前)")

    print("\n" + "=" * 70)
    print("✓ 演示完成!")
    print("=" * 70)


if __name__ == "__main__":
    main()
