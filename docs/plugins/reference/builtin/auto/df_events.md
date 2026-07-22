---
schema_version: 1
document_type: "plugin_reference"
profile: "auto"
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
