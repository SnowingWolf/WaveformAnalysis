# DAQ 适配器系统详解

## 概述

DAQ 适配器系统是一个灵活的框架，用于统一处理不同 DAQ（数据采集）设备的数据格式。它解决了不同设备产生不同文件格式、目录结构、时间戳单位等问题。

## 核心架构

### 三层架构

```
┌─────────────────────────────────────────────────────────┐
│                    DAQAdapter                           │
│  (完整适配器 - 提供统一的高层接口)                        │
│  - scan_run()      扫描运行目录                          │
│  - load_channel()  加载通道数据                          │
│  - extract_and_convert()  提取并转换数据                 │
└─────────────────────────────────────────────────────────┘
                    ↓ 组合
        ┌───────────────────────┬───────────────────────┐
        ↓                       ↓                       ↓
┌───────────────┐      ┌────────────────┐     ┌────────────────┐
│ FormatReader  │      │ DirectoryLayout│     │  FormatSpec    │
│ (文件读取器)   │      │ (目录结构)      │     │  (格式规范)     │
│               │      │                │     │                │
│ - read_file() │      │ - get_raw_path│     │ - columns      │
│ - read_files()│      │ - group_files │     │ - timestamp_unit│
└───────────────┘      └────────────────┘     │ - delimiter    │
                                              └────────────────┘
```

## 核心组件详解

### 1. FormatSpec (格式规范)

**作用**: 描述 DAQ 数据文件的格式特征

**包含信息**:
- **ColumnMapping**: CSV 列映射
  - `board`: BOARD 列索引 (板卡编号)
  - `channel`: CHANNEL 列索引 (通道编号)
  - `timestamp`: TIMETAG 列索引 (时间戳)
  - `samples_start`: 波形数据起始列
  - `baseline_start/end`: 基线计算范围

- **TimestampUnit**: 时间戳单位
  - `PICOSECONDS` (ps) - 1e-12 秒
  - `NANOSECONDS` (ns) - 1e-9 秒
  - `MICROSECONDS` (us) - 1e-6 秒
  - `MILLISECONDS` (ms) - 1e-3 秒
  - `SECONDS` (s)

- **文件格式参数**:
  - `delimiter`: CSV 分隔符 (如 `;` 或 `,`)
  - `header_rows_first_file`: 首文件头部行数
  - `header_rows_other_files`: 其他文件头部行数
  - `file_pattern`: 文件匹配模式 (如 `*CH*.CSV`)

- **采样参数**:
  - `expected_samples`: 预期采样点数 (如 800)
  - `sampling_rate_hz`: 采样率 (如 500 MHz)

**示例 - VX2730**:
```python
VX2730_SPEC = FormatSpec(
    name="vx2730_csv",
    columns=ColumnMapping(
        board=0,           # 第 0 列是 BOARD
        channel=1,         # 第 1 列是 CHANNEL
        timestamp=2,       # 第 2 列是 TIMETAG
        samples_start=7,   # 第 7 列开始是波形数据
        baseline_start=7,  # 前 40 个采样点用于基线
        baseline_end=47,
    ),
    timestamp_unit=TimestampUnit.PICOSECONDS,  # 时间戳单位是 ps
    delimiter=";",                              # 分号分隔
    header_rows_first_file=2,                   # 首文件跳过 2 行
    expected_samples=800,                       # 800 个采样点
    sampling_rate_hz=500e6,                     # 500 MHz
)
```

### 2. FormatReader (格式读取器)

**作用**: 根据 FormatSpec 读取和解析文件

**核心方法**:
- `read_file(file_path)`: 读取单个文件
- `read_files(file_paths)`: 读取并堆叠多个文件
- `read_files_generator(file_paths)`: 生成器模式读取（大数据）
- `extract_columns(data)`: 从原始数据提取各列
- `convert_timestamp_to_ps(timestamps)`: 时间戳单位转换

**工作流程**:
```
CSV 文件
    ↓ read_file()
原始 NumPy 数组 (n_events × n_columns)
    ↓ extract_columns()
结构化数据字典:
  - board: [0, 0, 0, ...]
  - channel: [0, 0, 0, ...]
  - timestamp: [1000, 2000, 3000, ...]  (原始单位)
  - samples: [[100.1, 100.2, ...], ...]  (波形数据)
  - baseline: [100.15, 100.18, ...]      (计算的基线)
    ↓ convert_timestamp_to_ps()
  - timestamp: [1000000, 2000000, ...]   (转换为 ps)
```

