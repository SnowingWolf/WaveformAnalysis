# WaveformsPlugin

> Extract waveforms from raw CSV files and structure them into NumPy structured arrays.

## Overview

| Property | Value |
|----------|-------|
| **Provides** | `st_waveforms` |
| **Version** | `0.5.0` |
| **Category** | 波形处理 |
| **Accelerator** | CPU (NumPy/SciPy) |
| **Streaming** | No |
| **Side Effect** | No |

## Dependencies

This plugin has no dependencies.

## Configuration Options

| Option | Type | Default | Units | Description |
|--------|------|---------|-------|-------------|
| `daq_adapter` | `str` | `vx2730` | - | DAQ adapter name (e.g., 'vx2730') |
| `wave_length` | `int` | `None` | - | Waveform length (number of sampling points). Automatically detect from the data when None。 |
| `dt_ns` | `int` | `None` | - | Sampling interval in ns for st_waveforms.dt (None=auto from adapter). |
| `n_jobs` | `int` | `None` | - | Number of parallel workers for file-level processing (None=auto, uses min(total_files, 50)) |
| `use_process_pool` | `bool` | `False` | - | Whether to use process pool for file-level parallelism (False=thread pool for I/O, True=process pool for CPU-intensive) |
| `chunksize` | `int` | `None` | - | Chunk size for CSV reading (None=read entire file, enables PyArrow; set value to enable chunked reading but disables PyArrow) |
| `parse_engine` | `str` | `auto` | - | CSV engine: auto | polars | pyarrow | pandas |
| `use_upstream_baseline` | `bool` | `False` | - | Whether to use baseline from upstream plugin (requires 'baseline' data). |
| `baseline_samples` | `any` | `None` | - | Baseline range: int (sample count from adapter start) or tuple (start, end) relative to samples_start. None=adapter default. |
| `streaming_mode` | `bool` | `False` | - | Enable streaming mode: read files and structure waveforms incrementally to reduce memory usage. When enabled, uses memmap for output to avoid full vstack memory overhead. |


## Output Schema

**Output Type**: `structured_array`

| Field | Type | Units | Description |
|-------|------|-------|-------------|
| `baseline` | `float64` | - | - |
| `baseline_upstream` | `float64` | - | - |
| `timestamp` | `int64` | - | - |
| `dt` | `int32` | - | - |
| `event_length` | `int32` | - | - |
| `channel` | `int16` | - | - |
| `wave` | `('<i2', (1500,))` | - | - |

## Usage Example

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import WaveformsPlugin

# Create context and register plugin
ctx = Context(config={"data_root": "DAQ"})
ctx.register(WaveformsPlugin())

# Configure plugin (optional)
ctx.set_config({
    "daq_adapter": 'vx2730',
    "wave_length": None,
    "dt_ns": None,
}, plugin_name="st_waveforms")

# Get data
data = ctx.get_data("run_001", "st_waveforms")
```

## Module

- **Module Path**: `waveform_analysis.core.plugins.builtin.cpu.waveforms`

---

*This documentation was auto-generated from plugin metadata.*