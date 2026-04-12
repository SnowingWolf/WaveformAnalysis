# WavePoolPlugin

> Build wave_pool from the shared internal records bundle.

## Overview

| Property | Value |
|----------|-------|
| **Provides** | `wave_pool` |
| **Version** | `0.9.0` |
| **Category** | 波形处理 |
| **Accelerator** | CPU (NumPy/SciPy) |
| **Streaming** | No |
| **Side Effect** | No |

## Dependencies

This plugin has no dependencies.

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
| `dt` | `int` | `None` | - | Sample interval in ns for records.dt (defaults to adapter rate or 1ns). |
| `baseline_samples` | `any` | `None` | - | Baseline range: int (sample count from adapter start) or tuple (start, end) relative to samples_start. JSON lists like [0, 800] are also accepted. None=adapter default. |


## Output Schema

**Output Type**: `array`

| Field | Type | Units | Description |
|-------|------|-------|-------------|
| `value` | `uint16` | - | - |

## Usage Example

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import WavePoolPlugin

# Create context and register plugin
ctx = Context(config={"data_root": "DAQ"})
ctx.register(WavePoolPlugin())

# Configure plugin (optional)
ctx.set_config({
    "daq_adapter": 'vx2730',
    "channel_workers": None,
    "channel_executor": 'thread',
}, plugin_name="wave_pool")

# Get data
data = ctx.get_data("run_001", "wave_pool")
```

## Module

- **Module Path**: `waveform_analysis.core.plugins.builtin.cpu.records`

---

*This documentation was auto-generated from plugin metadata.*
