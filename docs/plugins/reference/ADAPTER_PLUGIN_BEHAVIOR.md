# 插件系统对不同适配器的行为差异

## 概述

当前插件系统通过 `daq_adapter` 配置参数支持不同的 DAQ 设备。主要有两个内置适配器：[^source]
- **VX2730**: CSV 格式，每通道多文件
- **V1725**: 二进制格式，单文件多通道

插件系统在不同阶段对这两个适配器有不同的处理逻辑。

---

## 数据流对比

### VX2730 数据流（标准流程）

```
原始文件结构:
DAQ/run_001/RAW/
├── CH0_0.CSV    ← 通道 0, 文件 0
├── CH0_1.CSV    ← 通道 0, 文件 1
├── CH1_0.CSV    ← 通道 1, 文件 0
└── CH1_1.CSV    ← 通道 1, 文件 1

↓ RawFilesPlugin (使用 VX2730 适配器扫描)

raw_files = [
    ['CH0_0.CSV', 'CH0_1.CSV'],  # 通道 0
    ['CH1_0.CSV', 'CH1_1.CSV'],  # 通道 1
]

↓ WaveformsPlugin (标准 CSV 读取)

waveforms = [
    np.array([[...], [...]]),  # 通道 0 数据
    np.array([[...], [...]]),  # 通道 1 数据
]

↓ StWaveformsPlugin (使用 VX2730 FormatSpec)

st_waveforms = [
    structured_array_ch0,  # RECORD_DTYPE
    structured_array_ch1,
]
```

### V1725 数据流（特殊处理）

```
原始文件结构:
run_001/RAW/
└── wave_0.bin    ← 单个文件包含所有通道

↓ RawFilesPlugin (使用 V1725 适配器扫描)

raw_files = [
    ['wave_0.bin'],  # 通道 0 (实际文件相同)
    ['wave_0.bin'],  # 通道 1 (实际文件相同)
    ['wave_0.bin'],  # 通道 2 (实际文件相同)
]
注意: 所有通道指向同一个文件！

↓ WaveformsPlugin (V1725 特殊处理)

# 检测到 v1725，执行特殊逻辑:
# 1. 合并所有文件路径
# 2. 去重（因为都是同一个文件）
# 3. 使用 V1725Reader 读取二进制
# 4. 返回未分割的结构化数组

waveforms = structured_array (单个数组，包含所有通道)
# dtype: [('channel', 'i2'), ('timestamp', 'i8'),
#         ('baseline', 'i4'), ('trunc', 'b1'), ('wave', 'O')]

↓ StWaveformsPlugin (需要按通道分割)

# 问题: V1725 返回的是单个数组，不是按通道分组的列表
# 需要特殊处理！
```

---

## 插件行为详解

### 1. RawFilesPlugin - 文件扫描

**作用**: 扫描目录，返回按通道分组的文件列表

#### VX2730 行为
```python
# 配置
daq_adapter = "vx2730"

# 执行
adapter = get_adapter("vx2730")
channel_files = adapter.scan_run("DAQ", "run_001")
# 返回: {0: [Path('CH0_0.CSV'), Path('CH0_1.CSV')],
#        1: [Path('CH1_0.CSV'), Path('CH1_1.CSV')]}

# 转换为列表
raw_files = [
    ['DAQ/run_001/RAW/CH0_0.CSV', 'DAQ/run_001/RAW/CH0_1.CSV'],
    ['DAQ/run_001/RAW/CH1_0.CSV', 'DAQ/run_001/RAW/CH1_1.CSV'],
]
```

**关键点**:
- 每个通道有独立的文件列表
- 文件按索引排序
- 使用 VX2730_LAYOUT 的文件模式 `*CH*.CSV`

#### V1725 行为
```python
# 配置
daq_adapter = "v1725"

# 执行
adapter = get_adapter("v1725")
channel_files = adapter.scan_run(".", "run_001")

# V1725Adapter.scan_run() 特殊逻辑:
# 1. 尝试标准扫描（按通道分组）
# 2. 如果失败或为空，回退到单文件模式
# 3. 将所有 .bin 文件分配给通道 0

# 返回: {0: [Path('wave_0.bin')]}

# 转换为列表（假设有 3 个通道）
raw_files = [
    ['run_001/RAW/wave_0.bin'],  # 通道 0
    [],                           # 通道 1 (空)
    [],                           # 通道 2 (空)
]
```

**关键点**:
- V1725 的 .bin 文件包含所有通道数据
- 适配器无法从文件名判断通道
- 默认将文件分配给通道 0
- 其他通道为空列表

---

### 2. WaveformsPlugin - 波形加载

**作用**: 读取文件，提取波形数据

