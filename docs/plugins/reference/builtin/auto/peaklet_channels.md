# PeakletChannelsPlugin

> Aggregate hit_merged_features into per-peaklet channel contribution rows.

## Overview

| Property | Value |
|----------|-------|
| **Provides** | `peaklet_channels` |
| **Version** | `1.0.0` |
| **Category** | 特征提取 |
| **Accelerator** | CPU (NumPy/SciPy) |
| **Streaming** | No |
| **Side Effect** | No |

## Dependencies

This plugin depends on the following data:

- [`peaklets`](peaklets.md)
- [`peaklet_components`](peaklet_components.md)
- [`hit_merged_features`](hit_merged_features.md)
- [`peaklet_features`](peaklet_features.md)

## Configuration Options

This plugin has no configuration options.

## Output Schema

**Output Type**: `structured_array`

| Field | Type | Units | Description |
|-------|------|-------|-------------|
| `peaklet_index` | `int64` | - | - |
| `board` | `int16` | - | - |
| `channel` | `int16` | - | - |
| `area` | `float32` | - | - |
| `height` | `float32` | - | - |
| `n_hits` | `int32` | - | - |
| `area_fraction` | `float32` | - | - |

## Usage Example

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import PeakletChannelsPlugin

# Create context and register plugin
ctx = Context(config={"data_root": "DAQ"})
ctx.register(PeakletChannelsPlugin())

# Get data
data = ctx.get_data("run_001", "peaklet_channels")
```

## Module

- **Module Path**: `waveform_analysis.core.plugins.builtin.cpu.peaklet_channels`

---

*This documentation was auto-generated from plugin metadata.*
