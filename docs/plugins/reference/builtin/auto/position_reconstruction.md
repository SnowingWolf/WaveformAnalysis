# PositionReconstructionPlugin

> Reconstruct 3D position from S1-S2 pairs using vectorized CoG method

## Overview

| Property | Value |
|----------|-------|
| **Provides** | `position_reconstruction` |
| **Version** | `0.2.1` |
| **Category** | 其他 |
| **Accelerator** | CPU (NumPy/SciPy) |
| **Streaming** | No |
| **Side Effect** | No |

## Dependencies

This plugin depends on the following data:

- [`s1_s2_pairs`](s1_s2_pairs.md)

## Configuration Options

| Option | Type | Default | Units | Description |
|--------|------|---------|-------|-------------|
| `drift_velocity` | `float` | `0.0013` | - | 漂移速度 (mm/ns)，用于 Z 坐标计算。典型值：液氙 ~0.001 mm/ns, 液氩 ~0.0013 mm/ns |
| `min_s2_area_for_xy` | `float` | `100.0` | - | XY 重建所需的最小 S2 面积 (PE) |
| `edge_threshold_mm` | `float` | `5.0` | - | 边缘事件判定阈值：距离 TPC 边界的最小距离 (mm) |
| `detector_radius_mm` | `float` | `62.5` | - | 探测器有效半径 (mm)，用于边缘事件检测 |


## Output Schema

**Output Type**: `structured_array`

| Field | Type | Units | Description |
|-------|------|-------|-------------|
| `event_id` | `int64` | - | - |
| `pair_id` | `int64` | - | - |
| `s1_peak_id` | `int64` | - | - |
| `s2_peak_id` | `int64` | - | - |
| `x` | `float32` | - | - |
| `y` | `float32` | - | - |
| `z` | `float32` | - | - |
| `r` | `float32` | - | - |
| `x_err` | `float32` | - | - |
| `y_err` | `float32` | - | - |
| `z_err` | `float32` | - | - |
| `xy_chi2` | `float32` | - | - |
| `xy_ndf` | `int16` | - | - |
| `z_quality` | `float32` | - | - |
| `position_goodness` | `float32` | - | - |
| `xy_method` | `<U16` | - | - |
| `z_method` | `<U16` | - | - |
| `drift_time_ns` | `float32` | - | - |
| `s2_area` | `float32` | - | - |
| `s2_n_channels` | `int16` | - | - |
| `flags` | `uint32` | - | - |

## Usage Example

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import PositionReconstructionPlugin

# Create context and register plugin
ctx = Context(config={"data_root": "DAQ"})
ctx.register(PositionReconstructionPlugin())

# Configure plugin (optional)
ctx.set_config({
    "drift_velocity": 0.0013,
    "min_s2_area_for_xy": 100.0,
    "edge_threshold_mm": 5.0,
}, plugin_name="position_reconstruction")

# Get data
data = ctx.get_data("run_001", "position_reconstruction")
```

## Module

- **Module Path**: `waveform_analysis.core.plugins.builtin.cpu.position_reconstruction`

---

*This documentation was auto-generated from plugin metadata.*
