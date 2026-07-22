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
| `df` | - | declared | - | - |
## Configuration

| Name | Type | Default | Unit | Tracked | Deprecated | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `time_window_ns` | `float` | `100.0` | - | yes | no | Maximum time separation in nanoseconds for grouping events. |
## Output

| Field | DType | Unit | Meaning |
| --- | --- | --- | --- |
| - | `dataframe` | - | Group events across channels within a configurable time window. |
## Usage

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import GroupedEventsPlugin

ctx = Context(config={"data_root": "DAQ"})
ctx.register(GroupedEventsPlugin())
data = ctx.get_data("run_001", "df_events")
```

## Operational Notes

### Behavior

- Event Analysis Plugins - 事件分组与配对插件

**加速器**: CPU (NumPy/Numba)
**功能**: 多通道事件的时间窗口分组和符合配对

本模块包含两个相关的事件分析插件：
- GroupedEventsPlugin: 按时间窗口分组多通道事件
- PairedEventsPlugin: 配对跨通道的符合事件

注意：HitGroupedPlugin 已迁移到 waveform_analysis.core.plugins.builtin.hit.hit_grouped
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
waveform-docs generate plugins-agent --plugin df_events
waveform-docs check coverage --strict --fail-on-warning
```
