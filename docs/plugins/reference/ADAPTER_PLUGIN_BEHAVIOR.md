# 插件系统对不同适配器的行为差异

## 概述

全局 `daq_adapter` 支持三个内置格式：`vx2730`（CSV）、`vx2730_bin`（CoMPASS BIN）和
`v1725`（DAW_DEMO 二进制）。文件发现的分组与事件内的硬件通道是两个层次，真实唯一键为
`(board, channel)`。完整接口与迁移见 [DAQ 适配器系统详解](ADAPTER_SYSTEM_GUIDE.md)。

## 数据流对比

正式分析入口使用 `raw_files -> records / wave_pool`，通过 `records_view(ctx, run_id)` 访问波形。
共享 records bundle 完成原始解析、时间戳归一和元数据/波形池对齐，`records` 与 `wave_pool`
复用同一 bundle。原始 adapter 加载接口保留读取器的 dtype 与原生时间戳。

| 阶段 | vx2730 | vx2730_bin | v1725 |
| --- | --- | --- | --- |
| 文件 | `RAW/*.CSV` | `RAW/*.BIN`，扩展名大小写不敏感 | `RAW/*.bin` |
| 原始数组 | 二维数组 | 二维 int64 数组 | 含 board/channel 的结构化数组 |
| 原生时间戳 | ps | ps | sample index，需结合 250 MHz 采样率 |
| `raw_files` | 文件组列表 | 文件组列表，可单文件多通道 | 文件组列表，可单文件多通道 |
| 正式输出 | `records` + `wave_pool` | `records` + `wave_pool` | `records` + `wave_pool` |
| bundle 输入源 | `raw_files` 或 `st_waveforms` | 仅 `raw_files` | 仅 `raw_files` |

## 各插件行为

### 1. RawFilesPlugin - 文件扫描

`raw_files` 仍输出 `list[list[str]]`；schema 没有改为硬件键字典。
`adapter.scan_run()` 的字典组键由文件布局决定，不保证是物理通道；文件路径本身也不决定 board/channel。
V1725 分卷按整数索引排序（`seg0, seg2, seg10`）。

### 2. WaveformsPlugin - 原始波形加载

CSV 与 CoMPASS BIN 读取器返回二维原始数组。V1725 读取器返回结构化数组，其字段为
`board`、`channel`、`timestamp`、`baseline`（float64）、`trunc`、`wave`（object）。
这些原始差异由格式读取器和后续结构化/records bundle 路径解释，不能用旧的 boardless dtype 或
按 `range(n_channels)` 补空数组来描述当前硬件身份。

### 3. StWaveformsPlugin - 波形结构化

`st_waveforms` 使用适配器格式元数据解释原始输入；VX2730 CSV 和 V1725 支持此产物，
CoMPASS BIN 明确拒绝 `st_waveforms`。V1725 与 CoMPASS BIN 的 records bundle 均明确拒绝
`input_source="st_waveforms"`，须使用默认的原始文件路径。

### 4. RecordsPlugin / WavePoolPlugin - 正式分析入口

```python
from waveform_analysis import Context
from waveform_analysis.plugins import profiles
from waveform_analysis.core.data import records_view

ctx = Context(config={"data_root": "DAQ", "daq_adapter": "v1725"})
ctx.register(*profiles.cpu_default())
records = ctx.get_data("run_001", "records")
wave_pool = ctx.get_data("run_001", "wave_pool")
view = records_view(ctx, "run_001")
```

`records` 中的 `wave_offset` 与 `event_length` 索引 `wave_pool`，两者须保持一致。
板卡和通道取自事件元数据，不能用文件组编号或数组位置替代。

## 适配器加载接口

```python
from waveform_analysis.acquisition.formats import get_adapter

adapter = get_adapter("vx2730_bin")
raw = adapter.load_channel("DAQ", "run_001", channel=2, board=1)
chunks = adapter.load_channel_generator("DAQ", "run_001", channel=2, board=1)
all_raw = adapter.load_all_channels("DAQ", "run_001")
raw_1_2 = all_raw[(1, 2)]
```

三个格式均按实际记录的 `(board, channel)` 筛选。`board` 是单通道接口的必需关键字；
全通道接口返回硬件键字典，仅含实际有记录的通道，不再接受 `n_channels`。
缺目录抛出 `FileNotFoundError`；空运行或无匹配记录时单通道接口抛出 `ValueError`，
全通道接口在空运行返回 `{}`。生成器的错误在迭代时发生。

## 分卷与完整性边界

CoMPASS BIN 的读取、计数与流式读取共享头部/续卷解释规则。无头续卷须有同目录、同 family
的已知连续前卷；有效自身头部会独立建立布局。`name.BIN` 与 `name_0.BIN` 都是第 0 卷。
空首卷不能建立布局，已锚定的连续空中间卷才推进分卷状态；gap、反序和不同头部不触发静默回退。
损坏或截断文件直接报错。

计数检查文件大小、头部和首事件 `n_samples` 对齐，不是逐事件完整性证明。
实际读取会进一步检查后续事件的波形长度。

## 适配器配置的影响

显式配置高于 adapter 推断，高于插件默认值。`AdapterInfo` 从当前注册对象提取采样率、时间戳单位、
原生时间戳语义和采样间隔，不使用全局元数据缓存。未知名称返回 `None`，已注册元数据错误传播。
注册必须先于 Context 创建；同名格式替换后新建 Context，不支持通知已有 Context 热替换。

## 缓存与迁移

`raw_files` 版本为 `0.0.3`，分卷排序变更沿 lineage 传递到下游 `st_waveforms`。
共享原始输入路径的 `records` 与 `wave_pool` 版本均为 `0.17.0`。
这里没有更改 `raw_files` schema 或原始数组 dtype。

旧的 boardless 加载调用应补 `board=...`；全通道列表访问改为 `(board, channel)` 字典访问，
并显式处理缺失键。`use_cache` 参数与 `clear_adapter_info_cache` 已删除。
旧 `waveform_analysis.utils.formats` 别名和原有 `__module__` 身份继续保留。
