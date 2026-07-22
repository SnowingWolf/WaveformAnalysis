---
schema_version: 1
document_type: "plugin_reference"
profile: "agent"
provides: "hit_merged_components"
plugin_class: "HitMergedComponentsPlugin"
module: "waveform_analysis.core.plugins.builtin.hit.hit_merge"
version: "1.1.0"
summary: "Return per-cluster component hit indices for hit_merged rows."
depends_on: ["hit_merged", "hit_threshold"]
output_kind: "structured_array"
generated: true
---
# hit_merged_components

## Overview

Return per-cluster component hit indices for hit_merged rows.

| Item | Value |
| --- | --- |
| Provides | `hit_merged_components` |
| Plugin Class | `HitMergedComponentsPlugin` |
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
| `validate_components` | `bool` | `False` | - | yes | no | 校验 hit_merged 的 component_offset/component_count 与 cluster rows 是否一致。 |
## Output

| Field | DType | Unit | Meaning |
| --- | --- | --- | --- |
| `merged_index` | `int64` | - | - |
| `hit_index` | `int64` | - | - |
## Usage

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import HitMergedComponentsPlugin

ctx = Context(config={"data_root": "DAQ"})
ctx.register(HitMergedComponentsPlugin())
data = ctx.get_data("run_001", "hit_merged_components")
```

## Operational Notes

### Behavior

- Hit Merge Plugin - 合并临近 hit（同通道，允许跨波形/跨文件）
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
waveform-docs generate plugins-agent --plugin hit_merged_components
waveform-docs check coverage --strict --fail-on-warning
```
