---
schema_version: 1
document_type: "plugin_reference"
profile: "agent"
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
Compute waveform-derived features from ragged peaklet waveforms.

| Item | Value |
| --- | --- |
| Provides | `peaklet_features` |
| Plugin Class | `PeakletFeaturesPlugin` |
| Module | `waveform_analysis.core.plugins.builtin.peaks.peaklets` |
| Version | `4.1.0` |
| Category | 峰构建 |
| Accelerator | CPU (NumPy/SciPy) |
| Output Kind | `structured_array` |

| Dependency | Version Constraint | Resolution | Required Fields | Description |
| --- | --- | --- | --- | --- |
| `peaklet_waveforms` | - | declared | - | Build peaklet waveform index rows from records-backed hit_merged samples. Supports cross-record hits via component expansion. |
| `peaklet_waveform_pool` | - | declared | - | Return the flattened float32 signal pool paired with peaklet_waveforms. Configure waveform construction on peaklet_waveforms. |
| `peaklets` | - | declared | - | Build lightweight cross-channel peaklets from hit_merged intervals. |
### How It Works


## Configuration

| Name | Type | Default | Unit | Tracked | Deprecated | Description |
| --- | --- | --- | --- | --- | --- | --- |
| - | - | - | - | - | - | - |
## Output

structured_array output with fields: peak_id, time_start, time_end, time_peak, center_time, rise_time, fall_time, width_25_75, ....

| Field | DType | Unit | Meaning |
| --- | --- | --- | --- |
| `peak_id` | `int64` | - | Peaklet identifier |
| `time_start` | `int64` | - | Absolute start time of the peaklet (ps) |
| `time_end` | `int64` | - | Absolute end time of the peaklet (ps) |
| `time_peak` | `int64` | - | Time of the maximum sample value (ps) |
| `center_time` | `int64` | - | Center time of the peaklet (ps) |
| `rise_time` | `float32` | - | Rise time (ns) |
| `fall_time` | `float32` | - | Fall time (ns) |
| `width_25_75` | `float32` | - | Width between 25% and 75% of the peak (ns) |
| `rise_time_10_50` | `float32` | - | Rise time from 10% to 50% (ns) |
| `range_90p_area` | `float32` | - | Time range covering 90% of the waveform area (ns) |
| `area` | `float32` | - | Total waveform area |
| `height` | `float32` | - | Maximum waveform height |
| `width` | `float32` | - | Pulse width (ns) |
## Usage

### Minimal Example

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import PeakletFeaturesPlugin

ctx = Context(config={"data_root": "DAQ"})
ctx.register(PeakletFeaturesPlugin())
data = ctx.get_data("run_001", "peaklet_features")
```

## Operational Notes

### Behavior

### Failure Modes

- Dependency data, configuration, or output contract validation may fail explicitly.
### Downstream Impact

Consumers: `peaklet_channels`, `peaks`

## Maintenance

### Change Playbook

1. Keep `provides` and dependency semantics stable or update all consumers.
2. Bump `version` for behavior, configuration, or output contract changes.
3. Regenerate auto, agent, and web references after metadata changes.
### Validation

```bash
waveform-docs generate plugins-agent --plugin peaklet_features
waveform-docs check coverage --strict --fail-on-warning
```
