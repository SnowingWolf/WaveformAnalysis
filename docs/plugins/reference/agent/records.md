---
schema_version: 1
document_type: "plugin_reference"
profile: "agent"
provides: "records"
plugin_class: "RecordsPlugin"
module: "waveform_analysis.core.plugins.builtin.records.plugin"
version: "0.14.2"
summary: "Build records (event index table) from the shared internal records bundle."
depends_on: []
output_kind: "structured_array"
generated: true
---
# records

## Overview

Build records (event index table) from the shared internal records bundle.
RecordsPlugin 是分析链最底层的基础插件，把共享的 RecordsBundle / RecordsBundleRef （由 raw_files 或 st_waveforms 构建）产出的记录元数据暴露为正式的 `records` 结构化数组。每条记录对应一次事件，包含时间戳、板卡/通道、基线、极性、触发类型、dt，以及指向 wave_pool 的 `wave_offset` 与 `event_length` 等关键索引字段。

records 是绝大多数 records-backed 产物的源头：波形池的切片访问、通道角色掩码、不对称性筛选、滤波波形池与 peaklet 波形还原等都从 records 的行结构与字段约定取得语义。该插件不重复读取原始波形，而是复用同一份内存或磁盘 bundle（单分片直接 memmap records_path，多分片仅合并元数据视图），保证整条链共享一致的记录视图。

插件通过 `_RecordsBundlePluginBase` 共享配置源，并支持 `input_source` 在 raw_files 与 st_waveforms 之间切换（V1725 仅支持 raw_files）；`resolve_depends_on` 按所选输入源动态声明上游依赖。

| Item | Value |
| --- | --- |
| Provides | `records` |
| Plugin Class | `RecordsPlugin` |
| Module | `waveform_analysis.core.plugins.builtin.records.plugin` |
| Version | `0.14.2` |
| Category | 记录处理 |
| Output Kind | `structured_array` |

| Dependency | Version Constraint | Resolution | Required Fields | Description |
| --- | --- | --- | --- | --- |
| - | - | - | - | No declared inputs. |
### How It Works

1. 解析共享 bundle：调用 `get_records_bundle(context, run_id)` 获取（必要时构建）本 run 的 RecordsBundle / RecordsBundleRef。
2. 选择元数据视图：单分片 `RecordsBundleRef` 时直接 memmap `records_path`，多分片时通过 `get_records_view()` 仅合并 records 元数据（不载入 wave_pool），内存 bundle 直接返回 `bundle.records`。
3. 返回结果：输出按行对齐的 `RECORDS_DTYPE` 元数据数组，行序即后续 `record_id` 对齐约定。

## Configuration

| Name | Type | Default | Unit | Tracked | Deprecated | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `daq_adapter` | `str` | `vx2730` | - | yes | no | DAQ 适配器名称（vx2730/v1725 等），决定 bundle 的解析路径与默认 dt。 |
| `channel_workers` | `any` | `16` | - | no | no | Workers for channel-level waveform loading. |
| `channel_executor` | `str` | `process` | - | no | no | Executor type for channel-level loading and records merge: 'thread' or 'process'. |
| `n_jobs` | `int` | `16` | - | no | no | Workers per channel for file-level parsing; V1725 None=auto caps file readers at 4. |
| `use_process_pool` | `bool` | `True` | - | no | no | Use a process pool for file-level parsing (False=thread pool). |
| `chunksize` | `int` | `None` | - | no | no | CSV read chunk size; None reads full file (PyArrow if available). |
| `parse_engine` | `str` | `auto` | - | no | no | CSV engine: auto \| polars \| pyarrow \| pandas |
| `records_part_size` | `int` | `250000` | - | yes | no | Max events per records shard; <=0 disables sharding. |
| `v1725_part_size` | `int` | `20000` | - | yes | no | V1725 每文件 records 分片的最大波形数；<=0 表示每文件一个分片。 |
| `keep_on_disk` | `any` | `True` | - | yes | no | 是否保持 bundle 磁盘驻留；None 时 V1725 默认 True、其余适配器默认 False。 |
| `memory_budget_gb` | `float` | `50.0` | - | yes | no | 内存驻留 records bundle 的内存预算（GB）。 |
| `dt` | `int` | `None` | - | yes | no | 采样间隔（ns），写回 records.dt；缺省取适配器采样率或 1ns。 |
| `baseline_samples` | `any` | `None` | - | yes | no | 基线范围：int（距适配器起始的采样数）或 (start, end) 元组，相对 samples_start。 |
| `input_source` | `str` | `raw_files` | - | yes | no | records bundle 输入源：'raw_files' 或 'st_waveforms'（V1725 仅支持 'raw_files'）。 |
## Output

