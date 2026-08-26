# Hit Threshold 查询使用指南

## 概述

推荐通过 `PeakChannelAccessor` 分析 peak、merged 和 `hit_threshold` 之间的关系。Accessor 负责按 `run_id` 延迟加载关系数据，并复用 `waveform_analysis.utils.query_helpers` 的 DataFrame 契约；只有需要批量复用已在内存中的数组时，才直接调用底层函数。

## 快速开始

### 基本用法

```python
from waveform_analysis.utils.peak_channel_accessor import PeakChannelAccessor

accessor = PeakChannelAccessor(ctx, run_id, lazy_load=True)
```

### 使用场景 1: 查询某个 peak 的所有 hit 数据

```python
# 查询 peak 123 的所有 hit 数据（自动计算时间间隔）
intervals = accessor.get_hits(peak_id=123)

# 查看结果
print(f"Peak 123 包含 {len(intervals)} 个 hits")
print(intervals.head())
```

### 使用场景 2: 绘制时间间隔直方图

```python
import matplotlib.pyplot as plt
import numpy as np

# 获取时间间隔数据（排除第一行的 NaN）
dt = intervals["dt_start_to_start_ns"].dropna()

# 绘制直方图
plt.figure(figsize=(10, 6))
plt.hist(dt, bins=np.linspace(0, dt.max(), 100))
plt.yscale("log")
plt.xlabel("hit_threshold interval within hit_merged (ns)")
plt.ylabel("counts")
plt.title(f"Hit Time Intervals for Peak {peak_id}")
plt.show()
```

### 使用场景 3: 只查询某个 merged 的 hit 数据

```python
# 查询 merged 456 的所有 hit 数据
df = accessor.get_merged_hits(merged_index=456)

print(df[["hit_index", "time_start", "dt_start_to_start_ns"]])
```

### 使用场景 4: 直接使用底层函数

如果已经持有完整的 NumPy 产物，或要预先构建映射以优化大批量查询，可以继续使用底层函数。它们是保留的稳定接口，也是 Accessor 返回契约的实现真源：

```python
from waveform_analysis.utils import (
    get_hits_for_peak,
    get_hits_for_merged,
    build_peak_to_merged_lookup,
    build_merged_to_hit_lookup,
)

# 构建完整的映射字典
peak_lookup = build_peak_to_merged_lookup(peaklet_components)
merged_lookup = build_merged_to_hit_lookup(hit_merged_components)

# 批量查询多个 peak
for peak_id in [100, 101, 102]:
    merged_indices = peak_lookup.get(peak_id, np.array([], dtype=np.int64))
    print(f"Peak {peak_id}: {len(merged_indices)} merged hits")

# 直接复用已加载数组，返回结构与 accessor.get_hits() 一致
intervals = get_hits_for_peak(
    peak_id=123,
    peaklet_components=peaklet_components,
    hit_merged_components=hit_merged_components,
    hit_threshold=hit_threshold,
)
```

## 返回的 DataFrame 结构

### `get_hits_for_peak` 返回的列

| 列名 | 类型 | 说明 |
|------|------|------|
| `peak_id` | int64 | peak 的 ID |
| `merged_index` | int64 | hit 所属的 merged_index |
| `hit_index` | int64 | hit 在 hit_threshold 数组中的索引 |
| `position` | int64 | 采样点位置 |
| `edge_start` | int32 | 起始边界（样本） |
| `edge_end` | int32 | 结束边界（样本） |
| `width` | float32 | 宽度（样本点数） |
| `dt` | int32 | 采样间隔（ns） |
| `timestamp` | int64 | position 的绝对时间戳（ps） |
| `board` | int16 | 板卡编号 |
| `channel` | int16 | 通道号 |
| `record_id` | int64 | 来源 record ID |
| `time_start` | int64 | 起始绝对时间（ps） |
| `time_end` | int64 | 结束绝对时间（ps） |
| `dt_start_to_start_ns` | float64 | 与前一个 hit 的 time_start 间隔（ns），第一行为 NaN |
| `dt_end_to_start_ns` | float64 | 与前一个 hit 的 time_end 间隔（ns），第一行为 NaN |

### `get_hits_for_merged` 返回的列

与 `get_hits_for_peak` 相同，但不包含 `peak_id` 和 `merged_index` 列。

## 函数 API 参考

### `get_merged_indices_for_peak(peak_id, peaklet_components)`

获取某个 peak 包含的所有 merged_index。

**参数**：
- `peak_id` (int): 目标 peak 的 ID
- `peaklet_components` (np.ndarray): peaklet_components 数组

**返回**：
- `np.ndarray`: merged_index 数组（int64）

---

### `get_hit_indices_for_merged(merged_index, hit_merged_components)`

获取某个 merged 包含的所有 hit_index。

