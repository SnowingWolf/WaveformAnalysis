# DAQ 适配器系统详解

## 概述

DAQ 适配器负责原始文件发现、格式解析和硬件元数据描述。`DAQAdapter` 组合 `FormatSpec`、
`FormatReader` 与 `DirectoryLayout`，插件通过全局 `daq_adapter` 选择输入解释。
规范导入入口为 `waveform_analysis.acquisition.formats`；旧 `waveform_analysis.utils.formats`
继续指向同一对象与注册表，并保留原有 `__module__` 身份。

## 快速开始

### 使用默认 VX2730 格式

```python
from waveform_analysis import Context
from waveform_analysis.plugins import profiles

ctx = Context(config={"data_root": "DAQ", "daq_adapter": "vx2730"})
ctx.register(*profiles.cpu_default())
records = ctx.get_data("run_001", "records")
wave_pool = ctx.get_data("run_001", "wave_pool")
```

`records` 保存事件元数据，`wave_pool` 保存连续采样点。访问波形使用
`waveform_analysis.core.data.records_view(ctx, run_id)`，以 `record_id` 查询。

### 显式指定适配器

推荐全局配置 `daq_adapter`，避免同一链路混用输入格式。自定义 adapter 应先注册再创建 Context。
显式插件配置优先于 adapter 推断，adapter 推断优先于插件默认值。

## 核心架构

### 三层架构

| 组件 | 职责 |
| --- | --- |
| `FormatSpec` | 列映射、采样率、原生时间戳单位与语义、文件格式信息 |
| `FormatReader` | 读取单文件、文件序列与分块数据，提取字段 |
| `DirectoryLayout` | 构造运行目录、匹配文件并按布局分组、排序分卷 |
| `DAQAdapter` | 组合以上组件，按记录中的硬件键提供原始数据访问 |

## 核心组件详解

### 1. FormatSpec (格式规范)

`ColumnMapping` 描述二维数组中的 board、channel、timestamp 和 samples 列。
`timestamp_unit` 与 `raw_timestamp_mode` 共同解释原生时间戳；不能只凭数值大小推断单位。
例如 V1725 使用 `SAMPLE_INDEX`，必须结合采样间隔换算。

### 2. FormatReader (格式读取器)

CSV/BIN 输出二维数组，V1725 输出带 `board`、`channel`、`timestamp`、`baseline`、`trunc`、
`wave` 的结构化数组，其中 `baseline` 为 float64、`wave` 为 object。原始读取保留这些格式差异。
`normalize_timestamp_to_ps()` 或 `extract_and_convert()` 是显式转换接口；加载方法不隐式换算时间戳。

### 3. DirectoryLayout (目录布局)

`scan_run(data_root, run_name)` 返回 `dict[int, list[Path]]`，组键只表达文件布局。
一个文件组可以包含多个板卡或通道，不能将组键、文件名或列表位置当作物理通道。
`scan_run_detailed()` 另保留路径、文件名与索引信息。

### 4. DAQAdapter (完整适配器)

```python
from waveform_analysis.acquisition.formats import get_adapter

adapter = get_adapter("vx2730_bin")
file_groups = adapter.scan_run("DAQ", "run_001")
raw = adapter.load_channel("DAQ", "run_001", channel=1, board=0)
for chunk in adapter.load_channel_generator(
    "DAQ", "run_001", channel=1, chunk_size=10, board=0
):
    print(len(chunk))
all_raw = adapter.load_all_channels("DAQ", "run_001", show_progress=False)
raw_0_1 = all_raw[(0, 1)]
```

公开加载签名：

```text
load_channel(data_root, run_name, channel, show_progress=False, *, board)
load_channel_generator(data_root, run_name, channel, chunk_size=10, *, board)
load_all_channels(data_root, run_name, *, show_progress=False)
```

两个单通道接口均要求显式关键字 `board`，并按事件内容的 `(board, channel)` 筛选。
所有加载方法保持读取器 dtype、二维或结构化布局、原生时间戳和通道内读取顺序。
`load_all_channels()` 返回 `dict[tuple[int, int], np.ndarray]`，不接受 `n_channels`，不填充缺失通道。

| 输入情况 | 单通道加载 / 生成器 | 全通道加载 |
| --- | --- | --- |
| 目录不存在 | `FileNotFoundError` | `FileNotFoundError` |
| 空运行或没有匹配硬件通道 | `ValueError`（生成器在迭代时抛出） | 空运行返回 `{}` |
| 有记录 | 原始数组 / 非空原始数组块 | 仅包含实际有记录的硬件键 |

`chunk_size` 必须为正，并传给读取器；CSV 可按文件分批，BIN 按读取器事件块分批。生成器耗尽所有候选文件仍无匹配记录时抛出 `ValueError`。

## 数据流程

正式原始输入链路为 `raw_files -> records / wave_pool -> records_view`。
`raw_files` 保持 `list[list[str]]` 文件组 schema；其组键语义不等同于硬件通道。
共享 records bundle 按格式解析输入，生成带硬件键的元数据表和对应波形池，并归一时间戳。

`st_waveforms` 是 VX2730 CSV 和 V1725 支持的结构化产物，CoMPASS BIN 不支持此产物。
V1725 与 CoMPASS BIN 的 records bundle 均仅支持 `input_source="raw_files"`，
不能改为 `input_source="st_waveforms"`。具体输入路由见
[插件适配器行为](ADAPTER_PLUGIN_BEHAVIOR.md)。

