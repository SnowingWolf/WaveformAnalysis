# DAQ 适配器使用指南

**导航**: [文档中心](../README.md) > [功能特性](../../features/README.md) > DAQ 适配器使用指南


本文档详细说明如何使用 DAQ 适配器系统处理不同格式的 DAQ 数据，以及如何自定义适配器支持新的 DAQ 系统。

---

## 📋 目录

1. [概述](#概述)
2. [快速开始](#快速开始)
3. [核心概念](#核心概念)
4. [使用内置适配器](#使用内置适配器)
5. [自定义 DAQ 格式](#自定义-daq-格式)
6. [WaveformStruct 解耦](#waveformstruct-解耦)
7. [最佳实践](#最佳实践)
8. [故障排除](#故障排除)

---

## 概述

### 什么是 DAQ 适配器？

DAQ 适配器是 WaveformAnalysis 中用于统一不同 DAQ 系统数据格式的抽象层。它解决了以下问题：

- **格式多样性**: 不同 DAQ 系统使用不同的 CSV 列布局、时间戳单位、文件组织方式
- **硬编码问题**: 避免在代码中硬编码特定 DAQ 的列索引和格式
- **可扩展性**: 轻松添加对新 DAQ 系统的支持，无需修改核心代码

### 架构概览

```
DAQ 数据文件
    ↓
FormatSpec (格式规范)
    ├── ColumnMapping (列映射)
    ├── TimestampUnit (时间戳单位)
    └── 其他格式参数
    ↓
DirectoryLayout (目录布局)
    ├── 文件模式
    ├── 通道识别
    └── 目录结构
    ↓
DAQAdapter (完整适配器)
    ├── FormatReader (格式读取器)
    └── 文件扫描和加载
    ↓
WaveformStruct (波形结构化)
    └── 使用 FormatSpec 进行列映射
    ↓
结构化数组 (ST_WAVEFORM_DTYPE)
```

---

## 快速开始

### 使用默认 VX2730 格式

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import (
    RawFilesPlugin, WaveformsPlugin, StWaveformsPlugin
)

# 初始化（默认使用 VX2730 格式）
ctx = Context(config={"data_root": "DAQ", "daq_adapter": "vx2730"})
ctx.register(RawFilesPlugin())
ctx.register(WaveformsPlugin())
ctx.register(StWaveformsPlugin())

# 获取数据（自动使用 VX2730 配置）
st_waveforms = ctx.get_data('run_001', 'st_waveforms')
```

### 显式指定适配器

```python
# 为所有插件设置适配器（全局配置）
ctx.set_config({'daq_adapter': 'vx2730'})

# 或者为特定插件设置
ctx.set_config({'daq_adapter': 'vx2730'}, plugin_name='raw_files')
ctx.set_config({'daq_adapter': 'vx2730'}, plugin_name='waveforms')
ctx.set_config({'daq_adapter': 'vx2730'}, plugin_name='st_waveforms')
```

---

## 核心概念

### 1. FormatSpec (格式规范)

定义 DAQ 数据的格式参数。

```python
from waveform_analysis.utils.formats.base import FormatSpec, ColumnMapping, TimestampUnit

spec = FormatSpec(
    name="my_daq",                    # 格式名称
    columns=ColumnMapping(            # 列映射
        board=0,                      # BOARD 列索引
        channel=1,                    # CHANNEL 列索引
        timestamp=2,                  # 时间戳列索引
        samples_start=7,              # 波形数据起始列
        samples_end=None,             # 波形数据结束列（None = 到末尾）
        baseline_start=7,             # 基线计算起始列
        baseline_end=47               # 基线计算结束列
    ),
    timestamp_unit=TimestampUnit.PS,  # 时间戳单位（ps, ns, us, ms, s）
    expected_samples=800,             # 预期采样点数
    delimiter=';',                    # CSV 分隔符
    header_lines=2,                   # 头部行数
    comment_char='#'                  # 注释字符
)
```

`st_waveforms` 内的 `timestamp` 会按 `FormatSpec.timestamp_unit` 统一转换为 ps。

### 2. DirectoryLayout (目录布局)

定义 DAQ 数据的目录结构。

```python
from waveform_analysis.utils.formats.directory import DirectoryLayout

layout = DirectoryLayout(
    raw_subdir="RAW",                 # 原始数据子目录
    file_pattern="*.csv",             # 文件匹配模式
    channel_regex=r"CH(\d+)",         # 通道识别正则表达式
    recursive=False                   # 是否递归搜索
)
```

### 3. DAQAdapter (完整适配器)

结合格式规范和目录布局的完整适配器。

```python
from waveform_analysis.utils.formats.adapter import DAQAdapter

adapter = DAQAdapter(
    name="my_daq",
    format_spec=spec,
    directory_layout=layout
)
```

---

## 使用内置适配器

### VX2730 适配器

WaveformAnalysis 内置了 CAEN VX2730 数字化仪的适配器。

#### VX2730 格式特点

- **分隔符**: 分号 (`;`)
- **头部**: 2 行
- **时间戳单位**: 皮秒 (ps)
- **采样点数**: 800
- **列布局**:
  - 列 0: BOARD
  - 列 1: CHANNEL
  - 列 2: TIMETAG (时间戳)
  - 列 3-6: 其他元数据
  - 列 7-806: 波形数据 (800 个采样点)

#### 使用示例

```python
from waveform_analysis.utils.formats import VX2730_SPEC, VX2730_ADAPTER

# 查看格式规范
print(f"格式名称: {VX2730_SPEC.name}")
print(f"时间戳单位: {VX2730_SPEC.timestamp_unit}")
print(f"采样点数: {VX2730_SPEC.expected_samples}")

# 使用适配器扫描文件
files = VX2730_ADAPTER.scan_run("DAQ", "run_001")
print(f"找到 {len(files)} 个通道的文件")

# 加载单个通道
data = VX2730_ADAPTER.load_channel(files[0])
print(f"加载了 {len(data)} 个事件")
```

---

## 自定义 DAQ 格式

### 场景 1: 简单列映射变更

如果你的 DAQ 格式与 VX2730 类似，只是列索引不同：

```python
from waveform_analysis.utils.formats.base import FormatSpec, ColumnMapping
from waveform_analysis.core.processing.waveform_struct import WaveformStruct, WaveformStructConfig

# 定义自定义列映射
custom_spec = FormatSpec(
    name="custom_daq",
    columns=ColumnMapping(
        board=0,
        channel=1,
        timestamp=3,        # 时间戳在列 3（而不是列 2）
        samples_start=10,   # 波形数据从列 10 开始（而不是列 7）
        baseline_start=10,
        baseline_end=50
    ),
    expected_samples=1000   # 1000 个采样点（而不是 800）
)

# 创建配置并使用
config = WaveformStructConfig(format_spec=custom_spec)
struct = WaveformStruct(waveforms, config=config)
st_waveforms = struct.structure_waveforms(n_jobs=4)
```

可通过 `n_jobs` 并行加速多通道结构化处理。

**English**: Use `n_jobs` to parallelize structuring across channels.

### 场景 2: 完整自定义适配器

如果你需要支持完全不同的 DAQ 系统：

```python
from waveform_analysis.utils.formats import register_adapter, DAQAdapter
from waveform_analysis.utils.formats.base import FormatSpec, ColumnMapping, TimestampUnit
from waveform_analysis.utils.formats.directory import DirectoryLayout

# 1. 定义格式规范
my_spec = FormatSpec(
    name="my_daq",
    columns=ColumnMapping(
        board=0,
        channel=1,
        timestamp=3,
        samples_start=10,
        baseline_start=10,
        baseline_end=50
    ),
    timestamp_unit=TimestampUnit.NS,  # 纳秒时间戳
    expected_samples=1000,
    delimiter=',',                     # 逗号分隔
    header_lines=1,                    # 1 行头部
    comment_char='#'
)

# 2. 定义目录布局
my_layout = DirectoryLayout(
    raw_subdir="DATA",                 # 数据在 DATA 子目录
    file_pattern="*.csv",
    channel_regex=r"channel_(\d+)",    # 文件名格式: channel_0.csv
    recursive=False
)

# 3. 创建适配器
my_adapter = DAQAdapter(
    name="my_daq",
    format_spec=my_spec,
    directory_layout=my_layout
)

# 4. 注册适配器
register_adapter(my_adapter)

# 5. 在 Context 中使用
ctx.set_config({'daq_adapter': 'my_daq'})
st_waveforms = ctx.get_data('run_001', 'st_waveforms')
```

### 场景 3: 自定义格式读取器

如果你的数据格式不是标准 CSV，需要自定义读取器：

```python
from waveform_analysis.utils.formats.base import FormatReader
import numpy as np

class MyCustomReader(FormatReader):
    """自定义格式读取器"""

    def read_file(self, file_path: str) -> np.ndarray:
        """读取文件并返回 NumPy 数组"""
        # 实现你的自定义读取逻辑
        # 例如：读取二进制文件、HDF5 文件等
        data = self._read_custom_format(file_path)
        return data

    def _read_custom_format(self, file_path: str) -> np.ndarray:
        # 你的自定义读取逻辑
        pass

# 创建适配器时使用自定义读取器
my_adapter = DAQAdapter(
    name="my_daq",
    format_spec=my_spec,
    directory_layout=my_layout,
    reader=MyCustomReader(my_spec)
)
```

---

## WaveformStruct 解耦

### 背景

在 2026-01 版本之前，`WaveformStruct` 类硬编码了 VX2730 的列索引：

```python
# 旧代码（硬编码）
wave_data = waves[:, 7:]              # 假设波形从列 7 开始
baseline = np.mean(waves[:, 7:47])    # 假设基线范围是列 7-47
board = waves[:, 0]                   # 假设 BOARD 在列 0
channel = waves[:, 1]                 # 假设 CHANNEL 在列 1
timestamp = waves[:, 2]               # 假设时间戳在列 2
```

这导致无法支持其他 DAQ 格式。

### 解耦方案

现在 `WaveformStruct` 通过 `WaveformStructConfig` 配置类从 `FormatSpec` 读取列索引：

```python
# 新代码（配置驱动）
cols = self.config.format_spec.columns
wave_data = waves[:, cols.samples_start:cols.samples_end]
baseline = np.mean(waves[:, cols.baseline_start:cols.baseline_end])
board = waves[:, cols.board]
channel = waves[:, cols.channel]
timestamp = waves[:, cols.timestamp]
```

### 使用方式

#### 方式 1: 默认（向后兼容）

```python
# 无配置，默认使用 VX2730
struct = WaveformStruct(waveforms)
```

#### 方式 2: 从适配器创建

```python
# 从已注册的适配器创建
struct = WaveformStruct.from_adapter(waveforms, "vx2730")
```

#### 方式 3: 自定义配置

```python
# 使用自定义配置
config = WaveformStructConfig(format_spec=custom_spec)
struct = WaveformStruct(waveforms, config=config)
```

#### 方式 4: 在插件中使用

```python
# 通过 Context 配置
ctx.set_config({'daq_adapter': 'vx2730'}, plugin_name='st_waveforms')
st_waveforms = ctx.get_data('run_001', 'st_waveforms')
```

### 动态 ST_WAVEFORM_DTYPE

`WaveformStruct` 现在支持动态波形长度：

```python
from waveform_analysis.core.processing.dtypes import create_record_dtype

# 创建不同长度的 dtype
dtype_800 = create_record_dtype(800)   # VX2730 标准长度
dtype_1000 = create_record_dtype(1000) # 自定义长度
dtype_1600 = create_record_dtype(1600) # 更长的波形

# 使用配置自动创建
config = WaveformStructConfig(format_spec=custom_spec, wave_length=1000)
dtype = config.get_record_dtype()  # 自动创建 1000 点的 dtype
```

---

## 最佳实践

### 1. 一致性原则

在整个数据流中使用相同的 `daq_adapter`：

```python
# ✅ 推荐：全局配置
ctx.set_config({'daq_adapter': 'vx2730'})

# ❌ 不推荐：混用不同适配器
ctx.set_config({'daq_adapter': 'vx2730'}, plugin_name='raw_files')
ctx.set_config({'daq_adapter': 'custom'}, plugin_name='st_waveforms')  # 不一致！
```

### 2. 优先使用全局配置

```python
# ✅ 推荐：全局配置，简洁明了
ctx.set_config({'daq_adapter': 'vx2730'})

# ⚠️ 可用但繁琐：插件特定配置
ctx.set_config({'daq_adapter': 'vx2730'}, plugin_name='raw_files')
ctx.set_config({'daq_adapter': 'vx2730'}, plugin_name='waveforms')
ctx.set_config({'daq_adapter': 'vx2730'}, plugin_name='st_waveforms')
```

### 3. 验证适配器

在使用自定义适配器前，先验证格式：

```python
from waveform_analysis.utils.formats import get_adapter

# 获取适配器
adapter = get_adapter('my_daq')

# 验证格式规范
print(f"格式名称: {adapter.format_spec.name}")
print(f"列映射: {adapter.format_spec.columns}")
print(f"时间戳单位: {adapter.format_spec.timestamp_unit}")

# 测试文件扫描
files = adapter.scan_run("DAQ", "test_run")
print(f"找到 {len(files)} 个通道")

# 测试数据加载
if files:
    data = adapter.load_channel(files[0])
    print(f"加载了 {len(data)} 个事件")
    print(f"数据形状: {data.shape}")
```

### 4. 文档化自定义格式

为自定义适配器创建文档：

```python
"""
自定义 DAQ 适配器: MyDAQ

格式特点:
- 分隔符: 逗号
- 时间戳单位: 纳秒
- 采样点数: 1000
- 列布局:
  - 列 0: BOARD
  - 列 1: CHANNEL
  - 列 3: TIMESTAMP
  - 列 10-1009: 波形数据

目录结构:
- 数据目录: DATA/
- 文件命名: channel_0.csv, channel_1.csv, ...

使用示例:
    ctx.set_config({'daq_adapter': 'my_daq'})
    st_waveforms = ctx.get_data('run_001', 'st_waveforms')
"""
```

### 5. 测试自定义适配器

创建单元测试验证适配器：

```python
import pytest
from waveform_analysis.utils.formats import get_adapter

def test_my_daq_adapter():
    """测试自定义 DAQ 适配器"""
    adapter = get_adapter('my_daq')

    # 测试格式规范
    assert adapter.format_spec.name == 'my_daq'
    assert adapter.format_spec.expected_samples == 1000

    # 测试文件扫描
    files = adapter.scan_run("test_data", "my_daq_run")
    assert len(files) == 2

    # 测试数据加载
    data = adapter.load_channel(files[0])
    assert data.shape[1] >= 1010  # 至少包含元数据 + 1000 个采样点
```

---

## 故障排除

### 问题 1: 适配器未找到

**错误信息**:
```
ValueError: Adapter 'my_daq' not found. Available adapters: ['vx2730']
```

**解决方案**:
```python
# 确保已注册适配器
from waveform_analysis.utils.formats import register_adapter, list_adapters

# 检查已注册的适配器
print(list_adapters())

# 注册你的适配器
register_adapter(my_adapter)
```

### 问题 2: 列索引错误

**错误信息**:
```
IndexError: index 10 is out of bounds for axis 1 with size 8
```

**解决方案**:
```python
# 检查你的数据文件实际列数
import pandas as pd
df = pd.read_csv("your_file.csv", sep=';', header=1)
print(f"实际列数: {len(df.columns)}")

# 调整 ColumnMapping
columns = ColumnMapping(
    board=0,
    channel=1,
    timestamp=2,
    samples_start=7,  # 确保不超过实际列数
    baseline_start=7,
    baseline_end=min(47, len(df.columns))  # 不超过实际列数
)
```

### 问题 3: 时间戳单位不匹配

**症状**: 时间戳值异常大或异常小

**解决方案**:
```python
# 检查你的数据文件中的时间戳值
df = pd.read_csv("your_file.csv", sep=';', header=1)
print(f"时间戳范围: {df.iloc[:, 2].min()} - {df.iloc[:, 2].max()}")

# 根据数值范围选择合适的单位
# 如果值在 1e12 量级 → ps
# 如果值在 1e9 量级 → ns
# 如果值在 1e6 量级 → us
# 如果值在 1e3 量级 → ms
# 如果值在 1-1000 → s

from waveform_analysis.utils.formats.base import TimestampUnit
spec = FormatSpec(
    ...,
    timestamp_unit=TimestampUnit.NS  # 根据实际情况选择
)
```

### 问题 4: 波形长度不匹配

**错误信息**:
```
ValueError: could not broadcast input array from shape (1000,) into shape (800,)
```

**解决方案**:
```python
# 方案 1: 指定正确的波形长度
config = WaveformStructConfig(
    format_spec=custom_spec,
    wave_length=1000  # 匹配实际波形长度
)

# 方案 2: 让系统自动检测
# WaveformStruct 会自动使用实际波形长度创建动态 dtype
struct = WaveformStruct(waveforms, config=config)
st_waveforms = struct.structure_waveforms()  # 自动适配
```

### 问题 5: 文件扫描失败

**症状**: `scan_run()` 返回空列表

**解决方案**:
```python
# 检查目录布局配置
layout = DirectoryLayout(
    raw_subdir="RAW",           # 确保子目录名称正确
    file_pattern="*.csv",       # 确保文件扩展名正确
    channel_regex=r"CH(\d+)",   # 确保正则表达式匹配文件名
    recursive=False
)

# 手动测试文件扫描
import os
import re
data_dir = "DAQ/run_001/RAW"
files = [f for f in os.listdir(data_dir) if f.endswith('.csv')]
print(f"找到的文件: {files}")

# 测试正则表达式
pattern = re.compile(r"CH(\d+)")
for f in files:
    match = pattern.search(f)
    if match:
        print(f"文件 {f} 匹配通道 {match.group(1)}")
```

---

## 相关文档

- [快速入门指南](../user-guide/QUICKSTART_GUIDE.md)
- [架构设计文档](../architecture/ARCHITECTURE.md)
- [插件开发指南](../development/plugin-development/plugin_guide.md)
- [API 参考](../api/README.md)

---

## 更新历史

- **2026-01**: 初始版本，WaveformStruct DAQ 解耦
- **2026-01**: 添加 VX2730 适配器说明
- **2026-01**: 添加自定义适配器示例和故障排除
