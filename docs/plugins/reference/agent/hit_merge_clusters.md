---
schema_version: 1
document_type: "plugin_reference"
profile: "agent"
provides: "hit_merge_clusters"
plugin_class: "HitMergeClustersPlugin"
module: "waveform_analysis.core.plugins.builtin.hit.hit_merge"
version: "1.1.0"
summary: "Export cluster membership rows using the authoritative hit_merged configuration."
depends_on: ["hit_merged", "hit_threshold"]
output_kind: "structured_array"
generated: true
---
# hit_merge_clusters

## Overview

Export cluster membership rows using the authoritative hit_merged configuration.
| Item | Value |
| --- | --- |
| Provides | `hit_merge_clusters` |
| Plugin Class | `HitMergeClustersPlugin` |
| Module | `waveform_analysis.core.plugins.builtin.hit.hit_merge` |
| Version | `1.1.0` |
| Category | 特征提取 |
| Accelerator | CPU (NumPy/SciPy) |
| Output Kind | `structured_array` |

| Dependency | Version Constraint | Resolution | Required Fields | Description |
| --- | --- | --- | --- | --- |
| `hit_merged` | - | declared | - | Merge nearby threshold hits per channel with time-gap and max-width constraints. |
| `hit_threshold` | - | declared | - | Threshold-only hit detector with THRESHOLD_HIT_DTYPE output. |
### How It Works


## Configuration

| Name | Type | Default | Unit | Tracked | Deprecated | Description |
| --- | --- | --- | --- | --- | --- | --- |
| - | - | - | - | - | - | - |
## Output

structured_array output with fields: cluster_index, hit_index.

| Field | DType | Unit | Meaning |
| --- | --- | --- | --- |
| `cluster_index` | `int64` | - | Index of the merged cluster, matching merged_id |
| `hit_index` | `int64` | - | Row index in the source hit_threshold array |
## Usage

### Minimal Example

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import HitMergeClustersPlugin

ctx = Context(config={"data_root": "DAQ"})
ctx.register(HitMergeClustersPlugin())
data = ctx.get_data("run_001", "hit_merge_clusters")
```

## Operational Notes

### Behavior

### Failure Modes

- Dependency data, configuration, or output contract validation may fail explicitly.
### Downstream Impact

Terminal output; no direct builtin consumer is declared.


## Maintenance

### Change Playbook

1. Keep `provides` and dependency semantics stable or update all consumers.
2. Bump `version` for behavior, configuration, or output contract changes.
3. Regenerate auto, agent, and web references after metadata changes.
### Validation

```bash
waveform-docs generate plugins-agent --plugin hit_merge_clusters
waveform-docs check coverage --strict --fail-on-warning
```
