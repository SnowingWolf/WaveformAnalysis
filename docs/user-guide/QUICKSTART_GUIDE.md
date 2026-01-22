# 快速开始指南

**导航**: [文档中心](../README.md) > [用户指南](README.md) > 快速开始指南

> 阅读时间: 10 分钟 | 难度: ⭐ 入门

本文档帮助你在 5 分钟内快速上手 WaveformAnalysis。

---

## 📋 目录

1. [快速安装](#快速安装)
2. [核心概念](#核心概念)
3. [场景 1: 基础分析流程](#场景-1-基础分析流程)
4. [场景 2: 批量处理](#场景-2-批量处理)
5. [场景 3: 流式处理](#场景-3-流式处理)
6. [场景 4: 使用自定义 DAQ 格式](#场景-4-使用自定义-daq-格式)
7. [快速参考卡](#快速参考卡)

---

## 快速安装

### 方式 1: 使用安装脚本（推荐）

```bash
./install.sh
```

### 方式 2: 手动安装

```bash
# 开发模式安装
pip install -e .

# 带开发依赖
pip install -e ".[dev]"
```

### 方式 3: Conda 环境

```bash
# 激活环境
conda activate pyroot-kernel

# 安装
pip install -e .
```

---

## 核心概念

在开始之前，了解以下核心概念：

> ✅ 推荐路径：新代码请使用 **Context**。`WaveformDataset` 已弃用，仅保留兼容层。

| 概念 | 说明 |
|------|------|
| **Context** | 插件系统调度器，管理依赖、配置、缓存 |
| **Plugin** | 数据处理单元（RawFiles → Waveforms → Peaks） |
| **Lineage** | 自动血缘追踪，确保缓存一致性 |

---

## 场景 1: 基础分析流程

**推荐新手使用** - 使用 Context API 进行标准分析。

### 完整代码模板

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""基础波形分析"""

from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin import standard_plugins

def main():
    # 1. 初始化 Context
    ctx = Context(storage_dir='./strax_data')
    ctx.register(*standard_plugins)

    # 2. 设置配置
    ctx.set_config({
        'data_root': 'DAQ',
        'n_channels': 2,
        'threshold': 15.0,
    })

    # 3. 获取数据（自动触发依赖链）
    run_id = 'run_001'
    print(f"Processing run: {run_id}")
    peaks = ctx.get_data(run_id, 'peaks')
    print(f"Found {len(peaks)} peaks")

    # 4. 可视化血缘图（可选）
    ctx.plot_lineage('peaks', kind='labview')

    return peaks

if __name__ == '__main__':
    result = main()
    print(f"Analysis complete. Result shape: {result.shape}")
```

### 说明

| 步骤 | 说明 |
|------|------|
| `Context(storage_dir=...)` | 创建 Context，指定缓存目录 |
| `ctx.register(...)` | 注册标准插件集 |
| `ctx.set_config(...)` | 设置全局配置 |
| `ctx.get_data(run_id, name)` | 获取数据，自动触发依赖链 |

### 数据流

```
raw_files → waveforms → st_waveforms → peaks
```

### 预期

- **运行时间**: 约 30 秒（取决于数据量）
- **缓存位置**: `./strax_data/`
- **输出**: NumPy 结构化数组

---

## 场景 2: 批量处理

**处理多个 run** - 并行处理多个数据集。

### 代码模板

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.data.export import BatchProcessor
from waveform_analysis.core.plugins.builtin import standard_plugins

# 初始化
ctx = Context(storage_dir='./strax_data')
ctx.register(*standard_plugins)
ctx.set_config({'data_root': 'DAQ', 'n_channels': 2})

# 批量处理
processor = BatchProcessor(ctx)
results = processor.process_runs(
    run_ids=['run_001', 'run_002', 'run_003'],
    data_name='peaks',
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
from waveform_analysis.core.plugins.builtin import standard_plugins

# 初始化
ctx = Context(storage_dir='./strax_data')
ctx.register(*standard_plugins)
ctx.set_config({'data_root': 'DAQ', 'n_channels': 2})

# 创建流式上下文
stream_ctx = get_streaming_context(ctx, run_id='run_001', chunk_size=50000)

# 分块处理
for chunk in stream_ctx.get_stream('st_waveforms'):
    # 处理每个数据块
    process_chunk(chunk)
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
ctx = Context(config={"data_root": "DAQ", "n_channels": 2})

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
from waveform_analysis.core.processing.processor import WaveformStruct, WaveformStructConfig
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
| 设置配置 | `ctx.set_config({'n_channels': 2})` |
| 获取数据 | `ctx.get_data('run_001', 'peaks')` |
| 查看帮助 | `ctx.help()` |
| 查看配置 | `ctx.show_config()` |
| 血缘可视化 | `ctx.plot_lineage('peaks')` |
| 预览执行 | `ctx.preview_execution('run_001', 'peaks')` |

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

## 下一步

- [配置管理](../features/context/CONFIGURATION.md) - 详细配置说明
- [插件教程](../features/plugin/SIMPLE_PLUGIN_GUIDE.md) - 自定义插件开发
- [血缘可视化](../features/context/LINEAGE_VISUALIZATION_GUIDE.md) - 可视化数据流

---

**快速链接**:
[配置管理](../features/context/CONFIGURATION.md) |
[插件教程](../features/plugin/SIMPLE_PLUGIN_GUIDE.md) |
[示例代码](EXAMPLES_GUIDE.md)
