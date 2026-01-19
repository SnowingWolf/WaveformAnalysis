**导航**: [文档中心](../../README.md) > [功能特性](../README.md) > [工具函数](README.md) > 事件筛选工具使用指南

---

# 事件筛选工具使用指南

> **适合人群**: 数据分析用户 | **阅读时间**: 15 分钟 | **难度**: ⭐⭐ 中级

本指南介绍如何使用 `event_filters` 模块进行事件筛选和属性提取。该模块提供了高效的、支持 Numba 加速的事件筛选功能，特别适合处理多通道事件数据。

---

## 📋 目录

1. [概述](#概述)
2. [快速开始](#快速开始)
3. [核心功能](#核心功能)
4. [使用示例](#使用示例)
5. [性能优化](#性能优化)
6. [API 参考](#api-参考)
7. [常见问题](#常见问题)

---

## 概述

`event_filters` 模块提供了三个主要功能：

1. **`filter_events_by_function`** - 通用的筛选函数，支持自定义筛选逻辑
2. **`filter_coincidence_events`** - 筛选同时包含所有指定通道的事件（Coincidence 筛选）
3. **`extract_channel_attributes`** - 从筛选后的事件中提取指定通道的属性值

### 核心特性

- ✅ **Numba 加速支持** - 自动检测并使用 Numba 加速（如果可用）
- ✅ **向量化优化** - 自动尝试向量化操作以提高性能
- ✅ **灵活筛选** - 支持自定义筛选函数
- ✅ **多通道支持** - 专门优化了多通道事件处理

---

## 快速开始

### 导入模块

```python
from waveform_analysis.utils.event_filters import (
    filter_events_by_function,
    filter_coincidence_events,
    extract_channel_attributes,
)
```

### 基本使用示例

```python
import pandas as pd
import numpy as np

# 假设你有一个包含事件数据的 DataFrame
# df_events 包含 'channels' 列（每个事件包含一个通道数组）
df_events = pd.DataFrame({
    'channels': [[2, 3], [2], [3], [2, 3, 4], [1, 2]],
    'charges': [[10.5, 12.3], [8.2], [9.1], [11.0, 12.5, 13.2], [7.5, 8.0]],
    'time': [100, 200, 300, 400, 500],
})

# 筛选同时包含通道 2 和 3 的事件
df_filtered = filter_coincidence_events(df_events, channels=[2, 3])
print(f"筛选后的事件数: {len(df_filtered)}")
# 输出: 筛选后的事件数: 2

# 提取通道 2 和 3 的电荷值
charges_dict = extract_channel_attributes(df_filtered, channels=[2, 3], attribute='charges')
print(f"通道 2 的电荷: {charges_dict[2]}")
print(f"通道 3 的电荷: {charges_dict[3]}")
```

---

## 核心功能

### 1. filter_events_by_function - 通用筛选函数

使用自定义函数对事件进行筛选，支持向量化优化。

#### 函数签名

```python
def filter_events_by_function(
    df_events: pd.DataFrame,
    filter_func: Callable,
    column: Optional[str] = None,
    use_vectorized: bool = True,
) -> pd.DataFrame:
```

#### 参数说明

- `df_events`: 事件 DataFrame
- `filter_func`: 筛选函数，可以是：
  - 接受 Series（整行）的函数：`lambda row: bool`
  - 接受特定列值的函数：`lambda value: bool`（需要指定 `column`）
- `column`: 可选，指定要操作的列名（用于向量化优化）
- `use_vectorized`: 是否尝试向量化优化（默认 `True`）

#### 使用示例

```python
# 示例 1: 筛选整行（基于多个列）
def filter_by_time_and_charge(row):
    return row['time'] > 200 and max(row['charges']) > 10.0

df_filtered = filter_events_by_function(
    df_events,
    filter_func=filter_by_time_and_charge
)

# 示例 2: 筛选特定列（向量化优化）
df_filtered = filter_events_by_function(
    df_events,
    filter_func=lambda time: time > 200,  # 只接受时间值
    column='time',
    use_vectorized=True  # 尝试向量化
)

# 示例 3: 筛选通道数量
df_filtered = filter_events_by_function(
    df_events,
    filter_func=lambda channels: len(channels) >= 2,
    column='channels'
)
```

---

### 2. filter_coincidence_events - Coincidence 筛选

筛选同时包含所有指定通道的事件。这是多通道事件分析中最常用的筛选方式。

#### 函数签名

```python
def filter_coincidence_events(
    df_events: pd.DataFrame,
    channels: List[int],
    use_vectorized: bool = True,
    use_numba: Optional[bool] = None,
) -> pd.DataFrame:
```

#### 参数说明

- `df_events`: 包含 `channels` 列的 DataFrame
- `channels`: 要筛选的通道列表，如 `[2, 3]`
- `use_vectorized`: 是否使用向量化优化（默认 `True`）
- `use_numba`: 是否使用 Numba 加速（默认 `None`，自动检测）

#### 使用示例

```python
# 筛选同时包含通道 2 和 3 的事件
df_coincidence = filter_coincidence_events(df_events, channels=[2, 3])

# 筛选同时包含通道 0, 1, 2 的事件
df_triple = filter_coincidence_events(df_events, channels=[0, 1, 2])

# 禁用 Numba 加速（如果遇到兼容性问题）
df_filtered = filter_coincidence_events(
    df_events,
    channels=[2, 3],
    use_numba=False
)

# 禁用向量化（使用通用函数版本）
df_filtered = filter_coincidence_events(
    df_events,
    channels=[2, 3],
    use_vectorized=False
)
```

#### 工作原理

函数会检查每个事件的 `channels` 列是否包含所有指定的通道：

```python
# 对于 channels=[2, 3]
# 事件 1: channels=[2, 3]     → ✅ 通过（包含 2 和 3）
# 事件 2: channels=[2]        → ❌ 不通过（缺少 3）
# 事件 3: channels=[2, 3, 4]  → ✅ 通过（包含 2 和 3）
# 事件 4: channels=[1, 2]    → ❌ 不通过（缺少 3）
```

---

### 3. extract_channel_attributes - 属性提取

从筛选后的事件中提取指定通道的指定属性值。

#### 函数签名

```python
def extract_channel_attributes(
    df_filtered: pd.DataFrame,
    channels: List[int],
    attribute: str = 'charges',
    use_numba: Optional[bool] = None,
) -> Dict[int, List]:
```

#### 参数说明

- `df_filtered`: 筛选后的事件 DataFrame
- `channels`: 要提取的通道列表，如 `[2, 3]`
- `attribute`: 要提取的属性名称，如 `'charges'`, `'peaks'`, `'timestamps'`
- `use_numba`: 是否使用 Numba 加速（默认 `None`，自动检测）

#### 返回值

返回字典格式：`{channel: [attribute_values]}`

#### 使用示例

```python
# 提取通道 2 和 3 的电荷值
charges_dict = extract_channel_attributes(
    df_filtered,
    channels=[2, 3],
    attribute='charges'
)
# 返回: {2: [10.5, 11.0], 3: [12.3, 12.5]}

# 提取峰值信息
peaks_dict = extract_channel_attributes(
    df_filtered,
    channels=[0, 1],
    attribute='peaks'
)

# 提取时间戳
timestamps_dict = extract_channel_attributes(
    df_filtered,
    channels=[2, 3],
    attribute='timestamps'
)
```

---

## 使用示例

### 完整工作流示例

```python
import pandas as pd
import numpy as np
from waveform_analysis.utils.event_filters import (
    filter_coincidence_events,
    extract_channel_attributes,
)

# 1. 准备数据（从 Context 或 Dataset 获取）
# 假设你已经有了 df_events
# df_events = ctx.get_data(run_name, "df_events")

# 2. 筛选 Coincidence 事件（通道 2 和 3 同时触发）
df_coincidence = filter_coincidence_events(
    df_events,
    channels=[2, 3],
    use_numba=True  # 启用 Numba 加速
)

print(f"Coincidence 事件数: {len(df_coincidence)}")

# 3. 提取各通道的电荷值
charges_dict = extract_channel_attributes(
    df_coincidence,
    channels=[2, 3],
    attribute='charges'
)

# 4. 分析数据
for ch, charges in charges_dict.items():
    print(f"通道 {ch}:")
    print(f"  事件数: {len(charges)}")
    print(f"  平均电荷: {np.mean(charges):.2f}")
    print(f"  最大电荷: {np.max(charges):.2f}")
```

### 与 Context 集成示例

```python
from waveform_analysis.core.context import Context
from waveform_analysis.utils.event_filters import (
    filter_coincidence_events,
    extract_channel_attributes,
)

# 创建 Context
ctx = Context(storage_dir="./cache")

# 注册插件并处理数据
# ... (注册插件代码) ...

# 获取事件数据
run_name = "my_run"
df_events = ctx.get_data(run_name, "df_events")

# 筛选 Coincidence 事件
df_coincidence = filter_coincidence_events(df_events, channels=[2, 3])

# 提取属性
charges = extract_channel_attributes(
    df_coincidence,
    channels=[2, 3],
    attribute='charges'
)

# 进一步分析...
```

### 自定义筛选示例

```python
from waveform_analysis.utils.event_filters import filter_events_by_function

# 筛选电荷总和大于阈值的多通道事件
def filter_by_total_charge(row):
    total_charge = sum(row['charges'])
    return total_charge > 50.0

df_high_charge = filter_events_by_function(
    df_events,
    filter_func=filter_by_total_charge
)

# 筛选时间窗口内的事件
df_time_window = filter_events_by_function(
    df_events,
    filter_func=lambda time: 1000 < time < 2000,
    column='time'
)

# 筛选通道数量
df_multi_channel = filter_events_by_function(
    df_events,
    filter_func=lambda channels: len(channels) >= 3,
    column='channels'
)
```

---

## 性能优化

### Numba 加速

模块会自动检测 Numba 是否可用，并在可用时自动启用加速。Numba 可以显著提升大规模数据处理的性能。

```python
# 自动检测（推荐）
df_filtered = filter_coincidence_events(df_events, channels=[2, 3])
# 如果 Numba 可用，会自动使用加速版本

# 手动控制
df_filtered = filter_coincidence_events(
    df_events,
    channels=[2, 3],
    use_numba=True  # 强制启用（如果 Numba 不可用会回退）
)
```

### 向量化优化

默认启用向量化优化，可以显著提升性能：

```python
# 向量化版本（默认，推荐）
df_filtered = filter_coincidence_events(
    df_events,
    channels=[2, 3],
    use_vectorized=True
)

# 如果遇到问题，可以禁用
df_filtered = filter_coincidence_events(
    df_events,
    channels=[2, 3],
    use_vectorized=False
)
```

### 性能对比

| 方法 | 速度 | 适用场景 |
|------|------|----------|
| Numba + 向量化 | 最快 | 大规模数据（推荐） |
| 向量化（无 Numba） | 快 | 中等规模数据 |
| 通用函数 | 较慢 | 小规模数据或复杂筛选 |

### 最佳实践

1. **优先使用 Numba 加速** - 如果安装了 Numba，性能提升明显
2. **使用向量化** - 对于简单筛选，向量化版本更快
3. **批量处理** - 一次性处理多个筛选条件，而不是多次调用
4. **预筛选数据** - 先使用简单条件筛选，再使用复杂条件

---

## API 参考

### filter_events_by_function

```python
filter_events_by_function(
    df_events: pd.DataFrame,
    filter_func: Callable,
    column: Optional[str] = None,
    use_vectorized: bool = True,
) -> pd.DataFrame
```

**功能**: 使用自定义函数筛选事件

**参数**:
- `df_events`: 事件 DataFrame
- `filter_func`: 筛选函数
- `column`: 可选，指定列名
- `use_vectorized`: 是否向量化

**返回**: 筛选后的 DataFrame

---

### filter_coincidence_events

```python
filter_coincidence_events(
    df_events: pd.DataFrame,
    channels: List[int],
    use_vectorized: bool = True,
    use_numba: Optional[bool] = None,
) -> pd.DataFrame
```

**功能**: 筛选同时包含所有指定通道的事件

**参数**:
- `df_events`: 包含 `channels` 列的 DataFrame
- `channels`: 通道列表
- `use_vectorized`: 是否向量化
- `use_numba`: 是否使用 Numba

**返回**: 筛选后的 DataFrame

---

### extract_channel_attributes

```python
extract_channel_attributes(
    df_filtered: pd.DataFrame,
    channels: List[int],
    attribute: str = 'charges',
    use_numba: Optional[bool] = None,
) -> Dict[int, List]
```

**功能**: 提取指定通道的属性值

**参数**:
- `df_filtered`: 筛选后的事件 DataFrame
- `channels`: 通道列表
- `attribute`: 属性名称
- `use_numba`: 是否使用 Numba

**返回**: `{channel: [values]}` 格式的字典

---

## 常见问题

### Q1: 如何检查 Numba 是否可用？

```python
from waveform_analysis.utils.event_filters import NUMBA_AVAILABLE
print(f"Numba 可用: {NUMBA_AVAILABLE}")
```

### Q2: 筛选函数返回什么类型？

所有筛选函数都返回 `pd.DataFrame`，包含筛选后的事件行。

### Q3: 如何处理不等长的通道数组？

模块已经优化处理不等长的通道数组。`channels` 列可以包含不同长度的数组，函数会自动处理。

### Q4: 性能不够快怎么办？

1. 确保安装了 Numba：`pip install numba`
2. 启用向量化：`use_vectorized=True`
3. 启用 Numba：`use_numba=True`
4. 考虑预筛选数据以减少处理量

### Q5: 可以筛选多个条件吗？

可以，使用 `filter_events_by_function` 组合多个条件：

```python
def complex_filter(row):
    return (
        len(row['channels']) >= 2 and
        max(row['charges']) > 10.0 and
        row['time'] > 1000
    )

df_filtered = filter_events_by_function(df_events, complex_filter)
```

### Q6: 如何提取多个属性？

多次调用 `extract_channel_attributes`：

```python
charges = extract_channel_attributes(df_filtered, channels=[2, 3], attribute='charges')
peaks = extract_channel_attributes(df_filtered, channels=[2, 3], attribute='peaks')
```

---

## 相关资源

- [数据处理指南](README.md) - 其他数据处理功能
- [性能优化指南](../performance/PERFORMANCE_OPTIMIZATION.md) - 性能优化技巧
- [API 参考](../../api/README.md) - 完整 API 文档

---

**快速链接**:
[数据处理指南](README.md) |
[性能优化](../performance/README.md) |
[API 参考](../../api/README.md)
