---
schema_version: 2
document_type: "plugin_reference"
profile: "auto"
provides: "raw_files"
plugin_class: "RawFileNamesPlugin"
module: "waveform_analysis.core.plugins.builtin.raw_files.plugin"
version: "0.0.2"
summary: "Scan the data directory and group raw CSV files by channel number."
depends_on: []
declared_depends_on: []
resolved_depends_on: []
dependency_profile: "declared"
dependency_profile_values: {}
dependency_config_keys: []
output_kind: "list"
execution_kind: "static"
narrative_source: "source"
narrative_source_reason: null
source_fingerprint: "5693beea05d1d48c7db0fc791209f50944fc98c6b6441de0b9c7a2e9d28c20b3"
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
| Output Container | `list` |
| Execution Mode | `static` |
| Save Policy | `never` |
| Uses Run Config | no |
| Timeout | `none` |
| Side Effect | no |
| Narrative Source | `source` |
| Source Fingerprint | `5693beea05d1d48c7db0fc791209f50944fc98c6b6441de0b9c7a2e9d28c20b3` |

### Dependencies

默认文档画像：`declared`。

| Dependency | Version Constraint | Resolution | Required Fields | Description |
| --- | --- | --- | --- | --- |
| - | - | declared | - | 无输入依赖。 |
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
from waveform_analysis.core.plugins import profiles

ctx = Context(config={"data_root": "DAQ", "daq_adapter": "vx2730"})
ctx.register(*profiles.cpu_default())
result = ctx.get_data("run_001", "raw_files")
```

示例使用 `run_id="run_001"` 和文档默认运行画像；真实数据路径与配置应以当前实验设置为准。

### Downstream Consumers

- `records`
- `st_waveforms`
- `wave_pool`
