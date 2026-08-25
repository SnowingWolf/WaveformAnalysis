---
schema_version: 2
document_type: "plugin_reference"
profile: "agent"
provides: "df"
plugin_class: "DataFramePlugin"
module: "waveform_analysis.core.plugins.builtin.df.plugin"
version: "1.7.0"
summary: "Build the initial single-channel events DataFrame."
depends_on: []
declared_depends_on: []
resolved_depends_on: ["records", "basic_features"]
dependency_profile: "documentation-default-v1"
dependency_profile_values: {"daq_adapter": "vx2730", "use_filtered": false, "wave_source": "records"}
dependency_config_keys: ["use_filtered", "wave_source"]
output_kind: "dataframe"
execution_kind: "static"
narrative_source: "source"
narrative_source_reason: null
source_fingerprint: "04fa2ea58f5a365441622f84bd12bbcfe8288ffe73fb37e5bdc2c242dc1c7407"
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
| Module | `waveform_analysis.core.plugins.builtin.df.plugin` |
| Version | `1.7.0` |
| Category | 数据导出 |
| Output Container | `dataframe` |
| Execution Mode | `static` |
| Save Policy | `always` |
| Uses Run Config | yes |
| Timeout | `none` |
| Side Effect | no |
| Narrative Source | `source` |
| Source Fingerprint | `04fa2ea58f5a365441622f84bd12bbcfe8288ffe73fb37e5bdc2c242dc1c7407` |

### Dependencies

默认文档画像：`documentation-default-v1`（{"daq_adapter": "vx2730", "use_filtered": false, "wave_source": "records"}）。
该插件通过 `resolve_depends_on(context, run_id)` 动态解析依赖；可能影响解析的配置键：`use_filtered`, `wave_source`。

| Dependency | Version Constraint | Resolution | Required Fields | Description |
| --- | --- | --- | --- | --- |
| `records` | - | dynamic-default | - | Build records (event index table) from the shared internal records bundle. |
| `basic_features` | - | dynamic-default | - | Compute basic height, amplitude, area, and max-abs-diff features from waveform data. |
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
from waveform_analysis.core.plugins import profiles

ctx = Context(config={"data_root": "DAQ", "daq_adapter": "vx2730"})
ctx.register(*profiles.cpu_default())
result = ctx.get_data("run_001", "df")
```

示例使用 `run_id="run_001"` 和文档默认运行画像；真实数据路径与配置应以当前实验设置为准。

## Operational Notes

### Behavior

- DataFrame Plugin - DataFrame 构建插件
- **加速器**: CPU (NumPy/Pandas) **功能**: 构建单通道事件的 DataFrame
### Failure Modes

- `df` 的实际输入由 `resolve_depends_on(context, run_id)` 决定；默认画像之外的配置需要重新确认依赖是否可用。
- 动态依赖无法解析、所需配置不合法或上游产物缺失时，插件不会生成有效输出。
### Downstream Impact

直接消费者：`df_events`
## Maintenance

### Change Playbook

1. 保持 `provides`、依赖和输出字段语义稳定，或同步所有下游消费者。
2. 行为、配置或输出契约改变时升级插件 `version`。
3. 修改插件源码后重新生成 Auto、Agent 和 HTML 参考。
### Validation

```bash
waveform-docs generate plugins-agent --plugin df
waveform-docs check coverage --strict --fail-on-warning
```
