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
| `peaklets` | - | declared | - | - |
| `peaklet_components` | - | declared | - | - |
| `hit_merged_features` | - | declared | - | - |
| `peaklet_features` | - | declared | - | - |
## Configuration

| Name | Type | Default | Unit | Tracked | Deprecated | Description |
| --- | --- | --- | --- | --- | --- | --- |
| - | - | - | - | - | - | - |
## Output

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

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import PeakletChannelsPlugin

ctx = Context(config={"data_root": "DAQ"})
ctx.register(PeakletChannelsPlugin())
data = ctx.get_data("run_001", "peaklet_channels")
```

## Operational Notes

### Behavior

- Per-channel contribution table for peaklets.
### Failure Modes

- Dependency data, configuration, or output contract validation may fail explicitly.
### Downstream Impact

-
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
