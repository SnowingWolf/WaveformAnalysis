"""
演示如何使用 query_helpers 模块查询 peak、merged 和 hit_threshold 之间的关系

这个示例展示了：
1. 如何从 DAQAnalyzer 获取数据
2. 如何使用查询函数获取 hit 数据
3. 如何计算和可视化时间间隔
"""

import matplotlib.pyplot as plt
import numpy as np

from waveform_analysis.utils import get_hits_for_peak

# 注意：这个示例需要真实的数据文件才能运行
# 请根据你的数据路径修改以下配置

# 示例用法（需要真实数据）:
# from waveform_analysis.utils import DAQAnalyzer
#
# # 1. 创建 DAQAnalyzer 并加载数据
# analyzer = DAQAnalyzer(
#     data_dir="path/to/your/data",
#     output_dir="path/to/output",
#     targets=["peaklet_components", "hit_merged_components", "hit_threshold"]
# )
# analyzer.make("run_001")
#
# # 2. 获取数据
# peaklet_components = analyzer.get_array("run_001", "peaklet_components")
# hit_merged_components = analyzer.get_array("run_001", "hit_merged_components")
# hit_threshold = analyzer.get_array("run_001", "hit_threshold")
#
# # 3. 选择一个 peak_id 进行分析
# peak_id = 123  # 替换为你感兴趣的 peak_id
#
# # 4. 获取该 peak 的所有 hit 数据（带时间间隔）
# intervals = get_hits_for_peak(
#     peak_id=peak_id,
#     peaklet_components=peaklet_components,
#     hit_merged_components=hit_merged_components,
#     hit_threshold=hit_threshold
# )
#
# # 5. 查看 DataFrame
# print(f"Peak {peak_id} 包含 {len(intervals)} 个 hits")
# print("\n前几行数据：")
# print(intervals.head())
#
# # 6. 查看按 merged_index 分组的统计
# print("\n按 merged_index 分组的 hit 数量：")
# print(intervals.groupby("merged_index").size())
#
# # 7. 绘制时间间隔直方图
# dt = intervals["dt_start_to_start_ns"].dropna()
#
# if len(dt) > 0:
#     plt.figure(figsize=(10, 6))
#     plt.hist(dt, bins=np.linspace(0, dt.max(), 100), alpha=0.7, edgecolor='black')
#     plt.yscale("log")
#     plt.xlabel("hit_threshold interval within hit_merged (ns)")
#     plt.ylabel("counts")
#     plt.title(f"Hit Time Intervals for Peak {peak_id}")
#     plt.grid(True, alpha=0.3)
#     plt.tight_layout()
#     plt.savefig(f"hit_intervals_peak_{peak_id}.png", dpi=150)
#     plt.show()
#     print(f"\n图表已保存到 hit_intervals_peak_{peak_id}.png")
# else:
#     print("\n没有足够的数据绘制直方图")
#
# # 8. 分析时间间隔统计
# if len(dt) > 0:
#     print("\n时间间隔统计：")
#     print(f"  平均值: {dt.mean():.2f} ns")
#     print(f"  中位数: {dt.median():.2f} ns")
#     print(f"  最小值: {dt.min():.2f} ns")
#     print(f"  最大值: {dt.max():.2f} ns")
#     print(f"  标准差: {dt.std():.2f} ns")


# =============================================================================
# 模拟数据示例（无需真实数据即可运行）
# =============================================================================


def demo_with_simulated_data():
    """使用模拟数据演示查询功能"""
    print("=" * 70)
    print("使用模拟数据演示 query_helpers 功能")
    print("=" * 70)

    # 创建模拟的 peaklet_components
    peaklet_components = np.array(
        [
            (100, 200),
            (100, 201),
            (100, 202),
            (101, 203),
        ],
        dtype=[("peak_id", "i8"), ("merged_index", "i8")],
    )

    # 创建模拟的 hit_merged_components
    hit_merged_components = np.array(
        [
            (200, 0),
            (200, 1),
            (200, 2),
            (201, 3),
            (201, 4),
            (201, 5),
            (201, 6),
            (202, 7),
            (202, 8),
        ],
        dtype=[("merged_index", "i8"), ("hit_index", "i8")],
    )

    # 创建模拟的 hit_threshold
    hit_threshold_dtype = np.dtype(
        [
            ("position", "i8"),
            ("edge_start", "i4"),
            ("edge_end", "i4"),
            ("width", "f4"),
            ("dt", "i4"),
            ("timestamp", "i8"),
            ("board", "i2"),
            ("channel", "i2"),
            ("record_id", "i8"),
        ]
    )
    hit_threshold = np.zeros(9, dtype=hit_threshold_dtype)

    # 填充模拟数据
    for i in range(9):
        hit_threshold[i]["position"] = 100 + i * 10
        hit_threshold[i]["edge_start"] = 100 + i * 10
        hit_threshold[i]["edge_end"] = 110 + i * 10
        hit_threshold[i]["width"] = 10.0
        hit_threshold[i]["dt"] = 10  # 10 ns
        hit_threshold[i]["timestamp"] = 1000000 + i * 500000  # 每个 hit 间隔 500 us
        hit_threshold[i]["board"] = 1
        hit_threshold[i]["channel"] = i % 4
        hit_threshold[i]["record_id"] = 1000

    # 查询 peak 100 的 hit 数据
    peak_id = 100
    intervals = get_hits_for_peak(
        peak_id=peak_id,
        peaklet_components=peaklet_components,
        hit_merged_components=hit_merged_components,
        hit_threshold=hit_threshold,
    )

    print(f"\nPeak {peak_id} 包含 {len(intervals)} 个 hits")
    print("\n完整数据：")
    print(intervals.to_string())

    print("\n按 merged_index 分组的 hit 数量：")
    print(intervals.groupby("merged_index").size())

    # 绘制时间间隔直方图
    dt = intervals["dt_start_to_start_ns"].dropna()

    if len(dt) > 0:
        plt.figure(figsize=(10, 6))
        plt.hist(dt, bins=20, alpha=0.7, edgecolor="black", color="steelblue")
        plt.xlabel("hit_threshold interval within hit_merged (ns)", fontsize=12)
        plt.ylabel("counts", fontsize=12)
        plt.title(f"Hit Time Intervals for Peak {peak_id} (Simulated Data)", fontsize=14)
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig("demo_hit_intervals.png", dpi=150)
        print("\n图表已保存到 demo_hit_intervals.png")

        print("\n时间间隔统计：")
        print(f"  平均值: {dt.mean():.2f} ns")
        print(f"  中位数: {dt.median():.2f} ns")
        print(f"  最小值: {dt.min():.2f} ns")
        print(f"  最大值: {dt.max():.2f} ns")
        print(f"  标准差: {dt.std():.2f} ns")

    print("\n" + "=" * 70)
    print("演示完成！")
    print("=" * 70)


if __name__ == "__main__":
    demo_with_simulated_data()