structured_array output with fields: timestamp, pid, board, channel, baseline, baseline_upstream, polarity, record_id, ....

| Field | DType | Unit | Meaning |
| --- | --- | --- | --- |
| `timestamp` | `int64` | ps | ADC timestamp in picoseconds |
| `pid` | `int32` | None | Partition identifier used as a tie-breaker |
| `board` | `int16` | None | Hardware board index |
| `channel` | `int16` | None | Physical channel number |
| `baseline` | `float64` | ADC counts | Computed global waveform baseline |
| `baseline_upstream` | `float64` | ADC counts | Upstream baseline value from preceding processing |
| `polarity` | `<U8` | None | Hardware-truth signal polarity |
| `record_id` | `int64` | None | Sequential record identifier after sorting |
| `dt` | `int32` | ns | Sample interval in nanoseconds |
| `trigger_type` | `int16` | None | Trigger type code |
| `flags` | `uint32` | None | Bit field of record flags |
| `wave_offset` | `int64` | None | Starting index in wave_pool |
| `event_length` | `int32` | samples | Waveform length in samples |
| `time` | `int64` | ns | System time in nanoseconds |
## Usage

### Minimal Example

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.records import RecordsPlugin

ctx = Context(config={"data_root": "DAQ"})
ctx.register(RecordsPlugin())
data = ctx.get_data("run_001", "records")
```

## Operational Notes

### Behavior

- The plugin never re-parses raw waveforms itself; it only materializes the record metadata view from the shared bundle.
- Single-part `RecordsBundleRef` returns a memmap over `records_path` (zero-copy); multi-part falls back to a merged metadata-only view.
- `wave_offset` + `event_length` references into the `wave_pool` array (uint16), so `records` and `wave_pool` must stay index-consistent.
- Polarity and baseline enrichment are applied while the shared bundle is built, not inside this plugin's compute.
### Failure Modes

- 所选 `input_source` 非 'raw_files'/'st_waveforms' 时抛出 `ValueError`。
- V1725 使用 `input_source='st_waveforms'` 时抛出 `ValueError`（不支持该组合）。
- 上游 `raw_files` 数据缺失（非 list）时由共享 bundle 构建逻辑抛出 `ValueError`。
- 多分片 bundle 的元数据视图只合并 records、不合并 wave_pool，若下游误按 records 行取波形会越界——属消费方契约错误，本插件不单独拦截。
### Downstream Impact

Consumers: `peaklet_channels`, `peaklet_waveforms`, `records_asymmetry_mask`, `records_detector_mask`, `records_veto_mask`, `wave_pool_filtered`
- 行序与 `record_id` 语义的变更会影响所有 mask 类产物（其输出长度必须与 records 一致）以及 align 到 records 的派生数组。
- `wave_offset`/`event_length` 与 `wave_pool` 的索引一致性由下游切片访问共享，修改 records 布局需同步校验 `wave_pool_filtered` 与 `peaklet_waveforms`。

## Maintenance

### Change Playbook

1. RECORDS_DTYPE 字段或行序变化会级联影响 records 的 mask/滤波/peaklet 消费链，请同步运行对应定向测试并重新生成文档。
### Validation

```bash
waveform-docs generate plugins-agent --plugin records
waveform-docs check coverage --strict --fail-on-warning
```
