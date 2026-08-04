---
schema_version: 1
document_type: "plugin_reference"
profile: "agent"
provides: "raw_files"
plugin_class: "RawFileNamesPlugin"
module: "waveform_analysis.core.plugins.builtin.raw_files.plugin"
version: "0.0.2"
summary: "Scan the data directory and group raw CSV files by channel number."
depends_on: []
output_kind: "list"
generated: true
---
# raw_files

## Overview

Scan the data directory and group raw CSV files by channel number.
Plugin to find raw CSV files.

| Item | Value |
| --- | --- |
| Provides | `raw_files` |
| Plugin Class | `RawFileNamesPlugin` |
| Module | `waveform_analysis.core.plugins.builtin.raw_files.plugin` |
| Version | `0.0.2` |
| Category | 数据加载 |
| Output Kind | `list` |

| Dependency | Version Constraint | Resolution | Required Fields | Description |
| --- | --- | --- | --- | --- |
| - | - | - | - | No declared inputs. |
### How It Works

1. 扫描数据目录并按通道分组原始 CSV 文件
2. 从配置的数据目录中查找指定运行的所有原始波形文件，并按通道号分组。 支持 DAQ 集成，可以直接从 DAQ 元数据中获取文件列表。 支持通过 daq_adapter 参数指定 DAQ 适配器来处理不同格式。 通道选择由 DAQ 适配器或 DAQ 元数据决定，不再通过插件配置裁剪。

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
from waveform_analysis.core.plugins.builtin.raw_files import RawFileNamesPlugin

ctx = Context(config={"data_root": "DAQ"})
ctx.register(RawFileNamesPlugin())
data = ctx.get_data("run_001", "raw_files")
```

## Operational Notes

### Behavior

- 扫描数据目录并按通道分组原始 CSV 文件
- 从配置的数据目录中查找指定运行的所有原始波形文件，并按通道号分组。 支持 DAQ 集成，可以直接从 DAQ 元数据中获取文件列表。 支持通过 daq_adapter 参数指定 DAQ 适配器来处理不同格式。 通道选择由 DAQ 适配器或 DAQ 元数据决定，不再通过插件配置裁剪。
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
waveform-docs generate plugins-agent --plugin raw_files
waveform-docs check coverage --strict --fail-on-warning
```
