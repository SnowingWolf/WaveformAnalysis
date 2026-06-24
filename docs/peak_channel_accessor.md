# PeakChannelAccessor 设计文档

## 概述

`PeakChannelAccessor` 是一个用于访问 peak 通道级数据的统一接口，集成了数据访问和可视化功能。

## 核心特性

### 1. 分层加载

```python
# Feature Layer（默认加载）
- peaklet_components
- hit_merged
- hit_merged_features
- peaks（可选）

# Waveform Layer（延迟加载）
- records
- hit_threshold
- hit_merged_components
- wave_pool
```

**优势**：
- 不需要波形时，只加载几百 KB 的特征数据
- 避免加载几 GB 的 wave_pool
- 显著提升交互式分析速度

### 2. 索引优化

预建索引，避免高频布尔筛选：

```python
# O(1) 查找
_peak_to_merged_idx = {peak_id: [merged_index, ...]}
_record_id_to_idx = {record_id: row_index}
_merged_to_hit_idx = {merged_index: [hit_index, ...]}

# 不再使用 O(n) 扫描
# records[records["record_id"] == record_id]  ❌
# records[record_id_to_idx[record_id]]        ✅
```

### 3. 统一接口

数据访问和可视化在同一个类中：

```python
accessor = PeakChannelAccessor(context, run_id)

# 数据访问
channels = accessor.get_peak_channels(peak_id=42)

# 可视化
accessor.plot(peak_id=42)
```

## API 参考

### 数据访问方法

#### `get_peak_channels(peak_id)`

获取 peak 的所有通道特征（不加载波形）

**返回字段**：
- `peak_id`: int
- `merged_index`: int
- `board`: int
- `channel`: int
- `area`: float
- `height`: float
- `width`: float
- `rise_time`: float
- `fall_time`: float
- `center_time`: int
- `sample_start`: int
- `sample_end`: int
- `record_id`: int
- `is_single_record`: bool

#### `get_channel_waveform(merged_index, pad=30)`

获取单个通道的波形

**返回字段**：
- `merged_index`: int
- `board`: int
- `channel`: int
- `waveform`: np.ndarray（拼接后的完整波形）
- `time_ns`: np.ndarray（相对时间）
- `abs_time_ps`: np.ndarray（绝对时间）
- `dt`: int（采样间隔 ns）
- `is_single_record`: bool
- `segments`: list[dict]（原始片段，保留用于调试）

#### `get_peak_channel_data(peak_id, include_waveform=False, pad=30)`

主接口，获取 peak 的通道数据

**参数**：
- `include_waveform`: bool - 是否包含波形（默认 False）

**返回**：合并了特征和波形（如果请求）的通道列表

#### `get_sum_waveform(peak_id)`

获取 peak 的 sum waveform（从 peaklet_waveforms）

**返回字段**：
- `peak_id`: int
- `waveform`: np.ndarray
- `time_start`: int（ps）
- `time_end`: int（ps）
- `dt`: int（ns）
- `time_ns`: np.ndarray

#### `clear_waveform_cache(release_wave_pool=False)`

清理波形缓存

**参数**：
- `release_wave_pool`: bool - 是否释放 wave_pool

### 可视化方法

#### `plot(peak_id, pad=30, figsize=None, show_sum=True)`

绘制 peak 的所有通道波形

**特性**：
- 第一个子图：sum waveform（可选）
- 其余子图：各通道波形
- 自动时间对齐
- 显示特征信息（area, height, width）

#### `batch_plot(peak_ids, output_dir="output", pad=30, show_sum=True)`

批量绘制多个 peak

**功能**：
- 自动创建输出目录
- 保存为 PNG 文件
- 自动关闭图形释放内存

#### `plot_channel_comparison(peak_id, channel_selector=None, pad=30, figsize=(14, 8))`

在同一图上叠加显示多个通道

**参数**：
- `channel_selector`: callable - 通道筛选函数
  - 例如：`lambda ch: ch['area'] > 100`

