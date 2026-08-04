# plot_peak_channels_with_sum 使用指南

## 功能概述

`plot_peak_channels_with_sum` 函数用于可视化指定 peak 的多通道波形组成，并显示所有通道的求和波形。

## 主要特性

- **多通道展示**：每个通道的波形独立显示在自己的子图中
- **求和波形**：顶部显示所有通道的求和结果
- **时间对齐**：所有波形按事件内相对时间对齐（纳秒）
- **Hit 窗口高亮**：通过彩色背景标识每个 hit 的时间范围
- **Merged Index 标签**：显示每个 hit 的 merged_index
- **灵活分组**：支持按通道号或 (板号, 通道号) 分组

## 使用方法

### 基本用法

```python
from waveform_analysis.utils.visualization import plot_peak_channels_with_sum

# 从 context 获取必要数据
peaklet_comps = context.get_data(run_id, "peaklet_components")
hit_merged = context.get_data(run_id, "hit_merged")
hit_merged_comps = context.get_data(run_id, "hit_merged_components")
hit_threshold = context.get_data(run_id, "hit_threshold")
records = context.get_data(run_id, "records")
wave_pool = context.get_data(run_id, "wave_pool")
peaks = context.get_data(run_id, "peaks")

# 构建 record 查找字典
record_lookup = {int(rec["record_id"]): rec for rec in records}

# 绘制 peak 42 的波形
fig, axes = plot_peak_channels_with_sum(
    peak_id=42,
    peaklet_components=peaklet_comps,
    hit_merged=hit_merged,
    hit_merged_components=hit_merged_comps,
    hit_threshold=hit_threshold,
    wave_pool=wave_pool,
    record_lookup=record_lookup,
    peaks_raw=peaks,
)
```

### 自定义参数

```python
# 增加 padding，按通道号分组
fig, axes = plot_peak_channels_with_sum(
    peak_id=42,
    peaklet_components=peaklet_comps,
    hit_merged=hit_merged,
    hit_merged_components=hit_merged_comps,
    hit_threshold=hit_threshold,
    wave_pool=wave_pool,
    record_lookup=record_lookup,
    peaks_raw=peaks,
    pad=50,              # 增加 padding 到 50 个采样点
    group_by="channel",  # 按通道号分组（忽略板号）
)
```

## 参数说明

### 必需参数

| 参数 | 类型 | 说明 |
|------|------|------|
| `peak_id` | int | 要可视化的 peak ID |
| `peaklet_components` | ndarray | Peaklet 组件数组（含 'peak_id', 'merged_index'） |
| `hit_merged` | ndarray | 合并的 hit 数组 |
| `hit_merged_components` | ndarray | Hit 合并组件数组 |
| `hit_threshold` | ndarray | 阈值 hit 数组 |
| `wave_pool` | ndarray | 波形数据池 |
| `record_lookup` | dict | Record 查找字典 `{record_id: record}` |
| `peaks_raw` | ndarray | Peak 数组（用于显示 n_hits） |

### 可选参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `pad` | int | 30 | Hit 边界外的扩展采样点数 |
| `group_by` | str | "board_channel" | 分组方式："channel" 或 "board_channel" |

## 输出说明

### 返回值

- `fig`: matplotlib Figure 对象（如果没有数据则为 None）
- `axes`: numpy 数组，包含所有子图的 Axes 对象（如果没有数据则为 None）

### 图形布局

1. **顶部子图（高度 2.5x）**：求和波形
   - 标题显示：`peak_id=X, summed waveform, peaks.n_hits=N`
   - 黑色实线表示所有通道的求和

2. **其余子图（每个高度 1x）**：各通道波形
   - Y 轴标签：通道标识（如 "board 0, ch 5"）
   - 彩色波形线：该通道的信号
   - 彩色背景：Hit 窗口时间范围
   - 数字标签：merged_index

### 时间轴

- X 轴：相对于事件起始的时间（纳秒）
- 所有波形自动对齐到事件最早时间

## 工作原理

### 数据流程

1. **查找 Peaklet Components**
   - 从 `peaklet_components` 中找到所有 `peak_id` 匹配的记录
   - 提取对应的 `merged_index` 列表

2. **提取 Hit Merged**
   - 根据 `merged_index` 从 `hit_merged` 获取合并的 hit

3. **重建波形**
   - 单 record hit：直接从 record 提取窗口
   - 跨 record hit：从 `hit_merged_components` 和 `hit_threshold` 重建

4. **时间对齐**
   - 计算所有波形的绝对时间戳
   - 转换为相对于事件起始的时间（纳秒）

5. **求和计算**
   - 使用最小 dt 创建统一时间网格
   - 将所有通道波形插值到该网格并求和