#### VX2730 行为（标准流程）
```python
# 输入
raw_files = [
    ['CH0_0.CSV', 'CH0_1.CSV'],
    ['CH1_0.CSV', 'CH1_1.CSV'],
]

# 执行标准 CSV 读取
from waveform_analysis.core.processing.loader import get_waveforms

waveforms = get_waveforms(
    raw_filess=raw_files,
    daq_adapter="vx2730",
    ...
)

# 内部流程:
# 1. 对每个通道并行处理
# 2. 每个通道内，并行读取多个 CSV 文件
# 3. 使用 pandas 读取 CSV (分号分隔)
# 4. 堆叠为 NumPy 数组

# 返回
waveforms = [
    np.array([[0, 0, 1000, ..., 100.1, 100.2, ...],  # 通道 0
              [0, 0, 2000, ..., 100.3, 100.4, ...]]),
    np.array([[0, 1, 1000, ..., 99.8, 99.9, ...],    # 通道 1
              [0, 1, 2000, ..., 100.0, 100.1, ...]]),
]
# 形状: List[np.ndarray], 每个数组 (n_events, n_columns)
```

**关键点**:
- 返回列表，每个元素是一个通道的数据
- 每个通道的数据是 2D NumPy 数组
- 列索引对应 VX2730_SPEC 的 ColumnMapping

#### V1725 行为（特殊处理）
```python
# 输入
raw_files = [
    ['wave_0.bin'],
    [],
    [],
]

# 检测到 v1725，执行特殊逻辑
if daq_adapter == "v1725":
    adapter = get_adapter("v1725")

    # 1. 合并所有文件路径
    files = []
    for group in raw_files:
        if group:
            files.extend(group)
    # files = ['wave_0.bin']

    # 2. 去重（因为可能多个通道指向同一文件）
    seen = set()
    file_list = []
    for path in files:
        if path not in seen:
            seen.add(path)
            file_list.append(path)
    # file_list = ['wave_0.bin']

    # 3. 使用 V1725Reader 读取二进制
    data = adapter.format_reader.read_files(file_list)

    # 4. 返回未分割的结构化数组
    return data

# 返回
waveforms = np.array([
    (0, 1000, 100, False, array([...])),  # 通道 0, 事件 0
    (0, 2000, 101, False, array([...])),  # 通道 0, 事件 1
    (1, 1000, 99, False, array([...])),   # 通道 1, 事件 0
    (1, 2000, 100, False, array([...])),  # 通道 1, 事件 1
    (2, 1000, 98, False, array([...])),   # 通道 2, 事件 0
], dtype=[('channel', 'i2'), ('timestamp', 'i8'),
          ('baseline', 'i4'), ('trunc', 'b1'), ('wave', 'O')])
# 形状: np.ndarray (单个结构化数组，包含所有通道)
```

**关键点**:
- **不返回列表，返回单个结构化数组**
- 所有通道的数据混合在一起
- 通过 `channel` 字段区分通道
- `wave` 字段是 object 类型（可变长度）

---

### 3. StWaveformsPlugin - 波形结构化

**作用**: 将原始数据转换为 RECORD_DTYPE 结构化数组

#### VX2730 行为（标准流程）
```python
# 输入
waveforms = [
    np.array([[0, 0, 1000, ..., 100.1, 100.2, ...]]),  # 通道 0
    np.array([[0, 1, 1000, ..., 99.8, 99.9, ...]]),    # 通道 1
]

# 执行
config = WaveformStructConfig.from_adapter("vx2730")
# config.format_spec = VX2730_SPEC
# - columns.timestamp = 2
# - columns.baseline_start = 7
# - columns.baseline_end = 47
# - columns.samples_start = 7
# - timestamp_unit = PICOSECONDS

waveform_struct = WaveformStruct(waveforms, config=config)
st_waveforms = waveform_struct.structure_waveforms()

# 内部处理:
# 1. 对每个通道调用 _structure_waveform()
# 2. 使用 columns 提取各列:
#    - timestamp = waves[:, 2]
#    - baseline = mean(waves[:, 7:47])
#    - wave = waves[:, 7:]
# 3. 转换时间戳单位: ps -> ps (scale = 1.0)
# 4. 填充 RECORD_DTYPE

# 返回
st_waveforms = [
    np.array([
        (100.15, nan, 1000000, 800, 0, [100.1, 100.2, ...]),
        (100.18, nan, 2000000, 800, 0, [100.3, 100.4, ...]),
    ], dtype=RECORD_DTYPE),  # 通道 0
    np.array([
        (99.85, nan, 1000000, 800, 1, [99.8, 99.9, ...]),
        (100.02, nan, 2000000, 800, 1, [100.0, 100.1, ...]),
    ], dtype=RECORD_DTYPE),  # 通道 1
]
```