## 内置适配器

### 1. VX2730 适配器

`vx2730`：CoMPASS CSV，分号分隔，500 MHz，时间戳为 ps；默认匹配 `RAW/*.CSV`。
输出二维原始数组，以 `FormatSpec.columns` 解释元数据和采样列。
即使文件名包含 `CH<n>`，硬件筛选仍读取事件的 board/channel 列。

### 2. V1725 适配器

`v1725`：DAW_DEMO 二进制 `RAW/*.bin`，250 MHz，原生时间戳为 sample index。
结构化原始数组保留每条记录的板卡和通道；显式换算为 ps 时使用采样间隔。
规范分卷按整数索引排序，例如 `seg0, seg2, seg10`，不会按字符串排列为 `seg0, seg10, seg2`。

### 3. VX2730 CoMPASS BIN 适配器

`vx2730_bin`：CoMPASS 二进制列表，默认匹配 `RAW/*.BIN`，扩展名大小写不敏感；
500 MHz，输出二维 int64 原始数组，原生时间戳为 ps。
同一文件可包含多个硬件通道，分组 0 也不意味着物理通道 0。

读取、计数和流式读取共用分卷解析规则：

- 每卷自身有有效头部时独立解析并重置布局，包括间隔、反序输入和不同头部的文件。
- 无头续卷只能继承同目录、同命名 family 的已知连续前卷布局，数据偏移为 0。
  `name.BIN` 和 `name_0.BIN` 都表示第 0 卷；有头子集可从任意 N 卷锚定 N+1。
- 空中间卷仅在已建立布局且索引连续时推进锚点；空首卷不能建立布局。
- 损坏头部、事件截断和不一致的波形长度直接报错，不尝试静默降级解析。

`format_reader.count_total_rows()` 使用文件大小、头部和首事件 `n_samples` 验证布局与对齐，
不是逐事件完整性检查。实际读取还会校验后续事件的 `n_samples`。

## 自定义适配器

### 创建自定义适配器的步骤

```python
from waveform_analysis import Context
from waveform_analysis.acquisition.formats import (
    ColumnMapping, DAQAdapter, DirectoryLayout, FormatSpec,
    GenericCSVReader, TimestampUnit, register_adapter,
)

spec = FormatSpec(
    name="my_csv",
    columns=ColumnMapping(board=0, channel=1, timestamp=3, samples_start=10),
    timestamp_unit=TimestampUnit.NANOSECONDS,
    delimiter=",",
    sampling_rate_hz=500e6,
)
layout = DirectoryLayout(
    name="my_layout", raw_subdir="data",
    file_glob_pattern="*.csv", channel_regex=r"channel(\d+)",
)
register_adapter(DAQAdapter("my_adapter", GenericCSVReader(spec), layout))
ctx = Context(config={"data_root": "DAQ", "daq_adapter": "my_adapter"})
```

实际文件必须符合列映射和头部配置。注册表是进程内状态，新进程需重新注册自定义格式。

## 配置示例

### 在 Context 中使用

```python
print(ctx.get_adapter_info())
ctx.show_resolved_config("records")  # 需先注册对应插件
```

`AdapterInfo.from_adapter(name)` 与 `get_adapter_info(name)` 每次读取当前注册对象，复用
`AdapterInfo.from_adapter_object(adapter)` 提取逻辑，不保存全局元数据缓存。
未知名称返回 `None`；已注册对象的元数据错误直接传播。

### 切换到不同设备

替换同名 adapter 的格式规范后，应新建 Context。注册表不会通知已有 Context 或失效其配置与 lineage，
不支持对既有 Context 热替换格式。正常配置变更仍通过 `ctx.set_config(...)` 完成。

## 最佳实践

硬件唯一键始终使用 `(board, channel)`，配置文件推荐写作 `"board:channel"`。
`channel_metadata` 只保存硬件事实或兼容信息，不决定插件行为。
校验文件发现、原始读取和正式 records/wave_pool 三个层次，不能只凭文件计数判断数据完整性。

## 故障排除

缺目录与无匹配记录是不同错误，先检查 `adapter.get_raw_path(data_root, run_name)` 和事件硬件键。
不要将 `scan_run()` 返回的文件组数量描述为真实通道数量。
排查时间戳异常时检查 `timestamp_unit`、`raw_timestamp_mode` 与采样率，而非猜测数量级。

## API 迁移

| 旧调用 | 当前调用 |
| --- | --- |
| `load_channel(root, run, channel)` | `load_channel(root, run, channel, board=board)` |
| `load_channel_generator(root, run, channel)` | `load_channel_generator(root, run, channel, board=board)` |
| `load_all_channels(..., n_channels=N)` 及列表下标 | 删除 `n_channels`，使用字典键 `(board, channel)`，显式处理缺失键 |
| `get_adapter_info(..., use_cache=...)` | 删除 `use_cache` 参数 |
| `clear_adapter_info_cache()` | 删除清理调用；同名格式替换后新建 Context |

## 相关文档

- [适配器与插件行为](ADAPTER_PLUGIN_BEHAVIOR.md)
- [配置与适配器推断](../../features/context/CONFIGURATION.md#适配器推断)
- [数据产物与波形访问](../../architecture/DATA_PRODUCTS.md)
