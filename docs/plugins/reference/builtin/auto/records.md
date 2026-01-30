# RecordsPlugin

> Build records (event index table) from raw_files.

## Overview

| Property | Value |
|----------|-------|
| **Provides** | `records` |
| **Version** | `0.4.0` |
| **Category** | 记录处理 |
| **Accelerator** | CPU (NumPy/SciPy) |
| **Streaming** | No |
| **Side Effect** | No |

## Dependencies

This plugin depends on the following data:

- [`raw_files`](raw_files.md)

## Configuration Options

| Option | Type | Default | Units | Description |
|--------|------|---------|-------|-------------|
| `daq_adapter` | `str` | `vx2730` | - | DAQ adapter name for records bundle (e.g., 'vx2730', 'v1725'). |
| `channel_workers` | `any` | `None` | - | Workers for channel-level waveform loading (None=auto). |
| `channel_executor` | `str` | `thread` | - | Channel-level executor type: 'thread' or 'process'. |
| `n_jobs` | `int` | `None` | - | Workers per channel for file-level parsing (None=auto). |
| `use_process_pool` | `bool` | `False` | - | Use a process pool for file-level parsing (False=thread pool). |
| `chunksize` | `int` | `None` | - | CSV read chunk size; None reads full file (PyArrow if available). |
| `records_part_size` | `int` | `200000` | - | Max events per records shard; <=0 disables sharding. |
| `records_dt_ns` | `int` | `None` | - | Sample interval in ns (defaults to adapter rate or 1ns). |


## Output Schema

**Output Type**: `structured_array`

| Field | Type | Units | Description |
|-------|------|-------|-------------|
| `timestamp` | `int64` | - | - |
| `pid` | `int32` | - | - |
| `channel` | `int16` | - | - |
| `baseline` | `float64` | - | - |
| `baseline_upstream` | `float64` | - | - |
| `event_id` | `int64` | - | - |
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
    "channel_workers": None,
    "channel_executor": 'thread',
}, plugin_name="records")

# Get data
data = ctx.get_data("run_001", "records")
```

## Module

- **Module Path**: `waveform_analysis.core.plugins.builtin.cpu.records`

---

*This documentation was auto-generated from plugin metadata.*
