---
schema_version: 1
document_type: "plugin_reference"
profile: "auto"
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
| `hit_merged` | - | declared | - | - |
| `hit_threshold` | - | declared | - | - |
## Configuration

| Name | Type | Default | Unit | Tracked | Deprecated | Description |
| --- | --- | --- | --- | --- | --- | --- |
| - | - | - | - | - | - | - |
## Output

| Field | DType | Unit | Meaning |
| --- | --- | --- | --- |
| `cluster_index` | `int64` | - | - |
| `hit_index` | `int64` | - | - |
## Usage

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import HitMergeClustersPlugin

ctx = Context(config={"data_root": "DAQ"})
ctx.register(HitMergeClustersPlugin())
data = ctx.get_data("run_001", "hit_merge_clusters")
```
