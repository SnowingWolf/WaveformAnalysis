---
schema_version: 2
document_type: "plugin_reference"
profile: "agent"
provides: "st_waveforms"
plugin_class: "WaveformsPlugin"
module: "waveform_analysis.core.plugins.builtin.st_waveforms.plugin"
version: "0.10.0"
summary: "Extract waveforms from raw CSV files and structure them into NumPy structured arrays."
depends_on: []
declared_depends_on: []
resolved_depends_on: ["raw_files"]
dependency_profile: "documentation-default-v1"
dependency_profile_values: {"daq_adapter": "vx2730", "use_filtered": false, "wave_source": "records"}
dependency_config_keys: ["daq_adapter", "use_upstream_baseline"]
output_kind: "structured_array"
execution_kind: "static"
narrative_source: "source"
narrative_source_reason: null
source_fingerprint: "18b2f23c8e21d3471d1026c58a149583384988e0aa0c0742162d33ccd8922821"
generated: true
---
# st_waveforms

## Overview

Extract waveforms from raw CSV files and structure them into NumPy structured arrays.
Plugin to extract and structure waveforms from raw files.

合并了原来的 WaveformsPlugin 和 StWaveformsPlugin 功能： 1. 从原始 CSV 文件中提取波形数据 2. 将波形数据结构化为 NumPy 结构化数组（ST_WAVEFORM_DTYPE）

| Item | Value |
| --- | --- |
| Provides | `st_waveforms` |
| Plugin Class | `WaveformsPlugin` |
| Module | `waveform_analysis.core.plugins.builtin.st_waveforms.plugin` |
| Version | `0.10.0` |
| Category | 波形处理 |
| Output Container | `structured_array` |
| Execution Mode | `static` |
| Save Policy | `always` |
| Uses Run Config | yes |
| Timeout | `none` |
| Side Effect | no |
| Narrative Source | `source` |
| Source Fingerprint | `18b2f23c8e21d3471d1026c58a149583384988e0aa0c0742162d33ccd8922821` |

### Dependencies

默认文档画像：`documentation-default-v1`（{"daq_adapter": "vx2730", "use_filtered": false, "wave_source": "records"}）。
该插件通过 `resolve_depends_on(context, run_id)` 动态解析依赖；可能影响解析的配置键：`daq_adapter`, `use_upstream_baseline`。

| Dependency | Version Constraint | Resolution | Required Fields | Description |
| --- | --- | --- | --- | --- |
| `raw_files` | - | dynamic-default | - | Scan the data directory and group raw CSV files by channel number. |
### How It Works

1. 从原始 CSV 文件中提取波形数据并结构化为 NumPy 结构化数组
2. 合并了原来的 WaveformsPlugin 和 StWaveformsPlugin 功能： 1. 读取并解析原始 CSV 文件，提取每个通道的波形数据 2. 将波形数据结构化为包含时间戳、基线、通道号和波形数据的结构化数组
3. 使用文件级扁平化并行处理： - 所有文件统一进入并行池解析（通过 n_jobs 控制） - 解析完成后按通道聚合

## Configuration

| Name | Type | Default | Unit | Tracked | Deprecated | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `daq_adapter` | `str` | `vx2730` | - | yes | no | DAQ adapter name (e.g., 'vx2730') |
| `wave_length` | `int` | `None` | - | yes | no | Waveform length (number of sampling points). Automatically detect from the data when None。 |
| `dt` | `int` | `None` | - | yes | no | Sampling interval in ns for st_waveforms.dt (None=auto from adapter). |
| `n_jobs` | `int` | `None` | - | no | no | Number of parallel workers for file-level processing (None=auto, uses min(total_files, 50)) |
| `use_process_pool` | `bool` | `False` | - | no | no | Whether to use process pool for file-level parallelism (False=thread pool for I/O, True=process pool for CPU-intensive) |
| `chunksize` | `int` | `None` | - | no | no | Chunk size for CSV reading (None=read entire file, enables PyArrow; set value to enable chunked reading but disables PyArrow) |
| `parse_engine` | `str` | `auto` | - | no | no | CSV engine: auto \| polars \| pyarrow \| pandas |
| `use_upstream_baseline` | `bool` | `False` | - | yes | no | Whether to use baseline from upstream plugin (requires 'baseline' data). |
| `baseline_samples` | `any` | `None` | - | yes | no | Baseline range: int (sample count from adapter start) or tuple (start, end) relative to samples_start. JSON lists like [0, 800] are also accepted. None=adapter default. |
| `streaming_mode` | `bool` | `False` | - | no | no | Enable streaming mode: read files and structure waveforms incrementally to reduce memory usage. When enabled, uses memmap for output to avoid full vstack memory overhead. |
## Output

structured_array output with fields: baseline, baseline_upstream, polarity, timestamp, record_id, dt, event_length, board, ....

| Field | DType | Unit | Meaning |
| --- | --- | --- | --- |
| `baseline` | `float64` | ADC counts | Computed global waveform baseline for this record |
| `baseline_upstream` | `float64` | ADC counts | Upstream baseline value from preceding processing, optional |
| `polarity` | `<U8` | None | Hardware-truth signal polarity: positive \| negative \| unknown |
| `timestamp` | `int64` | ps | ADC raw timestamp in picoseconds |
| `record_id` | `int64` | None | Sequential record identifier within the structured waveform array |
| `dt` | `int32` | ns | Sample interval in nanoseconds, aligned to time |
| `event_length` | `int32` | samples | Waveform length in samples |
| `board` | `int16` | None | Hardware board index |
| `channel` | `int16` | None | Physical channel number |
| `wave` | `('<i2', (1500,))` | ADC counts | ADC sample data as 1-D int16 array |
## Usage

### Minimal Example

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins import profiles

ctx = Context(config={"data_root": "DAQ", "daq_adapter": "vx2730"})
ctx.register(*profiles.cpu_default())
result = ctx.get_data("run_001", "st_waveforms")
```

示例使用 `run_id="run_001"` 和文档默认运行画像；真实数据路径与配置应以当前实验设置为准。

## Operational Notes

### Behavior

- Waveforms Plugin - 波形提取与结构化插件
- **加速器**: CPU (NumPy) **功能**: 从原始 CSV 文件中提取波形数据并结构化为 NumPy 结构化数组
### Failure Modes

- `st_waveforms` 的实际输入由 `resolve_depends_on(context, run_id)` 决定；默认画像之外的配置需要重新确认依赖是否可用。
- 动态依赖无法解析、所需配置不合法或上游产物缺失时，插件不会生成有效输出。
### Downstream Impact

直接消费者：`filtered_waveforms`、`waveform_width`
## Maintenance

### Change Playbook

1. 保持 `provides`、依赖和输出字段语义稳定，或同步所有下游消费者。
2. 行为、配置或输出契约改变时升级插件 `version`。
3. 修改插件源码后重新生成 Auto、Agent 和 HTML 参考。
### Validation

```bash
waveform-docs generate plugins-agent --plugin st_waveforms
waveform-docs check coverage --strict --fail-on-warning
```
