# 时间字段统一方案

**导航**: [文档中心](../../README.md) > [功能特性](../README.md) > [core](README.md) > 时间字段统一方案

> 阅读时间: 10 分钟 | 难度: ⭐⭐ 进阶

本文档说明 WaveformAnalysis 中时间字段的统一设计方案，包括 `time` 和 `timestamp` 字段的定义、用途和实现细节。

---

## 📋 目录

1. [概述](#概述)
2. [设计目标](#设计目标)
3. [字段定义](#字段定义)
4. [实现细节](#实现细节)
5. [使用示例](#使用示例)
6. [向后兼容性](#向后兼容性)
7. [常见问题](#常见问题)

---

## 概述

### 为什么需要时间字段统一？

在波形分析中，时间信息至关重要。原有设计中只有 `timestamp` 字段（ADC 原始时间戳，皮秒单位），存在以下问题：

- **相对时间**: `timestamp` 是相对于某个未知起点的时间，无法直接对应到真实物理时间
- **跨运行比较困难**: 不同运行的数据无法基于绝对时间进行比较和关联
- **时间范围查询不便**: 无法使用真实时间（如 "2024-01-01 12:00:00"）进行查询

### 解决方案

引入 `time` 字段作为**绝对系统时间**（Unix 时间戳，纳秒单位），同时保留 `timestamp` 字段作为 ADC 原始时间戳。

---

## 设计目标

1. **time = 绝对系统时间**（Unix 时间戳，纳秒 ns）
2. **timestamp = ADC 原始时间戳**（皮秒 ps，统一为 ps）
3. **自动获取 epoch**: 从文件创建时间自动获取时间基准
4. **向后兼容**: 无 epoch 时降级为相对时间

---

## 字段定义

### RECORD_DTYPE 结构

```python
RECORD_DTYPE = [
    ("time", "i8"),        # 绝对系统时间 (Unix ns)
    ("baseline", "f8"),    # 基线值
    ("timestamp", "i8"),   # ADC 原始时间戳 (ps)
    ("event_length", "i8"),
    ("channel", "i2"),
    ("wave", "f4", (wave_length,)),
]
```

### 字段说明

| 字段 | 类型 | 单位 | 说明 |
|------|------|------|------|
| `time` | int64 | 纳秒 (ns) | 绝对系统时间，Unix 时间戳 |
| `timestamp` | int64 | 皮秒 (ps) | ADC 原始时间戳，统一为 ps |

`st_waveforms` 内的 `timestamp` 会按 `FormatSpec.timestamp_unit` 统一转换为 ps。

### 时间转换公式

```python
# time = epoch_ns + timestamp_ps // 1000
time = epoch_ns + timestamp // 1000
```

其中：
- `epoch_ns`: 文件创建时间（Unix 时间戳，纳秒）
- `timestamp`: ADC 时间戳（皮秒）
- `time`: 绝对系统时间（纳秒）

---

## 实现细节

### 1. DAQAdapter 新增方法

`get_file_epoch()` 方法从文件创建时间获取 epoch：

```python
def get_file_epoch(self, file_path: Path) -> int:
    """获取文件创建时间作为 epoch (纳秒)"""
    stat = file_path.stat()
    # 优先使用 st_birthtime (macOS)，否则用 st_mtime
    ctime = getattr(stat, 'st_birthtime', stat.st_mtime)
    return int(ctime * 1e9)  # 秒 → 纳秒
```

### 2. WaveformStructConfig 新增属性

```python
@dataclass
class WaveformStructConfig:
    format_spec: "FormatSpec"
    wave_length: Optional[int] = None
    epoch_ns: Optional[int] = None  # 新增：文件创建时间 (Unix ns)
```

### 3. WaveformStruct 填充 time 字段

在 `_structure_waveform()` 方法中：

```python
# 填充 time 字段（绝对系统时间 ns）
if self.config.epoch_ns is not None:
    # time = epoch_ns + timestamp_ps // 1000
    waveform_structured["time"] = self.config.epoch_ns + timestamps // 1000
else:
    # 默认：相对时间 ns（向后兼容）
    waveform_structured["time"] = timestamps // 1000
```

### 4. StWaveformsPlugin 传递 epoch

```python
# 获取 epoch（从 DAQ 适配器或文件创建时间）
epoch_ns = None
if daq_adapter:
    adapter = get_adapter(daq_adapter)
    raw_files = context.get_data(run_id, "raw_files")
    
    # 从第一个通道的第一个文件获取 epoch
    if raw_files and raw_files[0]:
        first_file = Path(raw_files[0][0])
        epoch_ns = adapter.get_file_epoch(first_file)

# 创建配置时传递 epoch
config = WaveformStructConfig.from_adapter(daq_adapter)
config.epoch_ns = epoch_ns
waveform_struct = WaveformStruct(waveforms, config=config)
```

---

## 使用示例

### 基本使用（自动获取 epoch）

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import (
    RawFilesPlugin, WaveformsPlugin, StWaveformsPlugin
)

# 初始化并设置 DAQ 适配器
ctx = Context(config={"data_root": "DAQ", "n_channels": 2})
ctx.register(RawFilesPlugin())
ctx.register(WaveformsPlugin())
ctx.register(StWaveformsPlugin())

# 设置适配器（自动获取 epoch）
ctx.set_config({'daq_adapter': 'vx2730'})

# 获取数据
st_waveforms = ctx.get_data('run_001', 'st_waveforms')

# 查看时间字段
print(f"time (绝对时间 ns): {st_waveforms[0]['time'][0]}")
print(f"timestamp (ADC ps): {st_waveforms[0]['timestamp'][0]}")
```

### 验证时间字段

```python
# 检查 dtype
assert "time" in st_waveforms[0].dtype.names
assert "timestamp" in st_waveforms[0].dtype.names

# 验证时间值
print(f"time[0]: {st_waveforms[0]['time'][0]}")        # Unix ns
print(f"timestamp[0]: {st_waveforms[0]['timestamp'][0]}")  # ADC ps

# 转换为人类可读时间
from datetime import datetime
time_ns = st_waveforms[0]['time'][0]
dt = datetime.fromtimestamp(time_ns / 1e9)
print(f"绝对时间: {dt}")
```

### 时间范围查询

```python
# chunk.py 和 query.py 会自动使用 time 字段
from waveform_analysis.core.processing.chunk import Chunk

# 创建 chunk（自动使用 time 字段）
chunk = Chunk(
    st_waveforms[0], 
    start=st_waveforms[0]['time'].min(), 
    end=st_waveforms[0]['time'].max()
)
```

---

## 向后兼容性

### 无 epoch 时的行为

如果未设置 `daq_adapter` 或无法获取 epoch，系统会降级为相对时间模式：

```python
# 无 epoch 时
time = timestamp // 1000  # 相对时间 ns
```

### 旧缓存失效

由于 `RECORD_DTYPE` 结构变化，旧缓存会自动失效并重新计算：

- dtype 变化触发 lineage hash 变化
- Context 自动检测并重新计算数据
- 无需手动清理缓存

### 自动生效的模块

以下模块对时间字段的处理原则如下：

- `chunk.py`: `_resolve_time_field()` 优先使用 `time`
- `streaming.py`: `_pick_time_field()` 优先使用 `timestamp`（ps）
- `query.py`: 时间范围查询默认使用 `time`（可通过 `time_field` 覆盖）

---

## 常见问题

### Q1: time 和 timestamp 有什么区别？

- **time**: 绝对系统时间（Unix 时间戳，纳秒），可以对应到真实物理时间
- **timestamp**: ADC 原始时间戳（皮秒，统一为 ps），相对于某个未知起点

### Q2: 如何获取 epoch？

epoch 从文件创建时间自动获取：
- macOS: 使用 `st_birthtime`（文件创建时间）
- Linux/Windows: 使用 `st_mtime`（文件修改时间）

### Q3: 如果没有 epoch 会怎样？

系统会降级为相对时间模式：`time = timestamp // 1000`（纳秒）

### Q4: 旧数据需要重新处理吗？

是的，由于 dtype 变化，旧缓存会自动失效。系统会自动重新计算数据。

### Q5: 如何验证 time 字段是否正确？

```python
# 检查 time 是否为合理的 Unix 时间戳
from datetime import datetime
time_ns = st_waveforms[0]['time'][0]
dt = datetime.fromtimestamp(time_ns / 1e9)
print(f"时间: {dt}")  # 应该是合理的日期时间
```

---

## 相关文档

- [DAQ 适配器指南](DAQ_ADAPTER_GUIDE.md)
- [绝对时间查询指南](ABSOLUTE_TIME_GUIDE.md)
- [架构设计文档](../../architecture/ARCHITECTURE.md)

---

**最后更新**: 2026-01-22
