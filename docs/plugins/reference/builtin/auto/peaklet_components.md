# PeakletComponentsPlugin

> Return per-peaklet component hit_merged indices.

## Overview

| Property | Value |
|----------|-------|
| **Provides** | `peaklet_components` |
| **Version** | `1.2.0` |
| **Category** | 特征提取 |
| **Accelerator** | CPU (NumPy/SciPy) |
| **Streaming** | No |
| **Side Effect** | No |

## Dependencies

This plugin depends on the following data:

- [`peaklets`](peaklets.md)
- [`hit_merged`](hit_merged.md)

## Configuration Options

This plugin has no configuration options.

## Output Schema

**Output Type**: `structured_array`

| Field | Type | Units | Description |
|-------|------|-------|-------------|
| `peak_id` | `int64` | - | - |
| `merged_index` | `int64` | - | - |

## Usage Example

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import PeakletComponentsPlugin

# Create context and register plugin
ctx = Context(config={"data_root": "DAQ"})
ctx.register(PeakletComponentsPlugin())

# Get data
data = ctx.get_data("run_001", "peaklet_components")
```

## Module

- **Module Path**: `waveform_analysis.core.plugins.builtin.cpu.peaklets`

---

*This documentation was auto-generated from plugin metadata.*
