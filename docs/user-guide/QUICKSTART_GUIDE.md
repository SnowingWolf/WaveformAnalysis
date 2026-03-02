# 快速开始指南

**导航**: [文档中心](../README.md) > [用户指南](README.md) > 快速开始指南

本文档帮助你快速上手 WaveformAnalysis。[^source]

---

## 📋 目录

1. [5 分钟上手](#5-分钟上手)
2. [目录结构](#目录结构)
3. [最小代码](#最小代码)
4. [配置说明](#配置说明)
5. [输出产物](#输出产物)
6. [场景 1: 基础分析流程](#场景-1-基础分析流程)
7. [场景 2: 批量处理](#场景-2-批量处理)
8. [场景 3: 流式处理](#场景-3-流式处理)
9. [场景 4: 使用自定义 DAQ 格式](#场景-4-使用自定义-daq-格式)
10. [快速参考卡](#快速参考卡)

---

## 5 分钟上手

> **只看这一节就能跑起来**

### 安装

```bash
# 方式 1: 使用安装脚本（推荐）
./install.sh

# 方式 2: 手动安装
pip install -e .

# 方式 3: 带开发依赖
pip install -e ".[dev]"
```

### 核心概念

| 概念 | 说明 |
|------|------|
| **Context** | 插件系统调度器，管理依赖、配置、缓存 |
| **Plugin** | 数据处理单元（RawFiles → Waveforms → Features） |
| **Lineage** | 自动血缘追踪，确保缓存一致性 |

推荐使用 **Context** API 进行数据处理。

---

## 目录结构

WaveformAnalysis 期望的 DAQ 数据目录结构：

```
DAQ/                          # data_root（可配置）
├── run_001/                  # run_id
│   └── RAW/                  # 原始数据子目录
│       ├── DataR_CH6.CSV     # 通道 6 数据文件
│       ├── DataR_CH7.CSV     # 通道 7 数据文件
│       └── ...
├── run_002/
│   └── RAW/
│       └── ...
└── run_003/
    └── RAW/
        └── ...
```

**说明**：
- `DAQ/` 是数据根目录，通过 `data_root` 配置
- `run_001/` 等是运行目录，作为 `run_id` 传入
- `RAW/` 是原始数据子目录（VX2730 默认布局）
- `*CH*.CSV` 是波形数据文件，通道号从文件名提取

---

## 最小代码

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins import profiles

# 1. 创建 Context
ctx = Context(storage_dir='./cache')

# 2. 注册标准插件
ctx.register(*profiles.cpu_default())

# 3. 最小配置（只需 3 项）
ctx.set_config({
    'data_root': 'DAQ',           # 数据根目录
    'daq_adapter': 'vx2730',      # DAQ 适配器
    'threshold': 15.0,            # 信号阈值（可选）
})

# 4. 获取数据
run_id = 'run_001'
basic_features = ctx.get_data(run_id, 'basic_features')

# 5. 使用结果
channels = sorted(set(basic_features['channel']))
for ch in channels:
    ch_data = basic_features[basic_features['channel'] == ch]
    print(f"通道 {ch}: {len(ch_data)} 个事件")
    print(f"  height: {ch_data['height'][:3]}...")
    print(f"  amp:    {ch_data['amp'][:3]}...")
    print(f"  area:   {ch_data['area'][:3]}...")
```

**English**:

```python
basic_features = ctx.get_data(run_id, 'basic_features')

channels = sorted(set(basic_features['channel']))
for ch in channels:
    ch_data = basic_features[basic_features['channel'] == ch]
    print(f"Channel {ch}: {len(ch_data)} events")
    print(f"  height: {ch_data['height'][:3]}...")
    print(f"  amp:    {ch_data['amp'][:3]}...")
    print(f"  area:   {ch_data['area'][:3]}...")
```

---

## 配置说明

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `data_root` | str | `"DAQ"` | 数据根目录路径 |
| `daq_adapter` | str | `"vx2730"` | DAQ 适配器名称 |
| `threshold` | float | `10.0` | Hit 检测阈值 |

**内置 DAQ 适配器**：
- `vx2730` - CAEN VX2730 数字化仪（CSV 格式）
- `v1725` - CAEN V1725 数字化仪（二进制格式）

---

## 输出产物

### basic_features 结构

`basic_features` 是单个结构化数组，通过 `channel` 字段区分通道：

```python
# 数据结构
basic_features: np.ndarray

# 每个通道的 dtype
dtype = [
    ('height', 'f4'),     # 脉冲高度 (baseline - min)
    ('amp', 'f4'),        # 峰峰值振幅 (max - min)
    ('area', 'f4'),       # 波形面积 (积分)
    ('timestamp', 'i8'),  # ADC 时间戳 (ps)
    ('channel', 'i2'),    # 物理通道号
]

```

**字段说明**：

| 字段 | 类型 | 单位 | 计算方式 |
|------|------|------|----------|
| `height` | float32 | ADC counts | `baseline - min(wave)` |
| `amp` | float32 | ADC counts | `max(wave) - min(wave)` |
| `area` | float32 | ADC counts × samples | `sum(baseline - wave)` |

**English**:

`basic_features` is a single structured array. Field definitions:

| Field | Type | Unit | Formula |
|------|------|------|---------|
| `height` | float32 | ADC counts | `baseline - min(wave)` |
| `amp` | float32 | ADC counts | `max(wave) - min(wave)` |
| `area` | float32 | ADC counts × samples | `sum(baseline - wave)` |

### 访问示例

```python
# 获取所有通道的 height
all_heights = basic_features['height']

# 获取通道 0 的数据
ch0 = basic_features[basic_features['channel'] == 0]
ch0_heights = ch0['height']
ch0_amps = ch0['amp']
ch0_areas = ch0['area']

# 统计
print(f"通道 0 平均高度: {ch0_heights.mean():.2f}")
print(f"通道 0 平均振幅: {ch0_amps.mean():.2f}")
print(f"通道 0 平均面积: {ch0_areas.mean():.2f}")
```

**English**:

```python
all_heights = basic_features['height']

ch0 = basic_features[basic_features['channel'] == 0]
ch0_heights = ch0['height']
ch0_amps = ch0['amp']
ch0_areas = ch0['area']

print(f"Channel 0 mean height: {ch0_heights.mean():.2f}")
print(f"Channel 0 mean amplitude: {ch0_amps.mean():.2f}")
print(f"Channel 0 mean area: {ch0_areas.mean():.2f}")
```

### 导出为 CSV

```python
import pandas as pd

# 转换为 DataFrame
rows = []
for record in basic_features:
    rows.append({
        'channel': int(record['channel']),
        'height': float(record['height']),
        'amp': float(record['amp']),
        'area': float(record['area']),
    })

df = pd.DataFrame(rows)
df.to_csv('basic_features.csv', index=False)
```

**English**:

```python
import pandas as pd

rows = []
for record in basic_features:
    rows.append({
        'channel': int(record['channel']),
        'height': float(record['height']),
        'amp': float(record['amp']),
        'area': float(record['area']),
    })

df = pd.DataFrame(rows)
df.to_csv('basic_features.csv', index=False)
```

**导出文件样例** (`basic_features.csv`)：

```csv
channel,height,amp,area
0,125.3,210.4,4521.7
0,98.7,175.2,3892.1
0,142.5,230.1,5103.4
1,87.2,160.8,3245.8
1,156.8,245.7,5678.2
...
```

**English**:

```csv
channel,height,amp,area
0,125.3,210.4,4521.7
0,98.7,175.2,3892.1
0,142.5,230.1,5103.4
1,87.2,160.8,3245.8
1,156.8,245.7,5678.2
...
```

### 数据流水线

```
raw_files → waveforms → st_waveforms → basic_features
    │           │            │              │
    │           │            │              └─ height/amp/area 特征
    │           │            └─ 结构化数组 (timestamp, baseline, wave)
    │           └─ 原始波形数据 (2D numpy array)
    └─ 文件路径列表
```

**English**: `basic_features` provides height/amp/area features on top of structured waveforms.

**可视化血缘图**：

```python
ctx.plot_lineage('basic_features', kind='labview')
```

## 场景 1: 基础分析流程

推荐新手使用，使用 Context API 进行标准分析。

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""基础波形分析"""

from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins import profiles

def main():
    # 1. 初始化 Context
    ctx = Context(storage_dir='./strax_data')
    ctx.register(*profiles.cpu_default())

    # 2. 设置配置
    ctx.set_config({
        'data_root': 'DAQ',
        'daq_adapter': 'vx2730',
        'threshold': 15.0,
    })

    # 3. 获取数据（自动触发依赖链）
    run_id = 'run_001'
    print(f"Processing run: {run_id}")
    basic_features = ctx.get_data(run_id, 'basic_features')
    ch0 = basic_features[basic_features['channel'] == 0]
    heights = ch0['height']
    amps = ch0['amp']
    areas = ch0['area']
    print(f"Found {len(ch0)} events in channel 0")

    # 4. 可视化血缘图（可选）
    ctx.plot_lineage('basic_features', kind='labview')

    return ch0

if __name__ == '__main__':
    result = main()
    print(f"Analysis complete. Events: {len(result)}")
```

**English**: `basic_features` is a single structured array. Filter by `channel` for per-channel analysis.

数据流：`raw_files → waveforms → st_waveforms → basic_features`

### 说明

| 步骤 | 说明 |
|------|------|
| `Context(storage_dir=...)` | 创建 Context，指定缓存目录 |
| `ctx.register(...)` | 注册标准插件集 |
| `ctx.set_config(...)` | 设置全局配置 |
| `ctx.get_data(run_id, name)` | 获取数据，自动触发依赖链 |

### 预期

- **缓存位置**: `./strax_data/`
- **输出**: NumPy 结构化数组

---

## 场景 2: 批量处理

处理多个 run，并行处理多个数据集。

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.data.export import BatchProcessor
from waveform_analysis.core.plugins import profiles

# 初始化
ctx = Context(storage_dir='./strax_data')
ctx.register(*profiles.cpu_default())
ctx.set_config({'data_root': 'DAQ', 'daq_adapter': 'vx2730'})

# 批量处理
processor = BatchProcessor(ctx)
results = processor.process_runs(
    run_ids=['run_001', 'run_002', 'run_003'],
    data_name='basic_features',
    max_workers=4,
    show_progress=True,
    on_error='continue'  # 'continue', 'stop', 'raise'
)

# 访问结果
for run_id, data in results['results'].items():
    print(f"{run_id}: {len(data)} events")

# 检查错误
if results['errors']:
    print(f"Errors: {results['errors']}")
```

## 场景 3: 流式处理

处理大数据，分块处理，内存友好。

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.core.streaming import get_streaming_context
from waveform_analysis.core.plugins import profiles

# 初始化
ctx = Context(storage_dir='./strax_data')
ctx.register(*profiles.cpu_default())
ctx.set_config({'data_root': 'DAQ', 'daq_adapter': 'vx2730'})

# 创建流式上下文
stream_ctx = get_streaming_context(ctx, run_id='run_001', chunk_size=50000)

# 分块处理
for chunk in stream_ctx.get_stream('st_waveforms'):
    # 处理每个数据块
    handle_chunk(chunk)
    print(f"Processed chunk: {chunk.start} - {chunk.end}")
```

## 场景 4: 使用自定义 DAQ 格式

### 使用内置适配器（推荐）

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import (
    RawFilesPlugin, WaveformsPlugin
)

# 初始化 Context
ctx = Context(config={"data_root": "DAQ", "daq_adapter": "vx2730"})

# 注册插件
ctx.register(RawFilesPlugin())
ctx.register(WaveformsPlugin())

# 获取数据（自动使用配置的适配器）
st_waveforms = ctx.get_data('run_001', 'st_waveforms')
print(f"Loaded {len(st_waveforms)} channels")
```

### 注册自定义适配器

```python
from waveform_analysis.utils.formats import register_adapter, DAQAdapter
from waveform_analysis.utils.formats.base import FormatSpec, ColumnMapping, TimestampUnit
from waveform_analysis.utils.formats.directory import DirectoryLayout

# 定义格式规范
my_spec = FormatSpec(
    name="my_daq",
    columns=ColumnMapping(board=0, channel=1, timestamp=3, samples_start=10),
    timestamp_unit=TimestampUnit.NANOSECONDS,
    expected_samples=1000
)

# 定义目录布局
my_layout = DirectoryLayout(
    raw_subdir="DATA",
    file_pattern="*.csv",
    channel_regex=r"CH(\d+)"
)

# 创建并注册适配器
my_adapter = DAQAdapter(
    name="my_daq",
    format_spec=my_spec,
    directory_layout=my_layout
)
register_adapter(my_adapter)

# 在 Context 中使用
ctx.set_config({'daq_adapter': 'my_daq'})
```

## 快速参考

### 常用命令

| 操作 | 代码 |
|------|------|
| 创建 Context | `ctx = Context(storage_dir='./data')` |
| 注册插件 | `ctx.register(*profiles.cpu_default())` |
| 设置配置 | `ctx.set_config({'daq_adapter': 'vx2730'})` |
| 获取数据 | `ctx.get_data('run_001', 'basic_features')` |
| 查看文档指南 | `ctx.help()` 或查看 `docs/` 目录 |
| 查看配置 | `ctx.show_config()` |
| 血缘可视化 | `ctx.plot_lineage('basic_features')` |
| 预览执行 | `ctx.preview_execution('run_001', 'basic_features')` |

### CLI 命令

```bash
# 处理数据
waveform-process --run-name run_001 --verbose

# 扫描 DAQ 目录
waveform-process --scan-daq --daq-root DAQ

# 显示帮助
waveform-process --help
```

---

## 常见问题

### Q: 找不到数据文件？

检查目录结构是否正确：
```python
# 调试：查看扫描到的文件
raw_files = ctx.get_data('run_001', 'raw_files')
print(f"通道数: {len(raw_files)}")
for i, files in enumerate(raw_files):
    print(f"  通道 {i}: {len(files)} 个文件")
```

### Q: 如何查看中间数据？

```python
# 查看结构化波形
st_waveforms = ctx.get_data('run_001', 'st_waveforms')
print(f"通道 0 的 dtype: {st_waveforms[0].dtype}")
print(f"通道 0 的字段: {st_waveforms[0].dtype.names}")
```

### Q: 如何清除缓存重新计算？

```python
ctx.clear_cache('run_001', 'basic_features')
# 或清除所有缓存
ctx.clear_cache('run_001')
```

---
## 下一步

- [配置管理](../features/context/CONFIGURATION.md) - 详细配置说明
- [插件教程](../plugins/tutorials/SIMPLE_PLUGIN_GUIDE.md) - 自定义插件开发
- [血缘可视化](../features/context/LINEAGE_VISUALIZATION_GUIDE.md) - 可视化数据流
- [示例代码](EXAMPLES_GUIDE.md) - 更多使用场景

[^source]: 来源：`waveform_analysis/core/context.py`、`waveform_analysis/core/plugins/profiles.py`、`waveform_analysis/core/plugins/builtin/cpu/`。
