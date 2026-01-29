# 快速开始指南

**导航**: [文档中心](../README.md) > [用户指南](README.md) > 快速开始指南

本文档帮助你快速上手 WaveformAnalysis。

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
pip install -e .
```

### 核心概念

| 概念 | 说明 |
|------|------|
| **Context** | 插件系统调度器，管理依赖、配置、缓存 |
| **Plugin** | 数据处理单元（RawFiles → Waveforms → Features） |
| **Lineage** | 自动血缘追踪，确保缓存一致性 |

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
from waveform_analysis.core.plugins.builtin.cpu import standard_plugins

# 1. 创建 Context
ctx = Context(storage_dir='./cache')

# 2. 注册标准插件
ctx.register(*standard_plugins)

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
for ch_idx, ch_data in enumerate(basic_features):
    print(f"通道 {ch_idx}: {len(ch_data)} 个事件")
    print(f"  height: {ch_data['height'][:3]}...")
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

`basic_features` 是一个列表，每个元素对应一个通道的 NumPy 结构化数组：

```python
# 数据结构
basic_features: List[np.ndarray]  # 长度 = 通道数

# 每个通道的 dtype
dtype = [
    ('height', 'f4'),  # 波形高度 (max - min)
    ('area', 'f4'),    # 波形面积 (积分)
]
```

**字段说明**：

| 字段 | 类型 | 单位 | 计算方式 |
|------|------|------|----------|
| `height` | float32 | ADC counts | `max(wave) - min(wave)` |
| `area` | float32 | ADC counts × samples | `sum(baseline - wave)` |

### 访问示例

```python
# 获取所有通道的 height
all_heights = [ch['height'] for ch in basic_features]

# 获取通道 0 的数据
ch0_heights = basic_features[0]['height']
ch0_areas = basic_features[0]['area']

# 统计
print(f"通道 0 平均高度: {ch0_heights.mean():.2f}")
print(f"通道 0 平均面积: {ch0_areas.mean():.2f}")
```

### 导出为 CSV

```python
import pandas as pd

# 转换为 DataFrame
rows = []
for ch_idx, ch_data in enumerate(basic_features):
    for i in range(len(ch_data)):
        rows.append({
            'channel': ch_idx,
            'height': ch_data['height'][i],
            'area': ch_data['area'][i],
        })

df = pd.DataFrame(rows)
df.to_csv('basic_features.csv', index=False)
```

**导出文件样例** (`basic_features.csv`)：

```csv
channel,height,area
0,125.3,4521.7
0,98.7,3892.1
0,142.5,5103.4
1,87.2,3245.8
1,156.8,5678.2
...
```

### 数据流水线

```
raw_files → waveforms → st_waveforms → basic_features
    │           │            │              │
    │           │            │              └─ height/area 特征
    │           │            └─ 结构化数组 (timestamp, baseline, wave)
    │           └─ 原始波形数据 (2D numpy array)
    └─ 文件路径列表
```

**可视化血缘图**：

```python
ctx.plot_lineage('basic_features', kind='labview')
```

---

## 场景 1: 基础分析流程

**推荐新手使用** - 使用 Context API 进行标准分析。

### 完整代码模板

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""基础波形分析"""

from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import standard_plugins

def main():
    # 1. 初始化 Context
    ctx = Context(storage_dir='./strax_data')
    ctx.register(*standard_plugins)

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
    heights = [ch['height'] for ch in basic_features]
    areas = [ch['area'] for ch in basic_features]
    print(f"Found {len(heights)} height arrays")

    # 4. 可视化血缘图（可选）
    ctx.plot_lineage('basic_features', kind='labview')

    return heights

if __name__ == '__main__':
    result = main()
    print(f"Analysis complete. Channels: {len(result)}")
```

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

**处理多个 run** - 并行处理多个数据集。

### 代码模板

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.data.export import BatchProcessor
from waveform_analysis.core.plugins.builtin.cpu import standard_plugins

# 初始化
ctx = Context(storage_dir='./strax_data')
ctx.register(*standard_plugins)
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

---

## 场景 3: 流式处理

**处理大数据** - 分块处理，内存友好。

### 代码模板

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.core.streaming import get_streaming_context
from waveform_analysis.core.plugins.builtin.cpu import standard_plugins

