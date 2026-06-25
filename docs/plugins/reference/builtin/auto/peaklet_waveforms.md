# PeakletWaveformPlugin

> Build peaklet waveform index rows from records-backed hit_merged samples.

## Overview

| Property | Value |
|----------|-------|
| **Provides** | `peaklet_waveforms` |
| **Version** | `1.0.0` |
| **Category** | 波形处理 |
| **Accelerator** | CPU (NumPy/SciPy) |
| **Streaming** | No |
| **Side Effect** | No |

## Dependencies

This plugin has no dependencies.

## Configuration Options

| Option | Type | Default | Units | Description |
|--------|------|---------|-------|-------------|
| `use_filtered` | `bool` | `False` | - | 是否使用 wave_pool_filtered 构建 peaklet 波形 |


## Output Schema

**Output Type**: `structured_array`

| Field | Type | Units | Description |
|-------|------|-------|-------------|
| `peak_id` | `int64` | - | - |
| `time_start` | `int64` | - | - |
| `time_end` | `int64` | - | - |
| `dt` | `int32` | - | - |
| `wave_offset` | `int64` | - | - |
| `wave_length` | `int32` | - | - |

## Usage Example

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import PeakletWaveformPlugin

# Create context and register plugin
ctx = Context(config={"data_root": "DAQ"})
ctx.register(PeakletWaveformPlugin())

# Configure plugin (optional)
ctx.set_config({
    "use_filtered": False,
}, plugin_name="peaklet_waveforms")

# Get data
data = ctx.get_data("run_001", "peaklet_waveforms")
```

## Module

- **Module Path**: `waveform_analysis.core.plugins.builtin.cpu.peaklets`

---

*This documentation was auto-generated from plugin metadata.*
