# HitFinderPlugin

> Example implementation of the HitFinder as a plugin.

## Overview

| Property | Value |
|----------|-------|
| **Provides** | `hits` |
| **Version** | `2.1.0` |
| **Category** | 特征提取 |
| **Accelerator** | CPU (NumPy/SciPy) |
| **Streaming** | No |
| **Side Effect** | No |

## Dependencies

This plugin has no dependencies.

## Configuration Options

| Option | Type | Default | Units | Description |
|--------|------|---------|-------|-------------|
| `threshold` | `float` | `10.0` | - | Hit 检测阈值 |
| `use_filtered` | `bool` | `False` | - | 是否使用 filtered_waveforms（需要先注册 FilteredWaveformsPlugin） |


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

# Configure plugin (optional)
ctx.set_config({
    "threshold": 10.0,
    "use_filtered": False,
}, plugin_name="hits")

# Get data
data = ctx.get_data("run_001", "hits")
```

## Module

- **Module Path**: `waveform_analysis.core.plugins.builtin.cpu.hit_finder`

---

*This documentation was auto-generated from plugin metadata.*