# 初始化
ctx = Context(storage_dir='./strax_data')
ctx.register(*standard_plugins)
ctx.set_config({'data_root': 'DAQ', 'daq_adapter': 'vx2730'})

# 创建流式上下文
stream_ctx = get_streaming_context(ctx, run_id='run_001', chunk_size=50000)

# 分块处理
for chunk in stream_ctx.get_stream('st_waveforms'):
    # 处理每个数据块
    handle_chunk(chunk)
    print(f"Processed chunk: {chunk.start} - {chunk.end}")
```

---

## 场景 4: 使用自定义 DAQ 格式

**支持多种 DAQ 系统** - 使用 DAQ 适配器处理不同格式的数据。

### 方式 1: 使用内置适配器（推荐）

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import (
    RawFilesPlugin, WaveformsPlugin, StWaveformsPlugin
)

# 初始化 Context
ctx = Context(config={"data_root": "DAQ", "daq_adapter": "vx2730"})

# 注册插件
ctx.register(RawFilesPlugin())
ctx.register(WaveformsPlugin())
ctx.register(StWaveformsPlugin())

# 为所有插件设置 DAQ 适配器（全局配置）
ctx.set_config({'daq_adapter': 'vx2730'})

# 获取数据（自动使用配置的适配器）
st_waveforms = ctx.get_data('run_001', 'st_waveforms')
print(f"Loaded {len(st_waveforms)} channels")
```

### 方式 2: 自定义 DAQ 格式

```python
from waveform_analysis.core.processing.waveform_struct import WaveformStruct, WaveformStructConfig
from waveform_analysis.utils.formats import FormatSpec, ColumnMapping, TimestampUnit

# 定义自定义格式
custom_spec = FormatSpec(
    name="my_daq",
    columns=ColumnMapping(
        board=0,           # BOARD 列索引
        channel=1,         # CHANNEL 列索引
        timestamp=3,       # 时间戳列索引
        samples_start=10,  # 波形数据起始列
        baseline_start=10, # 基线计算起始列
        baseline_end=50    # 基线计算结束列
    ),
    timestamp_unit=TimestampUnit.NANOSECONDS,  # 按实际单位设置
    expected_samples=1000  # 预期采样点数
)

# 创建配置
config = WaveformStructConfig(format_spec=custom_spec)

# 使用自定义配置
struct = WaveformStruct(waveforms, config=config)
st_waveforms = struct.structure_waveforms()
```

说明：`st_waveforms` 的 `timestamp` 会按 `FormatSpec.timestamp_unit` 统一转换为 ps。

### 方式 3: 注册自定义适配器

```python
from waveform_analysis.utils.formats import register_adapter, DAQAdapter
from waveform_analysis.utils.formats.base import FormatSpec, ColumnMapping, TimestampUnit
from waveform_analysis.utils.formats.directory import DirectoryLayout

# 定义格式规范
my_spec = FormatSpec(
    name="my_daq",
    columns=ColumnMapping(board=0, channel=1, timestamp=3, samples_start=10),
    timestamp_unit=TimestampUnit.NANOSECONDS,  # 按实际单位设置
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

---

## 快速参考卡

### 常用命令

| 操作 | 代码 |
|------|------|
| 创建 Context | `ctx = Context(storage_dir='./data')` |
| 注册插件 | `ctx.register(*standard_plugins)` |
| 设置配置 | `ctx.set_config({'daq_adapter': 'vx2730'})` |
| 获取数据 | `ctx.get_data('run_001', 'basic_features')` |
| 查看帮助 | `ctx.help()` |
| 查看配置 | `ctx.show_config()` |
| 血缘可视化 | `ctx.plot_lineage('basic_features')` |
| 预览执行 | `ctx.preview_execution('run_001', 'basic_features')` |

### 快速代码模板

```python
# 生成代码模板
ctx.quickstart('basic')              # 基础分析
```

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
- [插件教程](../features/plugin/SIMPLE_PLUGIN_GUIDE.md) - 自定义插件开发
- [血缘可视化](../features/context/LINEAGE_VISUALIZATION_GUIDE.md) - 可视化数据流

---

**快速链接**:
[配置管理](../features/context/CONFIGURATION.md) |
[插件教程](../features/plugin/SIMPLE_PLUGIN_GUIDE.md) |
[示例代码](EXAMPLES_GUIDE.md)