#### `plot_sum_vs_channels(peak_id, pad=30, figsize=(14, 10))`

对比绘制 sum waveform 与各通道叠加

**布局**：
- 上图：sum waveform
- 下图：所有通道叠加

## 使用示例

### 基础使用

```python
from waveform_analysis.utils.peak_channel_accessor import PeakChannelAccessor

# 创建访问器
accessor = PeakChannelAccessor(context, run_id)

# 只访问特征（快速）
channels = accessor.get_peak_channels(peak_id=42)
for ch in channels:
    print(f"Channel {ch['channel']}: area={ch['area']:.1f}")

# 访问特征 + 波形
channels = accessor.get_peak_channel_data(peak_id=42, include_waveform=True)
for ch in channels:
    print(f"Channel {ch['channel']}: waveform shape={ch['waveform'].shape}")

# 获取 sum waveform
sum_data = accessor.get_sum_waveform(peak_id=42)
print(f"Sum waveform shape: {sum_data['waveform'].shape}")
```

### 可视化

```python
# 绘制单个 peak
fig, axes = accessor.plot(peak_id=42)

# 批量绘制
accessor.batch_plot([42, 43, 44], output_dir="output")

# 通道对比（只显示 area > 100 的通道）
fig, ax = accessor.plot_channel_comparison(
    peak_id=42,
    channel_selector=lambda ch: ch['area'] > 100
)

# Sum vs Channels 对比
fig, axes = accessor.plot_sum_vs_channels(peak_id=42)
```

### 内存管理

```python
# 清理波形缓存（保留 wave_pool）
accessor.clear_waveform_cache(release_wave_pool=False)

# 完全释放波形层（释放 wave_pool）
accessor.clear_waveform_cache(release_wave_pool=True)
```

## 性能对比

| 操作 | 旧方法 | 新方法 | 提升 |
|------|--------|--------|------|
| 加载特征 | 加载全部数据（含 wave_pool） | 只加载特征层 | ~100x |
| 查找 record | 布尔筛选 O(n) | 索引查找 O(1) | ~1000x |
| 批量访问 | 每次重新加载 | 预加载 + 缓存 | ~10x |

## 设计原则

1. **分层加载**：默认最小化内存占用
2. **索引优化**：避免高频大数组扫描
3. **统一接口**：数据访问和可视化集成
4. **保留信息**：跨 record 波形保留 segments
5. **缓存控制**：允许用户控制内存使用

## 文件位置

- **实现**：`waveform_analysis/utils/peak_channel_accessor.py`
- **示例**：`examples/demo_peak_channel_accessor.py`
- **文档**：`docs/peak_channel_accessor.md`

## 依赖

- **必需**：numpy
- **可选**：matplotlib（仅用于可视化方法）

如果调用可视化方法但未安装 matplotlib，会给出友好的错误提示：
```
ImportError: plot() requires matplotlib. Install it with: pip install matplotlib
```

## 与旧版本对比

### 旧版本（分离的 Plotter）

```python
accessor = PeakChannelAccessor(context, run_id)
plotter = PeakChannelPlotter(accessor)  # 需要两个对象

channels = accessor.get_peak_channels(peak_id=42)
plotter.plot(peak_id=42)
```

### 新版本（集成设计）

```python
accessor = PeakChannelAccessor(context, run_id)  # 一个对象

channels = accessor.get_peak_channels(peak_id=42)
accessor.plot(peak_id=42)  # 统一接口
```

## 未来扩展

可以考虑添加的功能：

1. **导出功能**：导出通道数据为 CSV/HDF5
2. **统计分析**：通道贡献度、主导通道分析
3. **交互式绘图**：使用 Plotly 支持缩放、悬停等
4. **并行处理**：批量处理时并行提取波形

但要保持核心原则：**Accessor 只负责数据访问和基础可视化，不混入复杂的分析逻辑**。
