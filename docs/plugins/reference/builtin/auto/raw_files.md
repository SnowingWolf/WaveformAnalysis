---
schema_version: 1
document_type: "plugin_reference"
profile: "auto"
provides: "raw_files"
plugin_class: "RawFileNamesPlugin"
module: "waveform_analysis.core.plugins.builtin.cpu.waveforms"
version: "0.0.2"
summary: "Scan the data directory and group raw CSV files by channel number."
depends_on: []
output_kind: "list"
generated: true
---
# raw_files

## Overview

Scan the data directory and group raw CSV files by channel number.
| Item | Value |
| --- | --- |
| Provides | `raw_files` |
| Plugin Class | `RawFileNamesPlugin` |
| Module | `waveform_analysis.core.plugins.builtin.cpu.waveforms` |
| Version | `0.0.2` |
| Category | 数据加载 |
| Accelerator | CPU (NumPy/SciPy) |
| Output Kind | `list` |

| Dependency | Version Constraint | Resolution | Required Fields | Description |
| --- | --- | --- | --- | --- |
| - | - | - | - | No declared inputs. |
### How It Works


## Configuration

| Name | Type | Default | Unit | Tracked | Deprecated | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `data_root` | `str` | `DAQ` | - | yes | no | Root directory for data |
| `daq_adapter` | `str` | `vx2730` | - | yes | no | DAQ adapter name (e.g., 'vx2730') |
## Output

Raw file paths grouped by channel.

| Field | DType | Unit | Meaning |
| --- | --- | --- | --- |
| container | `list` | - | Raw file paths grouped by channel. |
## Usage

### Minimal Example

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import RawFileNamesPlugin

ctx = Context(config={"data_root": "DAQ"})
ctx.register(RawFileNamesPlugin())
data = ctx.get_data("run_001", "raw_files")
```
### Downstream Consumers

- Terminal output; no direct builtin consumer is declared.
