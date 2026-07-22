---
schema_version: 1
document_type: "plugin_reference"
profile: "auto"
provides: "wave_pool"
plugin_class: "WavePoolPlugin"
module: "waveform_analysis.core.plugins.builtin.cpu.records"
version: "0.14.1"
summary: "Build wave_pool from the shared internal records bundle."
depends_on: []
output_kind: "array"
generated: true
---
# wave_pool

## Overview

Build wave_pool from the shared internal records bundle.

| Item | Value |
| --- | --- |
| Provides | `wave_pool` |
| Plugin Class | `WavePoolPlugin` |
| Module | `waveform_analysis.core.plugins.builtin.cpu.records` |
| Version | `0.14.1` |
| Category | 波形处理 |
| Accelerator | CPU (NumPy/SciPy) |
| Output Kind | `array` |

| Dependency | Version Constraint | Resolution | Required Fields | Description |
| --- | --- | --- | --- | --- |
| - | - | - | - | - |
## Configuration

| Name | Type | Default | Unit | Tracked | Deprecated | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `daq_adapter` | `str` | `vx2730` | - | yes | no | DAQ adapter name for records bundle (e.g., 'vx2730', 'v1725'). |
| `channel_workers` | `any` | `None` | - | no | no | Workers for channel-level waveform loading (None=auto). |
| `channel_executor` | `str` | `thread` | - | no | no | Executor type for channel-level loading and records merge: 'thread' or 'process'. |
| `n_jobs` | `int` | `None` | - | no | no | Workers per channel for file-level parsing; V1725 None=auto caps file readers at 4. |
| `use_process_pool` | `bool` | `False` | - | no | no | Use a process pool for file-level parsing (False=thread pool). |
| `chunksize` | `int` | `None` | - | no | no | CSV read chunk size; None reads full file (PyArrow if available). |
| `parse_engine` | `str` | `auto` | - | no | no | CSV engine: auto \| polars \| pyarrow \| pandas |
| `records_part_size` | `int` | `250000` | - | yes | no | Max events per records shard; <=0 disables sharding. |
| `v1725_part_size` | `int` | `100000` | - | yes | no | Max V1725 waves per per-file records shard; <=0 uses one shard per file. |
| `keep_on_disk` | `any` | `None` | - | yes | no | Keep merged records bundle disk-backed. None defaults to True for V1725 and False otherwise. |
| `memory_budget_gb` | `float` | `50.0` | - | yes | no | Memory budget in GB for in-memory records bundle materialization. |
| `dt` | `int` | `None` | - | yes | no | Sample interval in ns for records.dt (defaults to adapter rate or 1ns). |
| `baseline_samples` | `any` | `None` | - | yes | no | Baseline range: int (sample count from adapter start) or tuple (start, end) relative to samples_start. JSON lists like [0, 800] are also accepted. None=adapter default. |
| `input_source` | `str` | `raw_files` | - | yes | no | Input source for records bundle: 'raw_files' or 'st_waveforms'. Use 'st_waveforms' for the materialized waveform path. |
## Output

| Field | DType | Unit | Meaning |
| --- | --- | --- | --- |
| `value` | `uint16` | - | - |
## Usage

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import WavePoolPlugin

ctx = Context(config={"data_root": "DAQ"})
ctx.register(WavePoolPlugin())
data = ctx.get_data("run_001", "wave_pool")
```
