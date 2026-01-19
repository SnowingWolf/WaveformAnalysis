# 🔌 DAQ 适配器层

**导航**: [文档中心](../../README.md) > [功能特性](../README.md) > [工具函数](README.md) > DAQ 适配器层

DAQ 适配器层提供统一的数据格式读取和目录结构适配接口，支持不同的 DAQ 设备和数据格式。

---

## 📋 概述

DAQ 适配器层解决两个核心问题：

1. **文件格式适配** - 不同的 CSV 列布局、时间戳单位、头部处理
2. **目录结构适配** - 不同的目录布局、文件命名规则、通道识别模式

### 核心组件

| 组件 | 说明 |
|------|------|
| `FormatSpec` | 格式规范数据类（列映射、时间戳单位、分隔符等） |
| `ColumnMapping` | CSV 列索引配置 |
| `TimestampUnit` | 时间戳单位枚举（ps, ns, us, ms, s） |
| `FormatReader` | 格式读取器抽象基类 |
| `DirectoryLayout` | 目录结构配置 |
| `DAQAdapter` | 完整适配器（FormatReader + DirectoryLayout） |

---

## 🚀 快速开始

### 使用内置 VX2730 适配器

```python
from waveform_analysis.utils.formats import get_adapter

# 获取 VX2730 适配器
adapter = get_adapter("vx2730")

# 扫描运行目录，获取按通道分组的文件
channel_files = adapter.scan_run("DAQ", "run_001")
print(f"找到 {len(channel_files)} 个通道")

# 加载单个通道数据
data = adapter.load_channel("DAQ", "run_001", channel=0)
print(f"加载 {len(data)} 条记录")

# 提取列并转换时间戳（自动转换为皮秒）
extracted = adapter.extract_and_convert(data)
print(f"时间戳范围: {extracted['timestamp'].min()} - {extracted['timestamp'].max()} ps")
```

### 在 Context 中使用

```python
from waveform_analysis.core import Context

ctx = Context()
ctx.set_config({'daq_adapter': 'vx2730'})

# 插件将自动使用配置的适配器
data = ctx.get_data('run_001', 'waveforms')
```

### 在 WaveformDataset 中使用

```python
from waveform_analysis import WaveformDataset

# 使用默认 VX2730 适配器（向后兼容）
ds = WaveformDataset(run_name="run_001", n_channels=2)
ds.load_raw_data()
```

---

## 📐 格式规范 (FormatSpec)

`FormatSpec` 定义 DAQ 数据文件的格式：

```python
from waveform_analysis.utils.formats import FormatSpec, ColumnMapping, TimestampUnit

spec = FormatSpec(
    name="my_format",
    version="1.0",
    columns=ColumnMapping(
        board=0,              # BOARD 列索引
        channel=1,            # CHANNEL 列索引
        timestamp=2,          # TIMETAG 列索引
        samples_start=7,      # 波形采样起始列
        samples_end=None,     # 波形采样结束列（None = 到行末）
        baseline_start=7,     # 基线计算起始列
        baseline_end=47,      # 基线计算结束列
    ),
    timestamp_unit=TimestampUnit.PICOSECONDS,  # 时间戳单位
    file_pattern="*CH*.CSV",                   # 文件匹配模式
    header_rows_first_file=2,                  # 首文件跳过行数
    header_rows_other_files=0,                 # 其他文件跳过行数
    delimiter=";",                             # CSV 分隔符
    expected_samples=800,                      # 预期采样点数
    metadata={                                 # 自定义元数据
        "manufacturer": "CAEN",
        "model": "VX2730",
    },
)
```

### 时间戳单位

```python
from waveform_analysis.utils.formats import TimestampUnit

TimestampUnit.PICOSECONDS   # 1e-12 秒
TimestampUnit.NANOSECONDS   # 1e-9 秒
TimestampUnit.MICROSECONDS  # 1e-6 秒
TimestampUnit.MILLISECONDS  # 1e-3 秒
TimestampUnit.SECONDS       # 1 秒
```

---

## 📁 目录布局 (DirectoryLayout)

`DirectoryLayout` 定义数据目录结构：

