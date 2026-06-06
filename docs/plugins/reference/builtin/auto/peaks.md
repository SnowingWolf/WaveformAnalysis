# PeaksPlugin

> Build final peaks table from peaklets and waveform-derived features.

## Overview

| Property | Value |
|----------|-------|
| **Provides** | `peaks` |
| **Version** | `1.0.0` |
| **Category** | 特征提取 |
| **Accelerator** | CPU (NumPy/SciPy) |
| **Streaming** | No |
| **Side Effect** | No |

## Dependencies

This plugin depends on the following data:

- [`peaklets`](peaklets.md)
- [`peaklet_features`](peaklet_features.md)
- [`peaklet_channels`](peaklet_channels.md)

## Configuration Options

This plugin has no configuration options.

## Output Schema

**Output Type**: `structured_array`

| Field | Type | Units | Description |
|-------|------|-------|-------------|
| `time_start` | `int64` | - | - |
| `time_end` | `int64` | - | - |
| `center_time` | `int64` | - | - |
| `max_time` | `int64` | - | - |
| `area` | `float32` | - | - |
| `height` | `float32` | - | - |
| `width` | `float32` | - | - |
| `rise_time` | `float32` | - | - |
| `fall_time` | `float32` | - | - |
| `n_hits` | `int32` | - | - |
| `n_channels` | `int32` | - | - |

## Usage Example

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import PeaksPlugin

# Create context and register plugin
ctx = Context(config={"data_root": "DAQ"})
ctx.register(PeaksPlugin())

# Get data
data = ctx.get_data("run_001", "peaks")
```

## Module

- **Module Path**: `waveform_analysis.core.plugins.builtin.cpu.peaklets`

---

*This documentation was auto-generated from plugin metadata.*
