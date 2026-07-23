---
schema_version: 1
document_type: "plugin_reference"
profile: "auto"
provides: "events"
plugin_class: "EventPlugin"
module: "waveform_analysis.core.plugins.builtin.cpu.event"
version: "0.0.1"
summary: "Complete event reconstruction from S1-S2 pairs and position"
depends_on: ["s1_s2_pairs", "position_reconstruction"]
output_kind: "structured_array"
generated: true
---
# events

## Overview

Complete event reconstruction from S1-S2 pairs and position
| Item | Value |
| --- | --- |
| Provides | `events` |
| Plugin Class | `EventPlugin` |
| Module | `waveform_analysis.core.plugins.builtin.cpu.event` |
| Version | `0.0.1` |
| Category | 事件分析 |
| Accelerator | CPU (NumPy/SciPy) |
| Output Kind | `structured_array` |

| Dependency | Version Constraint | Resolution | Required Fields | Description |
| --- | --- | --- | --- | --- |
| `s1_s2_pairs` | - | declared | - | Select best S1-S2 pairs from candidates |
| `position_reconstruction` | - | declared | - | Reconstruct 3D position from S1-S2 pairs using vectorized CoG method |
### How It Works


## Configuration

| Name | Type | Default | Unit | Tracked | Deprecated | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `min_s1` | `float` | `0.0` | - | yes | no | 最小 S1 阈值（用于质量筛选） |
| `min_s2` | `float` | `0.0` | - | yes | no | 最小 S2 阈值（用于质量筛选） |
| `fiducial_radius` | `(<class 'float'>, <class 'NoneType'>)` | `None` | - | yes | no | 基准体积半径 (mm)。None 表示不应用 |
| `fiducial_z_range` | `(<class 'tuple'>, <class 'NoneType'>)` | `None` | - | yes | no | 基准体积 Z 范围 (z_min, z_max) mm。None 表示不应用 |
## Output

structured_array output with fields: event_id, event_number, run_id, pair_id, s1_peak_id, s2_peak_id, x, y, ....

| Field | DType | Unit | Meaning |
| --- | --- | --- | --- |
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
## Usage

### Minimal Example

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import EventPlugin

ctx = Context(config={"data_root": "DAQ"})
ctx.register(EventPlugin())
data = ctx.get_data("run_001", "events")
```
### Downstream Consumers

- Terminal output; no direct builtin consumer is declared.