**示例 - VX2730Reader**:
```python
class VX2730Reader(FormatReader):
    def read_file(self, file_path, is_first_file=True):
        # 根据 spec.header_rows_first_file 跳过头部
        skiprows = self.spec.header_rows_first_file if is_first_file else 0

        # 使用 spec.delimiter 读取 CSV
        df = pd.read_csv(
            file_path,
            delimiter=self.spec.delimiter,
            skiprows=skiprows,
            header=None
        )
        return df.values
```

### 3. DirectoryLayout (目录结构)

**作用**: 描述数据文件的目录组织方式

**包含信息**:
- `raw_subdir`: 原始数据子目录名 (如 `"RAW"`)
- `file_pattern`: 文件匹配模式 (如 `"*CH*.CSV"`)
- `channel_pattern`: 通道号提取正则表达式

**目录结构示例**:
```
DAQ/                          # data_root
├── run_001/                  # run_name
│   ├── RAW/                  # raw_subdir
│   │   ├── CH0_0.CSV        # 通道 0, 文件 0
│   │   ├── CH0_1.CSV        # 通道 0, 文件 1
│   │   ├── CH1_0.CSV        # 通道 1, 文件 0
│   │   └── CH1_1.CSV        # 通道 1, 文件 1
│   └── processed/
└── run_002/
    └── RAW/
```

**核心方法**:
- `get_raw_path(data_root, run_name)`: 获取原始数据目录
  ```python
  # 返回: DAQ/run_001/RAW
  ```
- `group_files_by_channel(raw_path)`: 按通道分组文件
  ```python
  # 返回: {
  #   0: [Path('CH0_0.CSV'), Path('CH0_1.CSV')],
  #   1: [Path('CH1_0.CSV'), Path('CH1_1.CSV')],
  # }
  ```

### 4. DAQAdapter (完整适配器)

**作用**: 组合上述三个组件，提供统一的高层接口

**核心方法**:

#### 扫描和发现
```python
# 扫描运行目录，返回按通道分组的文件
channel_files = adapter.scan_run("DAQ", "run_001")
# 返回: {0: [Path(...), ...], 1: [Path(...), ...]}
```

#### 加载数据
```python
# 加载单个通道
data = adapter.load_channel("DAQ", "run_001", channel=0)
# 返回: NumPy 数组 (n_events × n_columns)

# 加载所有通道
all_data = adapter.load_all_channels("DAQ", "run_001")
# 返回: [ch0_data, ch1_data, ...]
```

#### 提取和转换
```python
# 提取列并转换时间戳为 ps
extracted = adapter.extract_and_convert(data)
# 返回: {
#   'board': array([0, 0, ...]),
#   'channel': array([0, 0, ...]),
#   'timestamp': array([1000000, 2000000, ...]),  # ps
#   'samples': array([[100.1, ...], ...]),
#   'baseline': array([100.15, ...]),
# }
```

## 适配器在数据流中的作用

### 完整数据流

```
┌─────────────────────────────────────────────────────────────┐
│ 1. 原始 DAQ 文件                                             │
│    CH0_0.CSV, CH0_1.CSV, CH1_0.CSV, ...                    │
└─────────────────────────────────────────────────────────────┘
                    ↓ DAQAdapter.scan_run()
┌─────────────────────────────────────────────────────────────┐
│ 2. 文件分组                                                  │
│    {0: [CH0_0.CSV, CH0_1.CSV], 1: [CH1_0.CSV, ...]}       │
└─────────────────────────────────────────────────────────────┘
                    ↓ DAQAdapter.load_channel()
┌─────────────────────────────────────────────────────────────┐
│ 3. 原始 NumPy 数组                                           │
│    array([[0, 0, 1000, ..., 100.1, 100.2, ...],            │
│           [0, 0, 2000, ..., 100.3, 100.4, ...]])           │
└─────────────────────────────────────────────────────────────┘
                    ↓ DAQAdapter.extract_and_convert()
┌─────────────────────────────────────────────────────────────┐
│ 4. 结构化数据字典                                            │
│    {'board': [...], 'channel': [...],                      │
│     'timestamp': [...], 'samples': [...]}                  │
└─────────────────────────────────────────────────────────────┘
                    ↓ WaveformStruct (使用 FormatSpec)
┌─────────────────────────────────────────────────────────────┐
│ 5. 结构化数组 (RECORD_DTYPE)                                │
│    array([(100.15, nan, 1000000, 800, 0, [100.1, ...]),   │
│           (100.18, nan, 2000000, 800, 0, [100.3, ...])],   │
│          dtype=[('baseline', 'f8'),                         │
│                 ('baseline_upstream', 'f8'),                │
│                 ('timestamp', 'i8'), ...])                  │
└─────────────────────────────────────────────────────────────┘
                    ↓ 后续插件处理
┌─────────────────────────────────────────────────────────────┐
│ 6. 特征提取、Hit 检测、事件重建等                            │
└─────────────────────────────────────────────────────────────┘
```

