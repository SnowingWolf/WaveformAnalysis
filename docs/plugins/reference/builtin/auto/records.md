# RecordsPlugin

> Build records (event index table) from the shared internal records bundle.

## Overview

| Property | Value |
|----------|-------|
| **Provides** | `records` |
| **Version** | `0.14.1` |
| **Category** | 记录处理 |
| **Accelerator** | CPU (NumPy/SciPy) |
| **Streaming** | No |
| **Side Effect** | No |

## Dependencies

This plugin has no dependencies.

## Configuration Options

| Option | Type | Default | Units | Description |
|--------|------|---------|-------|-------------|
| `daq_adapter` | `str` | `vx2730` | - | DAQ adapter name for records bundle (e.g., 'vx2730', 'v1725'). |
| `channel_workers` | `any` | `16` | - | Workers for channel-level waveform loading. |
| `channel_executor` | `str` | `process` | - | Executor type for channel-level loading and records merge: 'thread' or 'process'. |
| `n_jobs` | `int` | `16` | - | Workers per channel for file-level parsing; V1725 None=auto caps file readers at 4. |
| `use_process_pool` | `bool` | `True` | - | Use a process pool for file-level parsing (False=thread pool). |
| `chunksize` | `int` | `None` | - | CSV read chunk size; None reads full file (PyArrow if available). |
| `parse_engine` | `str` | `auto` | - | CSV engine: auto | polars | pyarrow | pandas |
| `records_part_size` | `int` | `250000` | - | Max events per records shard; <=0 disables sharding. |
| `v1725_part_size` | `int` | `20000` | - | Max V1725 waves per per-file records shard; <=0 uses one shard per file. |
| `keep_on_disk` | `any` | `True` | - | Keep merged records bundle disk-backed. None defaults to True for V1725 and False otherwise. |
| `memory_budget_gb` | `float` | `50.0` | - | Memory budget in GB for in-memory records bundle materialization. |
| `dt` | `int` | `None` | - | Sample interval in ns for records.dt (defaults to adapter rate or 1ns). |
| `baseline_samples` | `any` | `None` | - | Baseline range: int (sample count from adapter start) or tuple (start, end) relative to samples_start. JSON lists like [0, 800] are also accepted. None=adapter default. |
| `input_source` | `str` | `raw_files` | - | Input source for records bundle: 'raw_files' or 'st_waveforms'. Use 'st_waveforms' for the materialized waveform path. |


## Output Schema

**Output Type**: `structured_array`

| Field | Type | Units | Description |
|-------|------|-------|-------------|
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

## Usage Example

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import RecordsPlugin

# Create context and register plugin
ctx = Context(config={"data_root": "DAQ"})
ctx.register(RecordsPlugin())

# Configure plugin (optional)
ctx.set_config({
    "daq_adapter": 'vx2730',
    "channel_workers": 16,
    "channel_executor": 'process',
}, plugin_name="records")

# Get data
data = ctx.get_data("run_001", "records")
```

## Module

- **Module Path**: `waveform_analysis.core.plugins.builtin.cpu.records`

---

*This documentation was auto-generated from plugin metadata.*