```python
from waveform_analysis.utils.formats import DirectoryLayout

layout = DirectoryLayout(
    name="vx2730",
    raw_subdir="RAW",                                    # 原始数据子目录
    run_path_template="{data_root}/{run_name}/{raw_subdir}",  # 路径模板
    file_glob_pattern="*CH*.CSV",                        # 文件匹配模式
    file_extension=".CSV",                               # 文件扩展名
    channel_regex=r"CH(\d+)",                            # 通道号提取正则
    file_index_regex=r"_(\d+)\.CSV$",                    # 文件索引提取正则
    run_info_pattern="{run_name}_info.txt",              # 运行信息文件
)
```

### 预定义布局

```python
from waveform_analysis.utils.formats import VX2730_LAYOUT, FLAT_LAYOUT

# VX2730 标准布局: DAQ/run_name/RAW/*.CSV
layout1 = VX2730_LAYOUT

# 扁平布局: DAQ/run_name/*.csv（无 RAW 子目录）
layout2 = FLAT_LAYOUT
```

### 目录布局方法

```python
# 获取原始数据路径
raw_path = layout.get_raw_path("DAQ", "run_001")
# 结果: DAQ/run_001/RAW

# 从文件名提取通道号
channel = layout.extract_channel("DataR_CH0@VX2730_run_001.CSV")
# 结果: 0

# 按通道分组文件
groups = layout.group_files_by_channel(raw_path)
# 结果: {0: [{'path': ..., 'index': 0, 'filename': ...}], ...}
```

---

## 🔧 完整适配器 (DAQAdapter)

`DAQAdapter` 结合 `FormatReader` 和 `DirectoryLayout`：

```python
from waveform_analysis.utils.formats import (
    DAQAdapter, GenericCSVReader, DirectoryLayout, FormatSpec
)

# 创建完整适配器
adapter = DAQAdapter(
    name="my_adapter",
    format_reader=GenericCSVReader(my_spec),
    directory_layout=my_layout,
)

# 注册适配器
from waveform_analysis.utils.formats import register_adapter
register_adapter(adapter)
```

### 适配器 API

```python
# 获取原始数据路径
raw_path = adapter.get_raw_path("DAQ", "run_001")

# 扫描运行目录
channel_files = adapter.scan_run("DAQ", "run_001")
# 返回: {channel: [file_paths]}

# 加载单个通道
data = adapter.load_channel("DAQ", "run_001", channel=0, show_progress=True)

# 生成器模式加载（内存优化）
for chunk in adapter.load_channel_generator("DAQ", "run_001", channel=0, chunk_size=10):
    process_chunk(chunk)

# 提取列并转换时间戳
extracted = adapter.extract_and_convert(data)
# 返回: {'board': ..., 'channel': ..., 'timestamp': ..., 'samples': ..., 'baseline': ...}
```

---

## 🏭 自定义适配器示例

### 完整自定义示例

```python
from waveform_analysis.utils.formats import (
    FormatSpec, ColumnMapping, TimestampUnit,
    DirectoryLayout, DAQAdapter,
    GenericCSVReader, register_adapter
)

# 1. 定义文件格式
my_format = FormatSpec(
    name="my_daq",
    columns=ColumnMapping(
        board=0,
        channel=1,
        timestamp=3,      # 时间戳在第 4 列
        samples_start=5,  # 采样从第 6 列开始
        samples_end=None,
    ),
    timestamp_unit=TimestampUnit.NANOSECONDS,  # 纳秒单位
    header_rows_first_file=1,                   # 只有 1 行头部
    delimiter=",",                              # 逗号分隔
)

# 2. 定义目录结构
my_layout = DirectoryLayout(
    name="my_layout",
    raw_subdir="data",                           # 使用 data/ 而不是 RAW/
    run_path_template="{data_root}/{run_name}/{raw_subdir}",
    file_glob_pattern="*.dat",                   # .dat 文件
    channel_regex=r"channel(\d+)",               # channel0, channel1...
    file_index_regex=r"_part(\d+)\.dat$",        # _part0.dat, _part1.dat...
)

# 3. 创建并注册适配器
my_adapter = DAQAdapter(
    name="my_daq",
    format_reader=GenericCSVReader(my_format),
    directory_layout=my_layout,
)
register_adapter(my_adapter)

# 4. 使用自定义适配器
from waveform_analysis.utils.formats import get_adapter
adapter = get_adapter("my_daq")
data = adapter.load_channel("data_root", "run_001", channel=0)
```

