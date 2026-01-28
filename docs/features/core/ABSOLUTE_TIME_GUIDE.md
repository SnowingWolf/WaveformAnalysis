**导航**: [文档中心](../../README.md) > [功能特性](../README.md) > [core](README.md) > 绝对时间查询指南

# 绝对时间查询指南

本指南介绍如何在 WaveformAnalysis 中使用绝对时间（datetime）进行数据查询。

## 概述

WaveformAnalysis 的时间戳系统默认使用相对整数时间（皮秒或纳秒）。从版本 2026-01 开始，新增了**绝对时间**支持，允许用户：

- 使用 Python `datetime` 对象进行数据查询
- 自动从 DAQ 数据文件提取时间基准（epoch）
- 在相对时间和绝对时间之间双向转换

## 快速开始

### 1. 设置 Epoch

有两种方式设置 epoch：

#### 手动设置

```python
from datetime import datetime, timezone
from waveform_analysis.core.context import Context

ctx = Context()

# 方法 1: 使用 datetime 对象
epoch = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
ctx.set_epoch('run_001', epoch)

# 方法 2: 使用 Unix 时间戳
ctx.set_epoch('run_001', 1704110400.0)

# 方法 3: 使用 ISO 8601 字符串
ctx.set_epoch('run_001', "2024-01-01T12:00:00Z")
```

#### 自动提取

```python
# 从数据文件名自动提取
ctx.auto_extract_epoch('run_001')

# 指定提取策略
ctx.auto_extract_epoch('run_001', strategy='filename')  # 从文件名
ctx.auto_extract_epoch('run_001', strategy='csv_header')  # 从 CSV 头部
```

### 2. 使用绝对时间查询

```python
from datetime import datetime, timezone

# 定义时间范围
start = datetime(2024, 1, 1, 12, 0, 10, tzinfo=timezone.utc)
end = datetime(2024, 1, 1, 12, 0, 20, tzinfo=timezone.utc)

# 查询数据
data = ctx.get_data_time_range_absolute(
    'run_001',
    'basic_features',
    start_dt=start,
    end_dt=end
)
```

### 3. 查看 Epoch 信息

```python
epoch_info = ctx.get_epoch('run_001')
if epoch_info:
    print(f"Epoch: {epoch_info.epoch_datetime}")
    print(f"来源: {epoch_info.epoch_source}")
    print(f"时间单位: {epoch_info.time_unit.value}")
```

## 核心概念

### EpochInfo

`EpochInfo` 是 epoch 元数据的数据类，包含：

| 字段 | 类型 | 描述 |
|------|------|------|
| `epoch_timestamp` | float | Unix 时间戳（秒） |
| `epoch_datetime` | datetime | Python datetime 对象（带时区） |
| `epoch_source` | str | 来源："filename", "csv_header", "first_event", "manual" |
| `time_unit` | TimestampUnit | 相对时间单位（默认 ns） |

### TimeConverter

`TimeConverter` 提供相对时间和绝对时间之间的双向转换：

```python
from waveform_analysis.core.foundation.time_conversion import TimeConverter

converter = TimeConverter(epoch_info)

# 相对时间 → 绝对时间
dt = converter.relative_to_absolute(1_000_000_000)  # 1秒

# 绝对时间 → 相对时间
ns = converter.absolute_to_relative(dt)
```

### Epoch 提取策略

| 策略 | 描述 | 优先级 |
|------|------|--------|
| `filename` | 从文件名解析时间戳 | 最高（最可靠） |
| `csv_header` | 从 CSV 头部注释提取 | 中 |
| `first_event` | 从首个事件推导 | 最低（不太可靠） |
| `auto` | 按优先级自动尝试 | 默认 |

### 支持的文件名格式

以下文件名格式会被自动识别：

```
data_2024-01-01_12-00-00.csv       # ISO 8601 格式
run_20240101120000_CH0.csv         # 紧凑格式
data_2024_01_01_120000.csv         # 下划线分隔
acquisition_2024-01-01.csv         # 仅日期（默认 00:00:00）
```

## 配置选项

可以通过 Context 配置控制 epoch 行为：

```python
ctx = Context(config={
    # 是否自动提取 epoch（默认 True）
    'auto_extract_epoch': True,

    # 默认提取策略（默认 "auto"）
    'epoch_extraction_strategy': 'auto',

    # 自定义文件名模式（可选）
    'epoch_filename_patterns': [
        (r'custom_(\d{4})(\d{2})(\d{2})', '%Y%m%d'),
    ],
})
```

