# HitFinderPlugin

> Example implementation of the HitFinder as a plugin.

## Overview

| Property | Value |
|----------|-------|
| **Provides** | `hits` |
| **Version** | `0.0.0` |
| **Category** | 特征提取 |
| **Accelerator** | CPU (NumPy/SciPy) |
| **Streaming** | No |
| **Side Effect** | No |

## Dependencies

This plugin depends on the following data:

- [`st_waveforms`](st_waveforms.md)

## Configuration Options

This plugin has no configuration options.

## Output Schema

**Output Type**: `structured_array`

| Field | Type | Units | Description |
|-------|------|-------|-------------|
| `time` | `int64` | - | - |
| `area` | `float32` | - | - |
| `height` | `float32` | - | - |
| `width` | `float32` | - | - |
| `channel` | `int16` | - | - |
| `event_index` | `int64` | - | - |

## Usage Example

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import HitFinderPlugin

# Create context and register plugin
ctx = Context(config={"data_root": "DAQ"})
ctx.register(HitFinderPlugin())

# Get data
data = ctx.get_data("run_001", "hits")
```

## Module

- **Module Path**: `waveform_analysis.core.plugins.builtin.cpu.hit_finder`

---

*This documentation was auto-generated from plugin metadata.*