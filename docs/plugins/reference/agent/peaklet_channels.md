---
schema_version: 1
document_type: "plugin_reference"
profile: "agent"
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
Expand peaklets into per-board/channel contribution rows.

| Item | Value |
| --- | --- |
| Provides | `peaklet_channels` |
| Plugin Class | `PeakletChannelsPlugin` |
| Module | `waveform_analysis.core.plugins.builtin.peaks.peaklet_channels` |
| Version | `1.0.1` |
| Category | 峰构建 |
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
| `peaklet_id` | `int64` | - | Peaklet identifier |
| `board` | `int16` | - | Hardware board index |
| `channel` | `int16` | - | Physical channel number |
| `area` | `float32` | - | Total area contribution from this channel |
| `height` | `float32` | - | Maximum height contribution from this channel |
| `n_hits` | `int32` | - | Number of component hits from this channel |
| `area_fraction` | `float32` | - | Fraction of the peaklet total area contributed by this channel |
## Usage

### Minimal Example

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import PeakletChannelsPlugin

ctx = Context(config={"data_root": "DAQ"})
ctx.register(PeakletChannelsPlugin())
data = ctx.get_data("run_001", "peaklet_channels")
```

## Operational Notes

### Behavior

### Failure Modes

- Dependency data, configuration, or output contract validation may fail explicitly.
### Downstream Impact

Consumers: `peaks`

## Maintenance

### Change Playbook

1. Keep `provides` and dependency semantics stable or update all consumers.
2. Bump `version` for behavior, configuration, or output contract changes.
3. Regenerate auto, agent, and web references after metadata changes.
### Validation

```bash
waveform-docs generate plugins-agent --plugin peaklet_channels
waveform-docs check coverage --strict --fail-on-warning
```