## 高级用法

### 多通道数据查询

```python
# 查询所有通道
st_waveforms = ctx.get_data_time_range_absolute(
    'run_001',
    'st_waveforms',
    start_dt=start,
    end_dt=end
)
# 返回 List[np.ndarray]

# 查询特定通道
ch0_data = ctx.get_data_time_range_absolute(
    'run_001',
    'st_waveforms',
    start_dt=start,
    end_dt=end,
    channel=0
)
# 返回 np.ndarray
```

### 向量化转换

对于大规模数据，TimeConverter 支持向量化操作：

```python
import numpy as np

# 批量转换相对时间
relative_times = np.array([0, 1e9, 2e9])  # 纳秒
absolute_times = converter.relative_to_absolute(relative_times)
# 返回 datetime64[ns] 数组

# 批量转换绝对时间
dts = np.array(['2024-01-01T12:00:00', '2024-01-01T12:00:01'], dtype='datetime64[s]')
relative_times = converter.absolute_to_relative(dts)
# 返回 int64 数组
```

### TimeIndex 绝对时间查询

时间索引也支持绝对时间查询：

```python
# 构建索引（epoch 会自动传递）
ctx.build_time_index('run_001', 'basic_features')

# 获取索引的绝对时间范围
index = ctx._time_query_engine.get_index('run_001', 'basic_features')
time_range = index.get_time_range_absolute()
if time_range:
    min_dt, max_dt = time_range
    print(f"数据时间范围: {min_dt} 到 {max_dt}")
```

## 时区处理

### 最佳实践

1. **始终使用 UTC**：建议使用 UTC 时区存储和查询，避免夏令时等问题
2. **显式指定时区**：创建 datetime 时始终指定 `tzinfo`
3. **本地时间转换**：如需显示本地时间，在最后一步转换

```python
from datetime import timezone

# 推荐：使用 UTC
dt_utc = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

# 如果需要本地时间显示
import zoneinfo
local_tz = zoneinfo.ZoneInfo("Asia/Shanghai")
dt_local = dt_utc.astimezone(local_tz)
```

### 无时区 datetime

如果传入无时区的 datetime，系统会假定为 UTC：

```python
# 这两个是等价的
ctx.set_epoch('run_001', datetime(2024, 1, 1, 12, 0, 0))
ctx.set_epoch('run_001', datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc))
```

## 向后兼容

现有的相对时间查询继续工作：

```python
# 相对时间查询（纳秒）
data = ctx.get_data_time_range(
    'run_001',
    'basic_features',
    start_time=10_000_000_000,  # 10秒
    end_time=20_000_000_000     # 20秒
)
```

## 常见问题

### Q: 无法提取 epoch

```
ValueError: 无法从文件中提取 epoch
```

**解决方案**：
1. 确保数据文件名包含时间戳信息
2. 或手动设置 epoch：`ctx.set_epoch('run_001', epoch)`

### Q: 时间精度问题

相对时间使用 int64 存储，精度取决于时间单位：

| 单位 | 最大时间范围 | 精度 |
|------|------------|------|
| ps（皮秒） | ~292 年 | 1e-12 秒 |
| ns（纳秒） | ~292 年 | 1e-9 秒 |
| μs（微秒） | ~292000 年 | 1e-6 秒 |

### Q: 如何验证 epoch 是否正确

```python
epoch_info = ctx.get_epoch('run_001')
print(epoch_info)  # 显示 epoch 详情

# 获取数据的绝对时间范围
index = ctx._time_query_engine.get_index('run_001', 'basic_features')
time_range = index.get_time_range_absolute()
print(f"数据时间范围: {time_range}")
```

## API 参考

### Context 方法

| 方法 | 描述 |
|------|------|
| `set_epoch(run_id, epoch, time_unit)` | 手动设置 epoch |
| `get_epoch(run_id)` | 获取 epoch 元数据 |
| `auto_extract_epoch(run_id, strategy)` | 自动提取 epoch |
| `get_data_time_range_absolute(...)` | 使用 datetime 查询数据 |

### TimeIndex 方法

| 方法 | 描述 |
|------|------|
| `query_range_absolute(start_dt, end_dt)` | 绝对时间范围查询 |
| `query_point_absolute(dt)` | 绝对时间点查询 |
| `get_time_range_absolute()` | 获取索引的绝对时间范围 |
