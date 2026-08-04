---
schema_version: 1
document_type: "plugin_reference"
profile: "agent"
provides: "peaklet_components"
plugin_class: "PeakletComponentsPlugin"
module: "waveform_analysis.core.plugins.builtin.peaklet_components.plugin"
version: "1.4.0"
summary: "Return per-peaklet component hit_merged indices."
depends_on: ["hit_merged"]
output_kind: "structured_array"
generated: true
---
# peaklet_components

## Overview

Return per-peaklet component hit_merged indices.
Return flat peaklet-to-hit_merged membership rows.

| Item | Value |
| --- | --- |
| Provides | `peaklet_components` |
| Plugin Class | `PeakletComponentsPlugin` |
| Module | `waveform_analysis.core.plugins.builtin.peaklet_components.plugin` |
| Version | `1.4.0` |
| Category | 峰构建 |
| Output Kind | `structured_array` |

| Dependency | Version Constraint | Resolution | Required Fields | Description |
| --- | --- | --- | --- | --- |
| `hit_merged` | - | declared | - | Merge nearby threshold hits per channel with time-gap and max-width constraints. |
### How It Works


## Configuration

| Name | Type | Default | Unit | Tracked | Deprecated | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `time_window_ns` | `float` | `100.0` | - | yes | no | 跨通道 peaklet 合并时间窗口 |
| `max_total_width_ns` | `float` | `10000.0` | - | yes | no | peaklet 最大总宽度 |
| `dt` | `int` | `None` | - | yes | no | 保留兼容配置；优先使用输入 hit_merged 的 dt |
## Output

structured_array output with fields: peak_id, merged_index.

| Field | DType | Unit | Meaning |
| --- | --- | --- | --- |
| `peak_id` | `int64` | None | Peaklet identifier, matching the row index in the peaklets table |
| `merged_index` | `int64` | None | Index of the hit_merged row belonging to this peaklet |
## Usage

### Minimal Example

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.peaklet_components import PeakletComponentsPlugin

ctx = Context(config={"data_root": "DAQ"})
ctx.register(PeakletComponentsPlugin())
data = ctx.get_data("run_001", "peaklet_components")
```

## Operational Notes

### Behavior

### Failure Modes

- Dependency data, configuration, or output contract validation may fail explicitly.
### Downstream Impact

Consumers: `peaklet_channels`, `peaklets`

## Maintenance

### Change Playbook

1. Keep `provides` and dependency semantics stable or update all consumers.
2. Bump `version` for behavior, configuration, or output contract changes.
3. Regenerate auto, agent, and web references after metadata changes.
### Validation

```bash
waveform-docs generate plugins-agent --plugin peaklet_components
waveform-docs check coverage --strict --fail-on-warning
```
