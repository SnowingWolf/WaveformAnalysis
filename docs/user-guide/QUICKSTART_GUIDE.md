# 快速开始指南

**导航**: [文档中心](../README.md) > [用户指南](README.md) > 快速开始指南

本文档帮助你快速上手 WaveformAnalysis。

## 快速安装

```bash
# 方式 1: 使用安装脚本（推荐）
./install.sh

# 方式 2: 手动安装
pip install -e .

# 方式 3: 带开发依赖
pip install -e ".[dev]"
```

## 核心概念

推荐使用 **Context** API 进行数据处理。

| 概念 | 说明 |
|------|------|
| **Context** | 插件系统调度器，管理依赖、配置、缓存 |
| **Plugin** | 数据处理单元（RawFiles → Waveforms → Peaks） |
| **Lineage** | 自动血缘追踪，确保缓存一致性 |

## 场景 1: 基础分析流程

推荐新手使用，使用 Context API 进行标准分析。

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

数据流：`raw_files → waveforms → st_waveforms → basic_features`

## 场景 2: 批量处理

处理多个 run，并行处理多个数据集。

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

## 场景 3: 流式处理

处理大数据，分块处理，内存友好。

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

## 场景 4: 使用自定义 DAQ 格式

### 使用内置适配器（推荐）

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
| 注册插件 | `ctx.register(*standard_plugins)` |
| 设置配置 | `ctx.set_config({'daq_adapter': 'vx2730'})` |
| 获取数据 | `ctx.get_data('run_001', 'basic_features')` |
| 查看帮助 | `ctx.help()` |
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

## 下一步

- [配置管理](../features/context/CONFIGURATION.md) - 详细配置说明
- [插件教程](../features/plugin/SIMPLE_PLUGIN_GUIDE.md) - 自定义插件开发
- [血缘可视化](../features/context/LINEAGE_VISUALIZATION_GUIDE.md) - 可视化数据流
- [示例代码](EXAMPLES_GUIDE.md) - 更多使用场景
