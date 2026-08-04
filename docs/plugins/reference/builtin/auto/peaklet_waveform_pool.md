---
schema_version: 1
document_type: "plugin_reference"
profile: "auto"
provides: "peaklet_waveform_pool"
plugin_class: "PeakletWaveformPoolPlugin"
module: "waveform_analysis.core.plugins.builtin.peaks.peaklets"
version: "2.0.0"
summary: "Return the flattened float32 signal pool paired with peaklet_waveforms. Configure waveform construction on peaklet_waveforms."
depends_on: ["peaklet_waveforms"]
output_kind: "array"
generated: true
---
# peaklet_waveform_pool

## Overview

Return the flattened float32 signal pool paired with peaklet_waveforms. Configure waveform construction on peaklet_waveforms.
Return the pool produced alongside the canonical peaklet waveform index.

| Item | Value |
| --- | --- |
| Provides | `peaklet_waveform_pool` |
| Plugin Class | `PeakletWaveformPoolPlugin` |
| Module | `waveform_analysis.core.plugins.builtin.peaks.peaklets` |
| Version | `2.0.0` |
| Category | 峰构建 |
| Accelerator | CPU (NumPy/SciPy) |
| Output Kind | `array` |

| Dependency | Version Constraint | Resolution | Required Fields | Description |
| --- | --- | --- | --- | --- |
| `peaklet_waveforms` | - | declared | - | Build peaklet waveform index rows from records-backed hit_merged samples. Supports cross-record hits via component expansion. |
### How It Works


## Configuration

| Name | Type | Default | Unit | Tracked | Deprecated | Description |
| --- | --- | --- | --- | --- | --- | --- |
| - | - | - | - | - | - | - |
## Output

array output with fields: value.

| Field | DType | Unit | Meaning |
| --- | --- | --- | --- |
| `value` | `float32` | ADC counts | Flattened float32 waveform sample for peaklet waveform slices |
## Usage

### Minimal Example

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.plugin_sets import (
    plugins_hit,
    plugins_io,
    plugins_waveform,
)

ctx = Context(config={"data_root": "DAQ"})
ctx.register(*plugins_io(), *plugins_waveform(), *plugins_hit())

# Construction options belong to the canonical waveform producer.
ctx.set_config(
    {"use_filtered": False, "clip_negative_signal": False},
    plugin_name="peaklet_waveforms",
)
pool = ctx.get_data("run_001", "peaklet_waveform_pool")
```
### Downstream Consumers

- `peaklet_features`
