---
schema_version: 1
document_type: "plugin_reference"
profile: "auto"
provides: "position_reconstruction"
plugin_class: "PositionReconstructionPlugin"
module: "waveform_analysis.core.plugins.builtin.cpu.position_reconstruction"
version: "0.2.1"
summary: "Reconstruct 3D position from S1-S2 pairs using vectorized CoG method"
depends_on: ["s1_s2_pairs"]
output_kind: "structured_array"
generated: true
---
# position_reconstruction

## Overview

Reconstruct 3D position from S1-S2 pairs using vectorized CoG method
| Item | Value |
| --- | --- |
| Provides | `position_reconstruction` |
| Plugin Class | `PositionReconstructionPlugin` |
| Module | `waveform_analysis.core.plugins.builtin.cpu.position_reconstruction` |
| Version | `0.2.1` |
| Category | 其他 |
| Accelerator | CPU (NumPy/SciPy) |
| Output Kind | `structured_array` |

| Dependency | Version Constraint | Resolution | Required Fields | Description |
| --- | --- | --- | --- | --- |
| `s1_s2_pairs` | - | declared | - | Select best S1-S2 pairs from candidates |
### How It Works


## Configuration

| Name | Type | Default | Unit | Tracked | Deprecated | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `drift_velocity` | `float` | `0.0013` | - | yes | no | 漂移速度 (mm/ns)，用于 Z 坐标计算。典型值：液氙 ~0.001 mm/ns, 液氩 ~0.0013 mm/ns |
| `min_s2_area_for_xy` | `float` | `100.0` | - | yes | no | XY 重建所需的最小 S2 面积 (PE) |
| `edge_threshold_mm` | `float` | `5.0` | - | yes | no | 边缘事件判定阈值：距离 TPC 边界的最小距离 (mm) |
| `detector_radius_mm` | `float` | `62.5` | - | yes | no | 探测器有效半径 (mm)，用于边缘事件检测 |
## Output

structured_array output with fields: event_id, pair_id, s1_peak_id, s2_peak_id, x, y, z, r, ....

| Field | DType | Unit | Meaning |
| --- | --- | --- | --- |
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
## Usage

### Minimal Example

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import PositionReconstructionPlugin

ctx = Context(config={"data_root": "DAQ"})
ctx.register(PositionReconstructionPlugin())
data = ctx.get_data("run_001", "position_reconstruction")
```
### Downstream Consumers

- `events`
