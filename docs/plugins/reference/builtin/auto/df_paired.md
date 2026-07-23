---
schema_version: 1
document_type: "plugin_reference"
profile: "auto"
provides: "df_paired"
plugin_class: "PairedEventsPlugin"
module: "waveform_analysis.core.plugins.builtin.cpu.event_analysis"
version: "0.0.1"
summary: "Pair grouped events across channels for coincidence analysis."
depends_on: ["df_events"]
output_kind: "dataframe"
generated: true
---
# df_paired

## Overview

Pair grouped events across channels for coincidence analysis.
| Item | Value |
| --- | --- |
| Provides | `df_paired` |
| Plugin Class | `PairedEventsPlugin` |
| Module | `waveform_analysis.core.plugins.builtin.cpu.event_analysis` |
| Version | `0.0.1` |
| Category | 事件分析 |
| Accelerator | CPU (NumPy/SciPy) |
| Output Kind | `dataframe` |

| Dependency | Version Constraint | Resolution | Required Fields | Description |
| --- | --- | --- | --- | --- |
| `df_events` | - | declared | - | Group events across channels within a configurable time window. |
### How It Works


## Configuration

| Name | Type | Default | Unit | Tracked | Deprecated | Description |
| --- | --- | --- | --- | --- | --- | --- |
| - | - | - | - | - | - | - |
## Output

Paired coincidence event table.

| Field | DType | Unit | Meaning |
| --- | --- | --- | --- |
| container | `dataframe` | - | Paired coincidence event table. |
## Usage

### Minimal Example

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import PairedEventsPlugin

ctx = Context(config={"data_root": "DAQ"})
ctx.register(PairedEventsPlugin())
data = ctx.get_data("run_001", "df_paired")
```
### Downstream Consumers

- Terminal output; no direct builtin consumer is declared.
