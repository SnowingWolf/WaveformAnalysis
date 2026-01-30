# WaveformsPlugin

> Extract waveforms from raw CSV files and structure them into NumPy structured arrays.

## Overview

| Property | Value |
|----------|-------|
| **Provides** | `st_waveforms` |
| **Version** | `0.1.0` |
| **Category** | 波形处理 |
| **Accelerator** | CPU (NumPy/SciPy) |
| **Streaming** | No |
| **Side Effect** | No |

## Dependencies

This plugin depends on the following data:

- [`raw_files`](raw_files.md)

## Configuration Options

| Option | Type | Default | Units | Description |
|--------|------|---------|-------|-------------|
| `channel_workers` | `any` | `None` | - | Number of parallel workers for channel-level processing (None=auto, uses min(len(raw_files), cpu_count)) |
| `channel_executor` | `str` | `thread` | - | Executor type for channel-level parallelism: 'thread' or 'process' |
| `daq_adapter` | `str` | `vx2730` | - | DAQ adapter name (e.g., 'vx2730') |
| `n_jobs` | `int` | `None` | - | Number of parallel workers for file-level processing within each channel (None=auto, uses min(max_file_count, 50)) |
| `use_process_pool` | `bool` | `False` | - | Whether to use process pool for file-level parallelism (False=thread pool for I/O, True=process pool for CPU-intensive) |
| `chunksize` | `int` | `None` | - | Chunk size for CSV reading (None=read entire file, enables PyArrow; set value to enable chunked reading but disables PyArrow) |
| `use_upstream_baseline` | `bool` | `False` | - | Whether to use baseline from upstream plugin (requires 'baseline' data). |


## Output Schema

**Output Type**: `structured_array`

| Field | Type | Units | Description |
|-------|------|-------|-------------|
| `baseline` | `float64` | - | - |
| `baseline_upstream` | `float64` | - | - |
| `timestamp` | `int64` | - | - |
| `event_length` | `int64` | - | - |
| `channel` | `int16` | - | - |
| `wave` | `('<f4', (800,))` | - | - |

## Usage Example

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import WaveformsPlugin

# Create context and register plugin
ctx = Context(config={"data_root": "DAQ"})
ctx.register(WaveformsPlugin())

# Configure plugin (optional)
ctx.set_config({
    "channel_workers": None,
    "channel_executor": 'thread',
    "daq_adapter": 'vx2730',
}, plugin_name="st_waveforms")

# Get data
data = ctx.get_data("run_001", "st_waveforms")
```

## Module

- **Module Path**: `waveform_analysis.core.plugins.builtin.cpu.waveforms`

---

*This documentation was auto-generated from plugin metadata.*
