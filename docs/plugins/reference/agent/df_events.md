---
schema_version: 1
document_type: "plugin_reference"
profile: "agent"
provides: "df_events"
plugin_class: "GroupedEventsPlugin"
module: "waveform_analysis.core.plugins.builtin.cpu.event_analysis"
version: "0.0.1"
summary: "Group events across channels within a configurable time window."
depends_on: ["df"]
output_kind: "dataframe"
generated: true
---
# df_events

## Overview

Group events across channels within a configurable time window.
| Item | Value |
| --- | --- |
| Provides | `df_events` |
| Plugin Class | `GroupedEventsPlugin` |
| Module | `waveform_analysis.core.plugins.builtin.cpu.event_analysis` |
| Version | `0.0.1` |
| Category | 事件分析 |
| Accelerator | CPU (NumPy/SciPy) |
| Output Kind | `dataframe` |

| Dependency | Version Constraint | Resolution | Required Fields | Description |
| --- | --- | --- | --- | --- |
| `df` | - | declared | - | Build the initial single-channel events DataFrame. |
### How It Works


## Configuration

| Name | Type | Default | Unit | Tracked | Deprecated | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `time_window_ns` | `float` | `100.0` | - | yes | no | Maximum time separation in nanoseconds for grouping events. |
## Output

Grouped multi-channel event table.

| Field | DType | Unit | Meaning |
| --- | --- | --- | --- |
| container | `dataframe` | - | Grouped multi-channel event table. |
## Usage

### Minimal Example

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import GroupedEventsPlugin

ctx = Context(config={"data_root": "DAQ"})
ctx.register(GroupedEventsPlugin())
data = ctx.get_data("run_001", "df_events")
```

## Operational Notes

### Behavior

- 按时间窗口分组多通道事件
- 在指定的时间窗口内识别多通道同时触发的事件，并将它们分组。 支持 Numba 加速和多进程并行处理。
### Failure Modes

- Dependency data, configuration, or output contract validation may fail explicitly.
### Downstream Impact

Consumers: `df_paired`

## Maintenance

### Change Playbook

1. Keep `provides` and dependency semantics stable or update all consumers.
2. Bump `version` for behavior, configuration, or output contract changes.
3. Regenerate auto, agent, and web references after metadata changes.
### Validation

```bash
waveform-docs generate plugins-agent --plugin df_events
waveform-docs check coverage --strict --fail-on-warning
```