**关键点**:
- 输入是列表，输出也是列表
- 每个通道独立处理
- 使用 VX2730_SPEC 的列映射

#### V1725 行为（当前问题）
```python
# 输入（来自 WaveformsPlugin）
waveforms = np.array([
    (0, 1000, 100, False, array([...])),  # 通道 0
    (1, 1000, 99, False, array([...])),   # 通道 1
    (2, 1000, 98, False, array([...])),   # 通道 2
], dtype=[('channel', 'i2'), ('timestamp', 'i8'), ...])

# 问题: WaveformStruct 期望输入是 List[np.ndarray]
# 但 V1725 返回的是单个结构化数组！

# 当前代码会出错:
waveform_struct = WaveformStruct(waveforms, config=config)
# TypeError: 期望 List[np.ndarray]，得到 np.ndarray

# 需要预处理: 按通道分割
channels = {}
for row in waveforms:
    ch = row['channel']
    if ch not in channels:
        channels[ch] = []
    channels[ch].append(row)

# 转换为列表格式
waveforms_list = [
    np.array(channels.get(ch, []), dtype=waveforms.dtype)
    for ch in range(max(channels.keys()) + 1)
]

# 然后才能传给 WaveformStruct
waveform_struct = WaveformStruct(waveforms_list, config=config)
```

**关键点**:
- **V1725 的输出格式与 WaveformStruct 的输入格式不匹配**
- 需要额外的转换步骤
- 当前代码可能缺少这个转换

---

## 关键差异总结

### 数据结构差异

| 阶段 | VX2730 | V1725 |
|------|--------|-------|
| **raw_files** | `List[List[str]]`<br>每通道独立文件列表 | `List[List[str]]`<br>所有通道指向同一文件 |
| **waveforms** | `List[np.ndarray]`<br>每通道一个 2D 数组 | `np.ndarray`<br>单个结构化数组 |
| **st_waveforms** | `List[np.ndarray]`<br>每通道一个结构化数组 | `List[np.ndarray]`<br>需要预处理分割 |

### 处理逻辑差异

#### VX2730（标准流程）
```python
# 1. 扫描: 每通道独立文件
raw_files = [['CH0_0.CSV', 'CH0_1.CSV'], ['CH1_0.CSV', 'CH1_1.CSV']]

# 2. 加载: 并行读取 CSV
waveforms = [ch0_array, ch1_array]

# 3. 结构化: 直接处理
st_waveforms = [ch0_structured, ch1_structured]
```

#### V1725（特殊处理）
```python
# 1. 扫描: 所有通道指向同一文件
raw_files = [['wave.bin'], [], []]

# 2. 加载: 特殊逻辑
if daq_adapter == "v1725":
    # 去重文件
    # 读取二进制
    # 返回单个结构化数组
    waveforms = single_structured_array

# 3. 结构化: 需要预处理
# 按 channel 字段分割
waveforms_list = split_by_channel(waveforms)
st_waveforms = [ch0_structured, ch1_structured, ch2_structured]
```

---

## 适配器配置的影响

### FormatSpec 的作用

#### VX2730_SPEC
```python
FormatSpec(
    name="vx2730_csv",
    columns=ColumnMapping(
        board=0,           # 第 0 列
        channel=1,         # 第 1 列
        timestamp=2,       # 第 2 列
        samples_start=7,   # 第 7 列开始是波形
        baseline_start=7,  # 前 40 个点计算基线
        baseline_end=47,
    ),
    timestamp_unit=TimestampUnit.PICOSECONDS,  # ps
    delimiter=";",
    expected_samples=800,
)
```

**影响**:
- WaveformStruct 知道从哪一列提取 timestamp
- 知道用哪些列计算 baseline
- 知道时间戳单位，自动转换

#### V1725_SPEC
```python
FormatSpec(
    name="v1725_bin",
    columns=ColumnMapping(),  # 空映射（二进制格式不需要）
    timestamp_unit=TimestampUnit.NANOSECONDS,  # ns
    file_pattern="*.bin",
    expected_samples=None,  # 可变长度
)
```

**影响**:
- 不使用列映射（二进制格式已解析）
- 时间戳单位是 ns，需要转换为 ps
- 波形长度可变

---

## 当前存在的问题

### 问题 1: V1725 数据格式不匹配

**现象**:
```python
# WaveformsPlugin 返回
waveforms = np.ndarray (单个结构化数组)

# StWaveformsPlugin 期望
waveforms = List[np.ndarray] (列表)
```

**解决方案**:
在 StWaveformsPlugin 中添加 V1725 检测和转换:
```python
def compute(self, context, run_id, **kwargs):
    waveforms = context.get_data(run_id, "waveforms")
    daq_adapter = context.get_config(self, "daq_adapter")

    # V1725 特殊处理
    if daq_adapter == "v1725":
        # 检查是否是单个结构化数组
        if isinstance(waveforms, np.ndarray) and waveforms.dtype.names:
            # 按通道分割
            waveforms = split_by_channel(waveforms)

    # 标准处理
    waveform_struct = WaveformStruct(waveforms, config=config)
    ...
```

