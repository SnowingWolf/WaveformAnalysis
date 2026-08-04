---
schema_version: 1
document_type: "plugin_reference"
profile: "agent"
provides: "df"
plugin_class: "DataFramePlugin"
module: "waveform_analysis.core.plugins.builtin.cpu.dataframe"
version: "1.7.0"
summary: "Build the initial single-channel events DataFrame."
depends_on: []
output_kind: "dataframe"
generated: true
---
# df

## Overview

Build the initial single-channel events DataFrame.
Plugin to build the initial single-channel events DataFrame.

| Item | Value |
| --- | --- |
| Provides | `df` |
| Plugin Class | `DataFramePlugin` |
| Module | `waveform_analysis.core.plugins.builtin.cpu.dataframe` |
| Version | `1.7.0` |
| Category | 数据导出 |
| Accelerator | CPU (NumPy/SciPy) |
| Output Kind | `dataframe` |

| Dependency | Version Constraint | Resolution | Required Fields | Description |
| --- | --- | --- | --- | --- |
| - | - | - | - | No declared inputs. |
### How It Works

1. 构建单通道事件的 DataFrame
2. 整合结构化波形与 height/area 特征，构建包含所有事件信息的 pandas DataFrame。

## Configuration

| Name | Type | Default | Unit | Tracked | Deprecated | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `use_filtered` | `bool` | `False` | - | yes | no | 是否使用 filtered_waveforms（需要先注册 FilteredWaveformsPlugin） |
| `wave_source` | `str` | `auto` | - | yes | no | 波形数据源: auto\|records\|st_waveforms\|filtered_waveforms |
| `gain_adc_per_pe` | `dict` | `None` | - | yes | no | 按硬件通道配置 ADC/PE 增益，键请使用 "board:channel"，例如 {"0:0": 12.5, "0:1": 13.2}。设置后会新增 area_pe/height_pe 列。 |
## Output

Single-channel event table.

| Field | DType | Unit | Meaning |
| --- | --- | --- | --- |
| container | `dataframe` | - | Single-channel event table. |
## Usage

### Minimal Example

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import DataFramePlugin

ctx = Context(config={"data_root": "DAQ"})
ctx.register(DataFramePlugin())
data = ctx.get_data("run_001", "df")
```

## Operational Notes

### Behavior

- 构建单通道事件的 DataFrame
- 整合结构化波形与 height/area 特征，构建包含所有事件信息的 pandas DataFrame。
### Failure Modes

- Dependency data, configuration, or output contract validation may fail explicitly.
### Downstream Impact

Consumers: `df_events`

## Maintenance

### Change Playbook

1. Keep `provides` and dependency semantics stable or update all consumers.
2. Bump `version` for behavior, configuration, or output contract changes.
3. Regenerate auto, agent, and web references after metadata changes.
### Validation

```bash
waveform-docs generate plugins-agent --plugin df
waveform-docs check coverage --strict --fail-on-warning
```
