# EventPlugin

> Complete event reconstruction from S1-S2 pairs and position

## Overview

| Property | Value |
|----------|-------|
| **Provides** | `events` |
| **Version** | `0.0.0` |
| **Category** | 事件分析 |
| **Accelerator** | CPU (NumPy/SciPy) |
| **Streaming** | No |
| **Side Effect** | No |

## Dependencies

This plugin depends on the following data:

- [`s1_s2_pairs`](s1_s2_pairs.md)
- [`position_reconstruction`](position_reconstruction.md)

## Configuration Options

| Option | Type | Default | Units | Description |
|--------|------|---------|-------|-------------|
| `min_s1` | `float` | `0.0` | - | 最小 S1 阈值（用于质量筛选） |
| `min_s2` | `float` | `0.0` | - | 最小 S2 阈值（用于质量筛选） |
| `fiducial_radius` | `(<class 'float'>, <class 'NoneType'>)` | `None` | - | 基准体积半径 (mm)。None 表示不应用 |
| `fiducial_z_range` | `(<class 'tuple'>, <class 'NoneType'>)` | `None` | - | 基准体积 Z 范围 (z_min, z_max) mm。None 表示不应用 |


## Output Schema

**Output Type**: `structured_array`

| Field | Type | Units | Description |
|-------|------|-------|-------------|
| `event_id` | `int64` | - | - |
| `event_number` | `int64` | - | - |
| `run_id` | `<U32` | - | - |
| `pair_id` | `int64` | - | - |
| `s1_peak_id` | `int64` | - | - |
| `s2_peak_id` | `int64` | - | - |
| `x` | `float32` | - | - |
| `y` | `float32` | - | - |
| `z` | `float32` | - | - |
| `r` | `float32` | - | - |
| `drift_time` | `float32` | - | - |
| `s1_time` | `float64` | - | - |
| `s2_time` | `float64` | - | - |
| `s1_area` | `float32` | - | - |
| `s2_area` | `float32` | - | - |
| `log10_s2_s1` | `float32` | - | - |
| `s1_n_channels` | `int16` | - | - |
| `s2_n_channels` | `int16` | - | - |
| `s1_area_fraction_top` | `float32` | - | - |
| `s2_area_fraction_top` | `float32` | - | - |
| `s1_rise_time` | `float32` | - | - |
| `s2_rise_time` | `float32` | - | - |
| `n_s1_candidates` | `int32` | - | - |
| `n_s2_candidates` | `int32` | - | - |
| `flags` | `uint32` | - | - |

## Usage Example

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import EventPlugin

# Create context and register plugin
ctx = Context(config={"data_root": "DAQ"})
ctx.register(EventPlugin())

# Configure plugin (optional)
ctx.set_config({
    "min_s1": 0.0,
    "min_s2": 0.0,
    "fiducial_radius": None,
}, plugin_name="events")

# Get data
data = ctx.get_data("run_001", "events")
```

## Module

- **Module Path**: `waveform_analysis.core.plugins.builtin.cpu.event`

---

*This documentation was auto-generated from plugin metadata.*