### 问题 2: V1725 的 baseline 字段类型不匹配

**现象**:
```python
# V1725Reader 返回
dtype = [('baseline', 'i4'), ...]  # int32

# RECORD_DTYPE 期望
dtype = [('baseline', 'f8'), ...]  # float64
```

**解决方案**:
在转换时进行类型转换:
```python
waveforms_list[ch]['baseline'] = waveforms_list[ch]['baseline'].astype(np.float64)
```

### 问题 3: V1725 的 wave 字段是 object 类型

**现象**:
```python
# V1725Reader 返回
dtype = [('wave', 'O'), ...]  # object (可变长度)

# RECORD_DTYPE 期望
dtype = [('wave', 'f4', (800,)), ...]  # 固定长度 float32 数组
```

**解决方案**:
需要将 object 数组转换为固定长度数组:
```python
# 确定最大长度
max_len = max(len(w) for w in waveforms['wave'])

# 创建固定长度数组
fixed_waves = np.zeros((len(waveforms), max_len), dtype=np.float32)
for i, w in enumerate(waveforms['wave']):
    fixed_waves[i, :len(w)] = w
```

---

## 推荐的改进方案

### 方案 1: 在 WaveformsPlugin 中统一输出格式

**优点**: 所有适配器返回相同格式，下游插件无需特殊处理

```python
class WaveformsPlugin(Plugin):
    def compute(self, context, run_id, **kwargs):
        ...

        if daq_adapter == "v1725":
            # V1725 特殊处理
            data = adapter.format_reader.read_files(file_list)

            # 转换为标准格式: List[np.ndarray]
            waveforms = self._convert_v1725_to_standard(data)
            return waveforms

        # 标准处理
        return get_waveforms(...)

    def _convert_v1725_to_standard(self, data):
        """将 V1725 结构化数组转换为标准列表格式"""
        channels = {}
        for row in data:
            ch = row['channel']
            if ch not in channels:
                channels[ch] = []
            channels[ch].append(row)

        max_ch = max(channels.keys())
        return [
            np.array(channels.get(ch, []), dtype=data.dtype)
            for ch in range(max_ch + 1)
        ]
```

### 方案 2: 创建 V1725 专用插件链

**优点**: 清晰分离不同适配器的处理逻辑

```python
# V1725 专用插件
class V1725WaveformsPlugin(Plugin):
    provides = "waveforms"
    depends_on = ["raw_files"]

    def compute(self, context, run_id, **kwargs):
        # V1725 特定逻辑
        ...

class V1725StWaveformsPlugin(Plugin):
    provides = "st_waveforms"
    depends_on = ["waveforms"]

    def compute(self, context, run_id, **kwargs):
        # V1725 特定的结构化逻辑
        ...

# 根据配置选择插件链
from waveform_analysis.core.plugins import profiles

if daq_adapter == "v1725":
    plugins = v1725_plugins
else:
    plugins = profiles.cpu_default()
```

### 方案 3: 在适配器层统一接口

**优点**: 适配器负责返回统一格式，插件完全无感知

```python
class V1725Adapter(DAQAdapter):
    def load_all_channels(self, data_root, run_name, ...):
        # 读取二进制文件
        data = self.format_reader.read_files(...)

        # 按通道分割，返回标准格式
        return self._split_by_channel(data)

    def _split_by_channel(self, data):
        """将单个结构化数组分割为按通道分组的列表"""
        ...
```

---

## 总结

### 核心差异

1. **文件组织**:
   - VX2730: 每通道多文件
   - V1725: 单文件多通道


2. **数据格式**:
   - VX2730: CSV 文本
   - V1725: 二进制

3. **输出结构**:
   - VX2730: `List[np.ndarray]` (标准)
   - V1725: `np.ndarray` (结构化数组)

### 当前处理方式

- **RawFilesPlugin**: 两者都使用适配器扫描，但 V1725 返回重复的文件路径
- **WaveformsPlugin**: V1725 有特殊的 `if daq_adapter == "v1725"` 分支
- **StWaveformsPlugin**: 当前可能缺少 V1725 的转换逻辑

### 建议

推荐使用**方案 1**（在 WaveformsPlugin 中统一输出格式），因为：
- 改动最小
- 下游插件无需修改
- 保持插件系统的一致性
- 易于维护和扩展

[^source]: 来源：`waveform_analysis/core/plugins/builtin/cpu/waveforms.py`、`waveform_analysis/utils/formats/base.py`。
