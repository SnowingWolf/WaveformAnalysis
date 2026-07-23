---
schema_version: 1
document_type: "plugin_reference"
profile: "agent"
provides: "records"
plugin_class: "RecordsPlugin"
module: "waveform_analysis.core.plugins.builtin.cpu.records"
version: "0.14.1"
summary: "Build records (event index table) from the shared internal records bundle."
depends_on: []
output_kind: "structured_array"
generated: true
---
# records

## Overview

Build records (event index table) from the shared internal records bundle.
| Item | Value |
| --- | --- |
| Provides | `records` |
| Plugin Class | `RecordsPlugin` |
| Module | `waveform_analysis.core.plugins.builtin.cpu.records` |
| Version | `0.14.1` |
| Category | 记录处理 |
| Accelerator | CPU (NumPy/SciPy) |
| Output Kind | `structured_array` |

| Dependency | Version Constraint | Resolution | Required Fields | Description |
| --- | --- | --- | --- | --- |
| - | - | - | - | No declared inputs. |
### How It Works


## Configuration

| Name | Type | Default | Unit | Tracked | Deprecated | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `daq_adapter` | `str` | `vx2730` | - | yes | no | DAQ adapter name for records bundle (e.g., 'vx2730', 'v1725'). |
| `channel_workers` | `any` | `16` | - | no | no | Workers for channel-level waveform loading. |
| `channel_executor` | `str` | `process` | - | no | no | Executor type for channel-level loading and records merge: 'thread' or 'process'. |
| `n_jobs` | `int` | `16` | - | no | no | Workers per channel for file-level parsing; V1725 None=auto caps file readers at 4. |
| `use_process_pool` | `bool` | `True` | - | no | no | Use a process pool for file-level parsing (False=thread pool). |
| `chunksize` | `int` | `None` | - | no | no | CSV read chunk size; None reads full file (PyArrow if available). |
| `parse_engine` | `str` | `auto` | - | no | no | CSV engine: auto \| polars \| pyarrow \| pandas |
| `records_part_size` | `int` | `250000` | - | yes | no | Max events per records shard; <=0 disables sharding. |
| `v1725_part_size` | `int` | `20000` | - | yes | no | Max V1725 waves per per-file records shard; <=0 uses one shard per file. |
| `keep_on_disk` | `any` | `True` | - | yes | no | Keep merged records bundle disk-backed. None defaults to True for V1725 and False otherwise. |
| `memory_budget_gb` | `float` | `50.0` | - | yes | no | Memory budget in GB for in-memory records bundle materialization. |
| `dt` | `int` | `None` | - | yes | no | Sample interval in ns for records.dt (defaults to adapter rate or 1ns). |
| `baseline_samples` | `any` | `None` | - | yes | no | Baseline range: int (sample count from adapter start) or tuple (start, end) relative to samples_start. JSON lists like [0, 800] are also accepted. None=adapter default. |
| `input_source` | `str` | `raw_files` | - | yes | no | Input source for records bundle: 'raw_files' or 'st_waveforms'. Use 'st_waveforms' for the materialized waveform path. |
## Output

structured_array output with fields: timestamp, pid, board, channel, baseline, baseline_upstream, polarity, record_id, ....

| Field | DType | Unit | Meaning |
| --- | --- | --- | --- |
| `timestamp` | `int64` | - | - |
| `pid` | `int32` | - | - |
| `board` | `int16` | - | - |
| `channel` | `int16` | - | - |
| `baseline` | `float64` | - | - |
| `baseline_upstream` | `float64` | - | - |
| `polarity` | `<U8` | - | - |
| `record_id` | `int64` | - | - |
| `dt` | `int32` | - | - |
| `trigger_type` | `int16` | - | - |
| `flags` | `uint32` | - | - |
| `wave_offset` | `int64` | - | - |
| `event_length` | `int32` | - | - |
| `time` | `int64` | - | - |
## Usage

### Minimal Example

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import RecordsPlugin

ctx = Context(config={"data_root": "DAQ"})
ctx.register(RecordsPlugin())
data = ctx.get_data("run_001", "records")
```

## Operational Notes

### Behavior

### Failure Modes

- Dependency data, configuration, or output contract validation may fail explicitly.
### Downstream Impact

Consumers: `records_asymmetry_mask`, `records_detector_mask`, `records_veto_mask`, `wave_pool_filtered`

## Maintenance

### Change Playbook

1. Keep `provides` and dependency semantics stable or update all consumers.
2. Bump `version` for behavior, configuration, or output contract changes.
3. Regenerate auto, agent, and web references after metadata changes.
### Validation

```bash
waveform-docs generate plugins-agent --plugin records
waveform-docs check coverage --strict --fail-on-warning
```
