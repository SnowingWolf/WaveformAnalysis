"""
演示如何使用 n_hits 和 rise_time_10_50 进行 S1/S2 分类

这个示例展示了如何配置 PeakClassificationPlugin，使用以下条件识别 S2 信号：
- n_hits >= 8：S2 信号通常包含更多的 hit（多通道响应）
- rise_time_10_50 >= 100 ns：S2 信号的上升时间（10%-50%）较长（缓慢上升）
"""

import numpy as np

from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import (
    LABEL_S1,
    LABEL_S2,
    LABEL_UNKNOWN,
    PEAKS_DTYPE,
    PeakClassificationPlugin,
)


def create_test_data():
    """创建测试数据"""
    # 创建 3 个 peaks
    peaks = np.zeros(3, dtype=PEAKS_DTYPE)

    # Peak 0: S1 候选（少量 hits，快速上升）
    peaks[0]["peak_id"] = 0
    peaks[0]["time_start"] = 1000
    peaks[0]["time_end"] = 1050
    peaks[0]["time_peak"] = 1025
    peaks[0]["center_time"] = 1025
    peaks[0]["width"] = 50.0
    peaks[0]["area"] = 100.0
    peaks[0]["height"] = 10.0
    peaks[0]["rise_time"] = 10.0
    peaks[0]["fall_time"] = 15.0
    peaks[0]["rise_time_10_50"] = 5.0  # 快速上升
    peaks[0]["width_25_75"] = 20.0
    peaks[0]["range_90p_area"] = 40.0
    peaks[0]["n_hits"] = 5  # 少量 hits
    peaks[0]["n_channels"] = 3

    # Peak 1: S2 候选（大量 hits，慢速上升）
    peaks[1]["peak_id"] = 1
    peaks[1]["time_start"] = 2000
    peaks[1]["time_end"] = 2500
    peaks[1]["time_peak"] = 2250
    peaks[1]["center_time"] = 2250
    peaks[1]["width"] = 500.0
    peaks[1]["area"] = 5000.0
    peaks[1]["height"] = 50.0
    peaks[1]["rise_time"] = 100.0
    peaks[1]["fall_time"] = 200.0
    peaks[1]["rise_time_10_50"] = 120.0  # 慢速上升
    peaks[1]["width_25_75"] = 300.0
    peaks[1]["range_90p_area"] = 450.0
    peaks[1]["n_hits"] = 20  # 大量 hits
    peaks[1]["n_channels"] = 10

    # Peak 2: 边界情况（中等 hits，中等上升时间）
    peaks[2]["peak_id"] = 2
    peaks[2]["time_start"] = 3000
    peaks[2]["time_end"] = 3150
    peaks[2]["time_peak"] = 3075
    peaks[2]["center_time"] = 3075
    peaks[2]["width"] = 150.0
    peaks[2]["area"] = 500.0
    peaks[2]["height"] = 15.0
    peaks[2]["rise_time"] = 50.0
    peaks[2]["fall_time"] = 50.0
    peaks[2]["rise_time_10_50"] = 30.0
    peaks[2]["width_25_75"] = 80.0
    peaks[2]["range_90p_area"] = 120.0
    peaks[2]["n_hits"] = 10  # 中等 hits
    peaks[2]["n_channels"] = 5

    return peaks


def main():
    """主函数"""
    # 创建 Context
    ctx = Context()
    ctx.register(PeakClassificationPlugin())

    # 准备测试数据
    run_id = "demo_run"
    peaks = create_test_data()
    ctx._results[(run_id, "peaks")] = peaks

    # 配置分类器：使用字典配置 S2 判断条件
    ctx.set_config(
        {
            "s2_ranges": {
                "n_hits": (8, None),  # n_hits >= 8
                "rise_time_10_50": (100.0, None),  # rise_time_10_50 >= 100 ns
            },
        },
        plugin_name="peak_classification",
    )

    # 执行分类
    labels = ctx.get_data(run_id, "peak_classification")

    # 打印结果
    print("=" * 80)
    print("PeakletS1S2Classifier 演示：使用 n_hits 和 rise_time_10_50")
    print("=" * 80)
    print()
    print("配置方式（字典配置）：")
    print("  s2_ranges = {")
    print("    'n_hits': (8, None),")
    print("    'rise_time_10_50': (100.0, None),")
    print("  }")
    print()
    print("分类条件：")
    print("  S2: n_hits >= 8 AND rise_time_10_50 >= 100 ns")
    print()
    print("分类结果：")
    print("-" * 80)

    label_names = {LABEL_UNKNOWN: "Unknown", LABEL_S1: "S1", LABEL_S2: "S2"}

    for label_data, peak in zip(labels, peaks, strict=False):
        peak_id = label_data["peak_id"]
        label = label_data["label"]
        n_hits = peak["n_hits"]
        rise_time_10_50 = peak["rise_time_10_50"]

        print(f"Peak {peak_id}:")
        print(f"  n_hits: {n_hits}")
        print(f"  rise_time_10_50: {rise_time_10_50:.1f} ns")
        print(f"  分类结果: {label_names[label]}")

        # 解释分类原因
        if label == LABEL_S2:
            print("  ✓ 满足 S2 条件（n_hits >= 8 且 rise_time_10_50 >= 100 ns）")
        else:
            reasons = []
            if n_hits < 8:
                reasons.append(f"n_hits={n_hits} < 8")
            if rise_time_10_50 < 100.0:
                reasons.append(f"rise_time_10_50={rise_time_10_50:.1f} < 100")
            print(f"  ✗ 不满足 S2 条件：{', '.join(reasons)}")

        print()

    print("=" * 80)
    print()

    # 展示输出数据结构
    print("输出数据字段：")
    print(f"  {list(labels.dtype.names)}")
    print()

    # 展示新配置方式的优势
    print("新配置方式的优势：")
    print("  1. 更简洁 - 使用字典配置，不需要为每个特征单独定义配置项")
    print("  2. 更灵活 - 可以动态添加任何 peaks 中的特征")
    print("  3. 更直观 - 直接看配置就知道用了哪些特征")
    print("  4. 依赖更简单 - 仅依赖 peaks，无需分别依赖 peaklet_features 和 peaklets")
    print()


if __name__ == "__main__":
    main()
