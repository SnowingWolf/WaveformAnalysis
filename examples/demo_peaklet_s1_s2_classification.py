"""
演示 PeakletS1S2ClassifierPlugin 的使用

该示例展示如何：
1. 使用 peaklet 特征进行 S1/S2 分类
2. 配置多维特征范围
3. 分析分类结果
"""

import numpy as np

from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import (
    LABEL_S1,
    LABEL_S2,
    LABEL_UNKNOWN,
    PeakletS1S2ClassifierPlugin,
)


def main():
    """演示 peaklet S1/S2 分类"""

    # 创建 Context
    ctx = Context(storage_dir="./output/peaklet_s1_s2_demo")

    # 注册分类插件
    ctx.register(PeakletS1S2ClassifierPlugin())

    # 配置分类参数（基于暗物质探测器的典型参数）
    ctx.set_config(
        {
            # S1 特征：闪烁光，窄脉冲，快速
            "s1_width_range": (10.0, 200.0),  # 10-200 ns
            "s1_area_range": (10.0, 1000.0),  # 小面积
            "s1_rise_time_range": (5.0, 100.0),  # 快速上升
            "s1_fall_time_range": (5.0, 150.0),  # 快速下降
            "s1_n_channels_range": (2, 20),  # 少量通道
            # S2 特征：电离光，宽脉冲，慢速
            "s2_width_range": (500.0, 20000.0),  # 0.5-20 μs
            "s2_area_range": (1000.0, None),  # 大面积
            "s2_rise_time_range": (100.0, None),  # 慢速上升
            "s2_n_channels_range": (5, None),  # 多通道
            # 冲突处理：优先选择 S2（通常 S2 更重要）
            "conflict_policy": "prefer_s2",
            # 严格模式：确保至少配置了一个判断条件
            "strict": True,
        },
        plugin_name="peaklet_s1_s2",
    )

    print("=" * 70)
    print("PeakletS1S2ClassifierPlugin 使用示例")
    print("=" * 70)
    print("\n配置参数：")
    print("  S1: 窄脉冲 (10-200ns), 小面积 (10-1000), 快速上升/下降")
    print("  S2: 宽脉冲 (0.5-20μs), 大面积 (>1000), 慢速上升")
    print("  冲突策略: prefer_s2")
    print()

    # 注意：实际使用中，peaklet_features 和 peaklets 应该从完整的处理链获得
    # 这里仅作演示
    print("提示：")
    print("  该插件需要从完整的处理链获取 peaklet_features 和 peaklets 数据")
    print("  处理链路径：")
    print("    raw_files -> waveforms -> records -> wave_pool ->")
    print("    filtered_waveforms -> hits -> hit_merged -> peaklets ->")
    print("    peaklet_features -> peaklet_s1_s2")
    print()

    # 输出数据类型信息
    plugin = PeakletS1S2ClassifierPlugin()
    print("输出数据类型字段：")
    for name in plugin.output_dtype.names:
        dtype = plugin.output_dtype.fields[name][0]
        print(f"  - {name:20s} ({dtype})")
    print()

    # 分类标签说明
    print("分类标签：")
    print(f"  LABEL_UNKNOWN = {LABEL_UNKNOWN}  (不满足任何分类条件)")
    print(f"  LABEL_S1      = {LABEL_S1}  (闪烁光信号)")
    print(f"  LABEL_S2      = {LABEL_S2}  (电离光信号)")
    print()

    print("=" * 70)
    print("配置建议：")
    print("=" * 70)
    print()
    print("1. 初步配置：")
    print("   - 仅使用 width 和 area 进行初步分类")
    print("   - 观察分类结果分布，确定合理的阈值")
    print()
    print("2. 精细调整：")
    print("   - 添加 rise_time、fall_time 等时间特征")
    print("   - 使用 n_channels 过滤单通道噪声或多通道事件")
    print()
    print("3. 冲突处理：")
    print("   - prefer_s1: 适用于关注低能量 S1 事件的场景")
    print("   - prefer_s2: 适用于关注电离信号的场景")
    print("   - unknown: 严格分类，模糊事件标记为 unknown")
    print()
    print("4. 验证：")
    print("   - 可视化不同标签的特征分布（width vs area 散点图）")
    print("   - 检查 unknown 标签的比例和特征")
    print("   - 与物理预期对比（S1/S2 比例，能量分布等）")
    print()

    print("=" * 70)
    print("完整使用示例代码：")
    print("=" * 70)
    print(
        """
# 1. 创建完整的处理上下文
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import PeakletS1S2ClassifierPlugin

ctx = Context(storage_dir="./cache")
ctx.register(PeakletS1S2ClassifierPlugin())

# 2. 配置分类参数
ctx.set_config({
    "s1_width_range": (10.0, 200.0),
    "s1_area_range": (10.0, 1000.0),
    "s2_width_range": (500.0, 20000.0),
    "s2_area_range": (1000.0, None),
}, plugin_name="peaklet_s1_s2")

# 3. 获取分类结果
run_id = "run_001"
labels = ctx.get_data(run_id, "peaklet_s1_s2")

# 4. 分析结果
s1_count = np.sum(labels["label"] == 1)
s2_count = np.sum(labels["label"] == 2)
unknown_count = np.sum(labels["label"] == 0)

print(f"S1 事件: {s1_count}")
print(f"S2 事件: {s2_count}")
print(f"未分类: {unknown_count}")

# 5. 提取 S1 和 S2 事件
s1_events = labels[labels["label"] == 1]
s2_events = labels[labels["label"] == 2]

# 6. 绘制分布图
import matplotlib.pyplot as plt

plt.figure(figsize=(10, 6))
plt.scatter(s1_events["width_ns"], s1_events["area"],
            label="S1", alpha=0.5, s=10)
plt.scatter(s2_events["width_ns"], s2_events["area"],
            label="S2", alpha=0.5, s=10)
plt.xlabel("Width (ns)")
plt.ylabel("Area")
plt.xscale("log")
plt.yscale("log")
plt.legend()
plt.title("S1/S2 Classification")
plt.savefig("s1_s2_classification.png", dpi=150)
plt.close()
"""
    )

    print("\n完成！")


if __name__ == "__main__":
    main()
