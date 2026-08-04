---
schema_version: 1
document_type: "plugin_reference"
profile: "auto"
provides: "hit_merged_components"
plugin_class: "HitMergedComponentsPlugin"
module: "waveform_analysis.core.plugins.builtin.hit_merged_components.plugin"
version: "1.1.0"
summary: "Return per-cluster component hit indices for hit_merged rows."
depends_on: ["hit_merged", "hit_threshold"]
output_kind: "structured_array"
generated: true
---
# hit_merged_components

## Overview

Return per-cluster component hit indices for hit_merged rows.
Return flat component hit indices for each hit_merged cluster.

| Item | Value |
| --- | --- |
| Provides | `hit_merged_components` |
| Plugin Class | `HitMergedComponentsPlugin` |
| Module | `waveform_analysis.core.plugins.builtin.hit_merged_components.plugin` |
| Version | `1.1.0` |
| Category | 特征提取 |
| Output Kind | `structured_array` |

| Dependency | Version Constraint | Resolution | Required Fields | Description |
| --- | --- | --- | --- | --- |
| `hit_merged` | - | declared | - | Merge nearby threshold hits per channel with time-gap and max-width constraints. |
| `hit_threshold` | - | declared | - | Threshold-only hit detector with THRESHOLD_HIT_DTYPE output. |
### How It Works


## Configuration

| Name | Type | Default | Unit | Tracked | Deprecated | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `validate_components` | `bool` | `False` | - | yes | no | 校验 hit_merged 的 component_offset/component_count 与 cluster rows 是否一致。 |
## Output

structured_array output with fields: merged_index, hit_index.

| Field | DType | Unit | Meaning |
| --- | --- | --- | --- |
| `merged_index` | `int64` | None | Index of the merged hit record |
| `hit_index` | `int64` | None | Row index in the source hit_threshold array |
## Usage

### Minimal Example

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.hit_merged_components import HitMergedComponentsPlugin

ctx = Context(config={"data_root": "DAQ"})
ctx.register(HitMergedComponentsPlugin())
data = ctx.get_data("run_001", "hit_merged_components")
```
### Downstream Consumers

- `hit_grouped`
