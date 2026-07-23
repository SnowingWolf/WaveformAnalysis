---
schema_version: 1
document_type: "plugin_reference"
profile: "agent"
provides: "st_waveforms"
plugin_class: "WaveformsPlugin"
module: "waveform_analysis.core.plugins.builtin.cpu.waveforms"
version: "0.10.0"
summary: "Extract waveforms from raw CSV files and structure them into NumPy structured arrays."
depends_on: []
output_kind: "structured_array"
generated: true
---
# st_waveforms

## Overview

Extract waveforms from raw CSV files and structure them into NumPy structured arrays.
| Item | Value |
| --- | --- |
| Provides | `st_waveforms` |
| Plugin Class | `WaveformsPlugin` |
| Module | `waveform_analysis.core.plugins.builtin.cpu.waveforms` |
| Version | `0.10.0` |
| Category | 波形处理 |
| Accelerator | CPU (NumPy/SciPy) |
| Output Kind | `structured_array` |

| Dependency | Version Constraint | Resolution | Required Fields | Description |
| --- | --- | --- | --- | --- |
| - | - | - | - | No declared inputs. |
### How It Works


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
| `baseline` | `float64` | - | - |
| `baseline_upstream` | `float64` | - | - |
| `polarity` | `<U8` | - | - |
| `timestamp` | `int64` | - | - |
| `record_id` | `int64` | - | - |
| `dt` | `int32` | - | - |
| `event_length` | `int32` | - | - |
| `board` | `int16` | - | - |
| `channel` | `int16` | - | - |
| `wave` | `('<i2', (1500,))` | - | - |
## Usage

### Minimal Example

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import WaveformsPlugin

ctx = Context(config={"data_root": "DAQ"})
ctx.register(WaveformsPlugin())
data = ctx.get_data("run_001", "st_waveforms")
```

## Operational Notes

### Behavior

- 从原始 CSV 文件中提取波形数据并结构化为 NumPy 结构化数组
- 合并了原来的 WaveformsPlugin 和 StWaveformsPlugin 功能： 1. 读取并解析原始 CSV 文件，提取每个通道的波形数据 2. 将波形数据结构化为包含时间戳、基线、通道号和波形数据的结构化数组
- 使用文件级扁平化并行处理： - 所有文件统一进入并行池解析（通过 n_jobs 控制） - 解析完成后按通道聚合
### Failure Modes

- Dependency data, configuration, or output contract validation may fail explicitly.
### Downstream Impact

Consumers: `filtered_waveforms`

## Maintenance

### Change Playbook

1. Keep `provides` and dependency semantics stable or update all consumers.
2. Bump `version` for behavior, configuration, or output contract changes.
3. Regenerate auto, agent, and web references after metadata changes.
### Validation

```bash
waveform-docs generate plugins-agent --plugin st_waveforms
waveform-docs check coverage --strict --fail-on-warning
```