**参数**：
- `merged_index` (int): 目标 merged 的索引
- `hit_merged_components` (np.ndarray): hit_merged_components 数组

**返回**：
- `np.ndarray`: hit_index 数组（int64）

---

### `get_hits_for_merged(merged_index, hit_merged_components, hit_threshold)`

获取某个 merged 的所有 hit 数据（带时间间隔计算）。

**参数**：
- `merged_index` (int): 目标 merged 的索引
- `hit_merged_components` (np.ndarray): hit_merged_components 数组
- `hit_threshold` (np.ndarray): hit_threshold 完整数组

**返回**：
- `pd.DataFrame`: 包含该 merged 的所有 hit 数据，按 time_start 排序

---

### `get_hits_for_peak(peak_id, peaklet_components, hit_merged_components, hit_threshold)`

获取某个 peak 的所有 hit 数据（带 merged_index 和时间间隔）。

**参数**：
- `peak_id` (int): 目标 peak 的 ID
- `peaklet_components` (np.ndarray): peaklet_components 数组
- `hit_merged_components` (np.ndarray): hit_merged_components 数组
- `hit_threshold` (np.ndarray): hit_threshold 完整数组

**返回**：
- `pd.DataFrame`: 包含该 peak 的所有 hit 数据，按 time_start 排序

---

### `build_peak_to_merged_lookup(peaklet_components)`

构建 peak_id → merged_indices 完整映射（批量查询优化）。

**参数**：
- `peaklet_components` (np.ndarray): peaklet_components 数组

**返回**：
- `dict[int, np.ndarray]`: 字典，键为 peak_id，值为对应的 merged_index 数组

---

### `build_merged_to_hit_lookup(hit_merged_components)`

构建 merged_index → hit_indices 完整映射（批量查询优化）。

**参数**：
- `hit_merged_components` (np.ndarray): hit_merged_components 数组

**返回**：
- `dict[int, np.ndarray]`: 字典，键为 merged_index，值为对应的 hit_index 数组

## 时间计算说明

### 绝对时间计算

从 `hit_threshold` 数据中计算绝对时间：

```python
# edge_start/edge_end 是相对于 position 的样本偏移
# timestamp 是 position 对应的绝对时间（ps）
# dt 是采样间隔（ns）

time_start_ps = timestamp + (edge_start - position) * dt * 1000  # 转换 ns 到 ps
time_end_ps = timestamp + (edge_end - position) * dt * 1000
```

### 时间间隔计算

- `dt_start_to_start_ns`: 当前 hit 的 `time_start` 与前一个 hit 的 `time_start` 之间的间隔（ns）
- `dt_end_to_start_ns`: 当前 hit 的 `time_start` 与前一个 hit 的 `time_end` 之间的间隔（ns）

**注意**：第一行的时间间隔为 `NaN`（因为没有前一个 hit）。

## 常见问题

### Q: Accessor 会加载波形吗？

**A**: 不会。`get_hits()` 和 `get_merged_hits()` 使用独立的 hit 查询层，只读取 `peaklet_components`、`hit_merged_components` 与 `hit_threshold`。它们不读取 `peaklet_channels`、`records` 或 wave pool。构造时使用 `lazy_load=True`，还可以避免在首次 hit 查询前预加载通道特征层。

### Q: 如何直接获取 peaklet_components 等数据？

**A**: 仅在确实需要调用底层函数或进行批量数组计算时，从 Context 获取：

```python
peaklet_components = ctx.get_data(run_id, "peaklet_components")
hit_merged_components = ctx.get_data(run_id, "hit_merged_components")
hit_threshold = ctx.get_data(run_id, "hit_threshold")
```

### Q: 为什么第一行的时间间隔是 NaN？

**A**: 因为第一个 hit 没有前一个 hit 作为参考，所以时间间隔无法计算。在绘制直方图时，可以使用 `.dropna()` 排除这些值：

```python
dt = intervals["dt_start_to_start_ns"].dropna()
```

### Q: 如果 peak_id 不存在会怎样？

**A**: 函数会返回空的 DataFrame，但保留列结构。你可以检查长度来判断：

```python
intervals = get_hits_for_peak(peak_id, ...)
if len(intervals) == 0:
    print(f"Peak {peak_id} 不存在或没有 hits")
```

### Q: 时间间隔的单位是什么？

**A**: `dt_start_to_start_ns` 和 `dt_end_to_start_ns` 的单位是纳秒（ns）。原始的 `time_start` 和 `time_end` 单位是皮秒（ps）。

## 相关文档

- [PeakChannelAccessor API](../api/peak_channel_accessor.md)
- [DAQ Analyzer 使用指南](../features/utils/DAQ_ANALYZER_GUIDE.md)
- [插件参考文档](../plugins/reference/builtin/auto/INDEX.md)

## 版本历史

- **v1.0.0** (2026-06-17): 初始版本，提供基础查询和时间间隔计算功能
