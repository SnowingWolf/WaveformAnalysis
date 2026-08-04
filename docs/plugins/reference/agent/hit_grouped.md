---
schema_version: 1
document_type: "plugin_reference"
profile: "agent"
provides: "hit_grouped"
plugin_class: "HitGroupedPlugin"
module: "waveform_analysis.core.plugins.builtin.hit_grouped.plugin"
version: "0.5.0"
summary: "Group merged hits across channels into event-level coincidence windows."
depends_on: ["hit_merged", "hit_merged_components", "hit_threshold"]
output_kind: "dataframe"
generated: true
---
# hit_grouped

## Overview

Group merged hits across channels into event-level coincidence windows.
Plugin to group merged hits across channels using absolute hit windows.

| Item | Value |
| --- | --- |
| Provides | `hit_grouped` |
| Plugin Class | `HitGroupedPlugin` |
| Module | `waveform_analysis.core.plugins.builtin.hit_grouped.plugin` |
| Version | `0.5.0` |
| Category | 特征提取 |
| Output Kind | `dataframe` |

| Dependency | Version Constraint | Resolution | Required Fields | Description |
| --- | --- | --- | --- | --- |
| `hit_merged` | - | declared | - | Merge nearby threshold hits per channel with time-gap and max-width constraints. |
| `hit_merged_components` | - | declared | - | Return per-cluster component hit indices for hit_merged rows. |
| `hit_threshold` | - | declared | - | Threshold-only hit detector with THRESHOLD_HIT_DTYPE output. |
### How It Works


## Configuration

| Name | Type | Default | Unit | Tracked | Deprecated | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `time_window_ns` | `float` | `100.0` | - | yes | no | Maximum absolute time separation in nanoseconds for grouping hits. |
| `dt` | `int` | `None` | - | yes | no | 采样间隔（ns）。仅在输入 hit_merged 缺少 dt 字段时作为兼容补充。 |
## Output

Grouped hit coincidence table.

| Field | DType | Unit | Meaning |
| --- | --- | --- | --- |
| container | `dataframe` | - | Grouped hit coincidence table. |
## Usage

### Minimal Example

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.hit_grouped import HitGroupedPlugin

ctx = Context(config={"data_root": "DAQ"})
ctx.register(HitGroupedPlugin())
data = ctx.get_data("run_001", "hit_grouped")
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
waveform-docs generate plugins-agent --plugin hit_grouped
waveform-docs check coverage --strict --fail-on-warning
```
