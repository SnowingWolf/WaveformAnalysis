---
schema_version: 1
document_type: "plugin_reference"
profile: "auto"
provides: "peaklet_features"
plugin_class: "PeakletFeaturesPlugin"
module: "waveform_analysis.core.plugins.builtin.peaks.peaklets"
version: "4.1.0"
summary: "Compute peaklet waveform features from ragged signal pools."
depends_on: ["peaklet_waveforms", "peaklet_waveform_pool", "peaklets"]
output_kind: "structured_array"
generated: true
---
# peaklet_features

## Overview

Compute peaklet waveform features from ragged signal pools.

| Item | Value |
| --- | --- |
| Provides | `peaklet_features` |
| Plugin Class | `PeakletFeaturesPlugin` |
| Module | `waveform_analysis.core.plugins.builtin.peaks.peaklets` |
| Version | `4.1.0` |
| Category | 特征提取 |
| Accelerator | CPU (NumPy/SciPy) |
| Output Kind | `structured_array` |

| Dependency | Version Constraint | Resolution | Required Fields | Description |
| --- | --- | --- | --- | --- |
| `peaklet_waveforms` | - | declared | - | - |
| `peaklet_waveform_pool` | - | declared | - | - |
| `peaklets` | - | declared | - | - |
## Configuration

| Name | Type | Default | Unit | Tracked | Deprecated | Description |
| --- | --- | --- | --- | --- | --- | --- |
| - | - | - | - | - | - | - |
## Output

| Field | DType | Unit | Meaning |
| --- | --- | --- | --- |
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
## Usage

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import PeakletFeaturesPlugin

ctx = Context(config={"data_root": "DAQ"})
ctx.register(PeakletFeaturesPlugin())
data = ctx.get_data("run_001", "peaklet_features")
```