---

## 📚 VX2730 适配器详情

CAEN VX2730 数字化仪是默认支持的格式：

### 格式特点

| 特性 | 值 |
|------|-----|
| 分隔符 | 分号 (`;`) |
| 首文件头部 | 2 行 |
| 其他文件头部 | 0 行 |
| 时间戳单位 | 皮秒 (ps) |
| 预期采样点 | 800 |

### 列布局

| 列索引 | 内容 |
|--------|------|
| 0 | BOARD |
| 1 | CHANNEL |
| 2 | TIMETAG（时间戳） |
| 3-6 | 其他元数据 |
| 7+ | SAMPLES（波形采样） |

### 目录结构

```
DAQ/
└── run_name/
    └── RAW/
        ├── DataR_CH0@VX2730_run_name.CSV
        ├── DataR_CH0@VX2730_run_name_1.CSV
        ├── DataR_CH7@VX2730_run_name.CSV
        └── ...
```

### 直接使用 VX2730 组件

```python
from waveform_analysis.utils.formats import (
    VX2730_SPEC,      # 格式规范
    VX2730_LAYOUT,    # 目录布局
    VX2730Reader,     # 读取器
    VX2730_ADAPTER,   # 完整适配器
)

# 查看格式规范
print(f"分隔符: {VX2730_SPEC.delimiter}")
print(f"时间戳单位: {VX2730_SPEC.timestamp_unit}")

# 直接使用读取器
reader = VX2730Reader()
data = reader.read_files(['file1.CSV', 'file2.CSV'])
```

---

## 🔍 注册表 API

### 格式注册表

```python
from waveform_analysis.utils.formats import (
    register_format,
    get_format_reader,
    get_format_spec,
    list_formats,
    is_format_registered,
    unregister_format,
)

# 列出所有格式
print(list_formats())  # ['vx2730_csv', ...]

# 检查格式是否存在
if is_format_registered("vx2730_csv"):
    reader = get_format_reader("vx2730_csv")
    spec = get_format_spec("vx2730_csv")
```

### 适配器注册表

```python
from waveform_analysis.utils.formats import (
    register_adapter,
    get_adapter,
    list_adapters,
    is_adapter_registered,
    unregister_adapter,
)

# 列出所有适配器
print(list_adapters())  # ['vx2730', ...]

# 获取适配器
adapter = get_adapter("vx2730")
```

---

## 🔗 与其他组件集成

### 与 io.py 集成

```python
from waveform_analysis.utils.io import parse_and_stack_files

# 使用格式类型
data = parse_and_stack_files(files, format_type="vx2730_csv")

# 使用自定义读取器
from waveform_analysis.utils.formats import get_format_reader
reader = get_format_reader("vx2730_csv")
data = parse_and_stack_files(files, format_reader=reader)
```

### 与 DAQRun 集成

```python
from waveform_analysis.utils.daq import DAQRun

# 使用适配器名称
run = DAQRun("run_001", "DAQ/run_001", daq_adapter="vx2730")

# 使用自定义布局
from waveform_analysis.utils.formats import DirectoryLayout
layout = DirectoryLayout(name="custom", raw_subdir="data")
run = DAQRun("run_001", "DAQ/run_001", directory_layout=layout)
```

### 与 WaveformLoader 集成

```python
from waveform_analysis.core.processing import WaveformLoader

loader = WaveformLoader(
    n_channels=2,
    run_name="run_001",
    data_root="DAQ",
    daq_adapter="vx2730",
)
```

### 与插件集成

```python
# 在配置中指定适配器
ctx.set_config({'daq_adapter': 'vx2730'})

# 或在插件选项中指定
ctx.set_config({'daq_adapter': 'my_adapter'}, plugin_name='raw_files')
```

---

## 🔗 相关资源

- [波形预览](waveform_preview.md) - 支持适配器的波形预览工具
- [缓存管理](../advanced/CACHE.md) - 缓存机制说明
- [API 参考](../../api/api_reference.md) - 完整 API 文档

---

**快速链接**:
[VX2730 适配器](#-vx2730-适配器详情) |
[自定义适配器](#-自定义适配器示例) |
[注册表 API](#-注册表-api)
