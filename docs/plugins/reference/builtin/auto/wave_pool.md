# WavePoolPlugin

> Build wave_pool from the shared internal records bundle.

## Overview

| Property | Value |
|----------|-------|
| **Provides** | `wave_pool` |
| **Version** | `0.14.1` |
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
| `channel_executor` | `str` | `thread` | - | Executor type for channel-level loading and records merge: 'thread' or 'process'. |
| `n_jobs` | `int` | `None` | - | Workers per channel for file-level parsing; V1725 None=auto caps file readers at 4. |
| `use_process_pool` | `bool` | `False` | - | Use a process pool for file-level parsing (False=thread pool). |
| `chunksize` | `int` | `None` | - | CSV read chunk size; None reads full file (PyArrow if available). |
| `parse_engine` | `str` | `auto` | - | CSV engine: auto | polars | pyarrow | pandas |
| `records_part_size` | `int` | `250000` | - | Max events per records shard; <=0 disables sharding. |
| `v1725_part_size` | `int` | `100000` | - | Max V1725 waves per per-file records shard; <=0 uses one shard per file. |
| `keep_on_disk` | `any` | `None` | - | Keep merged records bundle disk-backed. None defaults to True for V1725 and False otherwise. |
| `memory_budget_gb` | `float` | `50.0` | - | Memory budget in GB for in-memory records bundle materialization. |
| `dt` | `int` | `None` | - | Sample interval in ns for records.dt (defaults to adapter rate or 1ns). |
| `baseline_samples` | `any` | `None` | - | Baseline range: int (sample count from adapter start) or tuple (start, end) relative to samples_start. JSON lists like [0, 800] are also accepted. None=adapter default. |
| `input_source` | `str` | `raw_files` | - | Input source for records bundle: 'raw_files' or 'st_waveforms'. Use 'st_waveforms' for the materialized waveform path. |


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
