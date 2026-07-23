---
schema_version: 1
document_type: "plugin_reference"
profile: "auto"
provides: "peaklet_channels"
plugin_class: "PeakletChannelsPlugin"
module: "waveform_analysis.core.plugins.builtin.peaks.peaklet_channels"
version: "1.0.1"
summary: "Aggregate hit_merged_features into per-peaklet channel contribution rows."
depends_on: ["peaklets", "peaklet_components", "hit_merged_features", "peaklet_features"]
output_kind: "structured_array"
generated: true
---
# peaklet_channels

## Overview

Aggregate hit_merged_features into per-peaklet channel contribution rows.
| Item | Value |
| --- | --- |
| Provides | `peaklet_channels` |
| Plugin Class | `PeakletChannelsPlugin` |
| Module | `waveform_analysis.core.plugins.builtin.peaks.peaklet_channels` |
| Version | `1.0.1` |
| Category | 特征提取 |
| Accelerator | CPU (NumPy/SciPy) |
| Output Kind | `structured_array` |

| Dependency | Version Constraint | Resolution | Required Fields | Description |
| --- | --- | --- | --- | --- |
| `peaklets` | - | declared | - | Build lightweight cross-channel peaklets from hit_merged intervals. |
| `peaklet_components` | - | declared | - | Return per-peaklet component hit_merged indices. |
| `hit_merged_features` | - | declared | - | Compute per-hit_merged local waveform features from records-backed samples. |
| `peaklet_features` | - | declared | - | Compute peaklet waveform features from ragged signal pools. |
### How It Works


## Configuration

| Name | Type | Default | Unit | Tracked | Deprecated | Description |
| --- | --- | --- | --- | --- | --- | --- |
| - | - | - | - | - | - | - |
## Output

structured_array output with fields: peaklet_id, board, channel, area, height, n_hits, area_fraction.

| Field | DType | Unit | Meaning |
| --- | --- | --- | --- |
| `peaklet_id` | `int64` | - | - |
| `board` | `int16` | - | - |
| `channel` | `int16` | - | - |
| `area` | `float32` | - | - |
| `height` | `float32` | - | - |
| `n_hits` | `int32` | - | - |
| `area_fraction` | `float32` | - | - |
## Usage

### Minimal Example

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import PeakletChannelsPlugin

ctx = Context(config={"data_root": "DAQ"})
ctx.register(PeakletChannelsPlugin())
data = ctx.get_data("run_001", "peaklet_channels")
```
### Downstream Consumers

- `peaks`
