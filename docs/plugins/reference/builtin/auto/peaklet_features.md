# PeakletFeaturesPlugin

> Compute peaklet waveform features from ragged signal pools.

## Overview

| Property | Value |
|----------|-------|
| **Provides** | `peaklet_features` |
| **Version** | `4.0.0` |
| **Category** | 特征提取 |
| **Accelerator** | CPU (NumPy/SciPy) |
| **Streaming** | No |
| **Side Effect** | No |

## Dependencies

This plugin depends on the following data:

- [`peaklet_waveforms`](peaklet_waveforms.md)
- [`peaklet_waveform_pool`](peaklet_waveform_pool.md)
- [`peaklets`](peaklets.md)

## Configuration Options

This plugin has no configuration options.

## Output Schema

**Output Type**: `structured_array`

| Field | Type | Units | Description |
|-------|------|-------|-------------|
| `peak_id` | `int64` | - | - |
| `time_start` | `int64` | - | - |
| `time_end` | `int64` | - | - |
| `time_peak` | `int64` | - | - |
| `center_time` | `int64` | - | - |
| `rise_time` | `float32` | - | - |
| `fall_time` | `float32` | - | - |
| `width_25_75` | `float32` | - | - |
| `rise_time_10_50` | `float32` | - | - |
| `range_90p_area` | `float32` | - | - |
| `area` | `float32` | - | - |
| `height` | `float32` | - | - |
| `width` | `float32` | - | - |

## Usage Example

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import PeakletFeaturesPlugin

# Create context and register plugin
ctx = Context(config={"data_root": "DAQ"})
ctx.register(PeakletFeaturesPlugin())

# Get data
data = ctx.get_data("run_001", "peaklet_features")
```

## Module

- **Module Path**: `waveform_analysis.core.plugins.builtin.peaks.peaklets`

---

*This documentation was auto-generated from plugin metadata.*