## 适配器的具体应用位置

### 1. RawFilesPlugin (原始文件扫描)

**位置**: `waveform_analysis/core/plugins/builtin/cpu/raw_files.py`

**作用**: 使用适配器扫描目录，获取文件列表

```python
class RawFilesPlugin(Plugin):
    provides = "raw_files"

    def compute(self, context, run_id, **kwargs):
        daq_adapter = context.get_config(self, "daq_adapter")
        adapter = get_adapter(daq_adapter)

        # 使用适配器扫描目录
        channel_files = adapter.scan_run(data_root, run_id)

        # 返回按通道分组的文件路径
        return [[str(f) for f in files] for files in channel_files.values()]
```

### 2. WaveformsPlugin (波形加载)

**位置**: `waveform_analysis/core/plugins/builtin/cpu/waveforms.py`

**作用**: 使用适配器读取文件，加载波形数据

```python
class WaveformsPlugin(Plugin):
    provides = "waveforms"
    depends_on = ["raw_files"]

    def compute(self, context, run_id, **kwargs):
        raw_files = context.get_data(run_id, "raw_files")
        daq_adapter = context.get_config(self, "daq_adapter")
        adapter = get_adapter(daq_adapter)

        waveforms = []
        for channel_files in raw_files:
            # 使用适配器的 FormatReader 读取文件
            data = adapter.format_reader.read_files(channel_files)
            waveforms.append(data)

        return waveforms
```

### 3. StWaveformsPlugin (波形结构化)

**位置**: `waveform_analysis/core/plugins/builtin/cpu/st_waveforms.py`

**作用**: 使用适配器的 FormatSpec 配置 WaveformStruct

```python
class StWaveformsPlugin(Plugin):
    provides = "st_waveforms"
    depends_on = ["waveforms"]

    def compute(self, context, run_id, **kwargs):
        waveforms = context.get_data(run_id, "waveforms")
        daq_adapter = context.get_config(self, "daq_adapter")

        # 从适配器获取格式规范
        config = WaveformStructConfig.from_adapter(daq_adapter)

        # 使用格式规范创建 WaveformStruct
        # FormatSpec 告诉 WaveformStruct:
        # - 哪一列是 timestamp
        # - 哪些列是 baseline 计算范围
        # - 时间戳单位是什么
        # - 波形数据从哪一列开始
        waveform_struct = WaveformStruct(waveforms, config=config)

        return waveform_struct.structure_waveforms()
```

### 4. WaveformStruct (核心处理)

**位置**: `waveform_analysis/core/processing/waveform_struct.py`

**作用**: 使用 FormatSpec 的列映射和单位信息

```python
def _structure_waveform(self, waves, ...):
    # 从配置获取列映射
    cols = self.config.format_spec.columns

    # 使用列映射提取数据
    timestamps = waves[:, cols.timestamp].astype(np.int64)
    baseline_vals = np.mean(
        waves[:, cols.baseline_start:cols.baseline_end],
        axis=1
    )
    wave_data = waves[:, cols.samples_start:cols.samples_end]

    # 使用时间戳单位转换
    timestamp_scale = self.config.format_spec.get_timestamp_scale_to_ps()
    timestamps = timestamps * timestamp_scale

    # 填充结构化数组
    waveform_structured["baseline"] = baseline_vals
    waveform_structured["timestamp"] = timestamps
    waveform_structured["wave"] = wave_data
```

## 内置适配器

### 1. VX2730 适配器

**设备**: CAEN VX2730 数字化仪

**格式特点**:
- 文件格式: CSV (分号分隔)
- 时间戳单位: 皮秒 (ps)
- 采样率: 500 MHz
- 采样点数: 800
- 列布局: `BOARD;CHANNEL;TIMETAG;...;SAMPLES[7:]`
- 目录结构: `DAQ/{run_name}/RAW/*.CSV`

**使用**:
```python
from waveform_analysis.utils.formats import get_adapter

adapter = get_adapter("vx2730")
data = adapter.load_channel("DAQ", "run_001", channel=0)
```

### 2. V1725 适配器

**设备**: CAEN V1725 数字化仪 (DAW_DEMO 二进制格式)

