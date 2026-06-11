# Peaklet 可视化示例

## 概述

本目录包含 peaklet 检测流程的可视化演示脚本。

## 脚本说明

### `demo_peaklet_visualization.py`

展示完整的 peaklet 检测流程：

1. **Hit 检测**：从模拟的多通道波形数据中检测阈值触发点（hits）
2. **Hit 合并**：将同一通道内时间相近的 hits 合并为 `hit_merged`
3. **Peaklet 聚类**：将跨通道时间重叠的 `hit_merged` 聚类为 `peaklets`
4. **特征提取**：提取每个 peaklet 的波形特征（面积、高度、宽度、上升/下降时间等）
5. **可视化**：生成包含 4 个子图的完整流程图

## 运行示例

```bash
# 运行演示脚本
python examples/demo_peaklet_visualization.py

# 输出图片位于: examples/output/peaklet_visualization.png
```

## 输出说明

脚本会生成一张包含 4 个子图的可视化图表：

- **子图 1**：原始波形 + Hit 检测区间（红色阴影）
- **子图 2**：Hit 合并后的时间区间（按通道分组）
- **子图 3**：Peaklet 聚类结果（跨通道的时间重叠区间）
- **子图 4**：Peaklet 波形特征（归一化波形 + 峰值标记 + 特征数值）

## 主要特性

### Peaklet 检测的优势

- **跨通道聚类**：自动识别同一物理事件在多个通道的信号
- **时间一致性**：基于时间窗口（`time_window_ns`）判断是否属于同一事件
- **灵活配置**：可调节合并窗口、最大宽度等参数
- **特征丰富**：提取面积、高度、宽度、上升/下降时间等多维特征

### 关键参数

- `time_window_ns`：跨通道 peaklet 合并时间窗口（默认 100 ns）
- `max_total_width_ns`：单个 peaklet 的最大总宽度（默认 10000 ns）
- `merge_gap_ns`：同通道 hit 合并间隔（默认 10 ns）

## 示例输出

```
============================================================
检测结果详情
============================================================

【Peak 0】
  时间范围: 156.0 - 260.0 ns
  中心时间: 208.0 ns
  峰值时间: 208.0 ns
  面积: 12609.00
  高度: 687.00
  宽度: 104.00 ns
  上升时间: 52.00 ns
  下降时间: 52.00 ns
  包含 hits: 4
  跨越通道: 4
```

## 相关文档

- [Peaks 插件文档](../docs/plugins/reference/builtin/auto/peaks.md)
- [Peaklet Features 插件文档](../docs/plugins/reference/builtin/auto/peaklet_features.md)
- [Agent 插件参考](../docs/plugins/reference/agent/peaks.md)