6. **绘图**
   - 创建多子图布局
   - 顶部显示求和波形
   - 下方按通道显示各波形

## 使用场景

### 1. Peak 质量检查

```python
# 检查某个 peak 是否由多个通道正确组成
fig, axes = plot_peak_channels_with_sum(
    peak_id=suspect_peak_id,
    ...
)
# 观察：
# - 求和波形是否符合预期形状
# - 各通道是否贡献合理
# - 时间对齐是否正确
```

### 2. S1/S2 分类验证

```python
# 可视化 S1 候选（应该窄且快）
fig, axes = plot_peak_channels_with_sum(
    peak_id=s1_peak_id,
    pad=20,  # S1 窄，减少 padding
    ...
)

# 可视化 S2 候选（应该宽且慢）
fig, axes = plot_peak_channels_with_sum(
    peak_id=s2_peak_id,
    pad=100,  # S2 宽，增加 padding
    ...
)
```

### 3. 多板调试

```python
# 按 (板号, 通道号) 分组，检查跨板信号
fig, axes = plot_peak_channels_with_sum(
    peak_id=cross_board_peak_id,
    group_by="board_channel",  # 区分不同板
    ...
)
```

### 4. Hit Merging 验证

```python
# 检查 merged_index 标签，验证 hit merging 是否正确
# 同一通道内，相邻 hit 应该有不同的 merged_index
fig, axes = plot_peak_channels_with_sum(
    peak_id=merged_peak_id,
    ...
)
# 观察 merged_index 标签的分布
```

## 常见问题

### Q1: 返回 None, None 怎么办？

**原因**：没有找到该 peak 的数据或所有波形窗口无效。

**检查**：
```python
# 检查 peak 是否存在
comps = peaklet_components[peaklet_components["peak_id"] == peak_id]
print(f"找到 {len(comps)} 个 peaklet components")

# 检查 hit_merged 是否存在
merged_indices = comps["merged_index"].astype(int)
hms = hit_merged[merged_indices]
print(f"找到 {len(hms)} 个 hit_merged")
```

### Q2: 波形显示不完整？

**原因**：`pad` 太小或 hit 窗口边界不正确。

**解决**：
```python
# 增加 pad 值
fig, axes = plot_peak_channels_with_sum(
    peak_id=peak_id,
    pad=100,  # 增加到 100 采样点
    ...
)
```

### Q3: 求和波形看起来不对？

**可能原因**：
1. 极性设置错误（检查 record 的 'polarity' 字段）
2. 基线计算不准确
3. 时间对齐问题（检查 dt 和 timestamp）

**调试**：
```python
# 检查各通道波形是否合理
for i, ax in enumerate(axes[1:]):
    print(f"通道 {i}: y 范围 {ax.get_ylim()}")
```

### Q4: 内存占用过大？

**原因**：Peak 包含太多通道或时间跨度太长。

**解决**：
```python
# 减少 pad
fig, axes = plot_peak_channels_with_sum(
    peak_id=peak_id,
    pad=10,  # 减少到 10 采样点
    ...
)

# 或者只看特定通道（需要修改函数，目前未实现）
```

## 技术细节

### 时间精度

- 内部使用皮秒（ps）精度
- 显示时转换为纳秒（ns）
- 求和时使用最小 dt 确保对齐

### 颜色方案

- 使用 matplotlib 的 "tab20" 色图
- 最多支持 20 个不同通道/分组
- 颜色按 key 排序后分配

### 坐标系统

```
event_t0 = 事件最早时间戳（ps）
相对时间（ns）= (绝对时间（ps）- event_t0) / 1000
```

## 依赖要求

- **matplotlib**: 必需，用于绘图
- **numpy**: 必需，数值计算
- **waveform_analysis**: 必需，数据类型定义

## 性能考虑

- **数据规模**：适用于单个 peak（通常 <50 个通道）
- **时间复杂度**：O(n_channels × n_samples)
- **内存占用**：主要取决于 wave_pool 大小和 pad 值

## 示例输出

```
peak_id=42, summed waveform, peaks.n_hits=8
[顶部子图: 黑色求和波形]

board 0, ch 5
[彩色波形，带 merged_index 标签]

board 0, ch 7
[彩色波形，带 merged_index 标签]

...

Time from event start (ns)
```

## 相关函数

- `plot_waveforms`: Plotly 交互式波形查看器
- `corner_hist`: 多变量统计分析
- `plot_1d_cut_on_corner`: 单变量切割线绘制
- `plot_2d_cut_on_corner`: 二维切割曲线绘制

## 版本历史

- **v1.0** (2026-06-17): 初始版本
  - 支持多通道波形展示
  - 自动求和和时间对齐
  - Hit 窗口高亮和标签