**格式特点**:
- 文件格式: 二进制 (.bin)
- 时间戳单位: 纳秒 (ns)
- 采样率: 250 MHz
- 文件模式: `*.bin`
- 目录结构: `{run_name}/RAW/*.bin`
- 特殊处理: 多通道数据存储在单个 .bin 文件中

**二进制格式解析**:
- Event Header (16 bytes): 包含通道掩码
- Channel Header (12 bytes): 时间戳、基线、截断标志
- Waveform Data: int16 数组

**使用**:
```python
adapter = get_adapter("v1725")
data = adapter.load_channel(".", "run_001", channel=0)
```

## 自定义适配器

### 创建自定义适配器的步骤

#### 1. 定义格式规范
```python
from waveform_analysis.utils.formats import (
    FormatSpec, ColumnMapping, TimestampUnit
)

MY_SPEC = FormatSpec(
    name="my_daq_csv",
    columns=ColumnMapping(
        board=0,
        channel=1,
        timestamp=3,      # 时间戳在第 3 列
        samples_start=10, # 波形从第 10 列开始
        baseline_start=10,
        baseline_end=50,
    ),
    timestamp_unit=TimestampUnit.NANOSECONDS,  # 纳秒
    delimiter=",",                              # 逗号分隔
    header_rows_first_file=1,
    expected_samples=1000,
    sampling_rate_hz=1e9,  # 1 GHz
)
```

#### 2. 创建读取器（可选，使用通用读取器）
```python
from waveform_analysis.utils.formats import GenericCSVReader

reader = GenericCSVReader(MY_SPEC)
```

#### 3. 定义目录布局
```python
from waveform_analysis.utils.formats import DirectoryLayout

MY_LAYOUT = DirectoryLayout(
    name="my_daq",
    raw_subdir="data",           # 原始数据在 data/ 子目录
    file_pattern="ch*.csv",      # 文件名模式
    channel_pattern=r"ch(\d+)",  # 从文件名提取通道号
)
```

#### 4. 创建并注册适配器
```python
from waveform_analysis.utils.formats import DAQAdapter, register_adapter

my_adapter = DAQAdapter(
    name="my_daq",
    format_reader=reader,
    directory_layout=MY_LAYOUT,
)

register_adapter(my_adapter)
```

#### 5. 使用自定义适配器
```python
from waveform_analysis.utils.formats import get_adapter

adapter = get_adapter("my_daq")
data = adapter.load_channel("data_root", "run_001", channel=0)
```

## 适配器的优势

### 1. 解耦设备依赖
- WaveformStruct 不再硬编码 VX2730 的列索引
- 可以轻松支持新的 DAQ 设备
- 修改格式不需要改动核心代码

### 2. 统一接口
- 所有 DAQ 设备使用相同的 API
- 插件代码与具体设备无关
- 便于测试和维护

### 3. 灵活配置
- 通过配置文件切换不同设备
- 支持同一设备的不同版本
- 可以动态注册新格式

### 4. 自动单位转换
- 自动处理不同的时间戳单位
- 统一转换为内部标准单位 (ps 或 ns)
- 避免单位错误

### 5. 目录结构抽象
- 支持不同的目录组织方式
- 自动扫描和分组文件
- 处理复杂的文件命名规则

## 配置示例

### 在 Context 中使用
```python
from waveform_analysis.core.context import Context

ctx = Context()

# 配置使用 VX2730 适配器
ctx.set_config({
    "daq_adapter": "vx2730",
    "data_root": "DAQ",
})

# 所有插件自动使用 VX2730 格式
st_waveforms = ctx.get_data("run_001", "st_waveforms")
```

### 切换到不同设备
```python
# 只需修改配置，无需改动代码
ctx.set_config({
    "daq_adapter": "v1725",  # 切换到 V1725
    "data_root": ".",
})

# 相同的代码，不同的设备
st_waveforms = ctx.get_data("run_001", "st_waveforms")
```

## 总结

适配器系统通过三层架构（FormatSpec + FormatReader + DirectoryLayout）提供了灵活、可扩展的 DAQ 数据处理框架。它在数据流的最前端工作，负责：

1. **文件发现**: 扫描目录，按通道分组文件
2. **数据读取**: 根据格式规范读取和解析文件
3. **单位转换**: 统一时间戳和其他物理量的单位
4. **数据提取**: 从原始数据中提取各个字段
5. **配置传递**: 将格式信息传递给 WaveformStruct

这使得整个系统可以轻松支持不同的 DAQ 设备，而无需修改核心处理逻辑。
