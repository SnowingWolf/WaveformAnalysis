---
schema_version: 2
document_type: "plugin_reference"
profile: "agent"
provides: "records_detector_mask"
plugin_class: "RecordsDetectorMaskPlugin"
module: "waveform_analysis.core.plugins.builtin.records_detector_mask.plugin"
version: "0.1.0"
summary: "Bool mask for detector-channel records after channel-role splitting."
depends_on: ["records", "records_asymmetry_mask"]
declared_depends_on: ["records", "records_asymmetry_mask"]
resolved_depends_on: ["records", "records_asymmetry_mask"]
dependency_profile: "declared"
dependency_profile_values: {}
dependency_config_keys: []
output_kind: "array"
execution_kind: "static"
narrative_source: "source"
narrative_source_reason: null
source_fingerprint: "488f69c243caafa119701f392beab66142cc9074440189557fcd779381510df8"
generated: true
---
# records_detector_mask

## Overview

Bool mask for detector-channel records after channel-role splitting.
Bool mask for records that should enter normal detector hit finding.

| Item | Value |
| --- | --- |
| Provides | `records_detector_mask` |
| Plugin Class | `RecordsDetectorMaskPlugin` |
| Module | `waveform_analysis.core.plugins.builtin.records_detector_mask.plugin` |
| Version | `0.1.0` |
| Category | 记录处理 |
| Output Container | `array` |
| Execution Mode | `static` |
| Save Policy | `always` |
| Uses Run Config | no |
| Timeout | `none` |
| Side Effect | no |
| Narrative Source | `source` |
| Source Fingerprint | `488f69c243caafa119701f392beab66142cc9074440189557fcd779381510df8` |

### Dependencies

默认文档画像：`declared`。

| Dependency | Version Constraint | Resolution | Required Fields | Description |
| --- | --- | --- | --- | --- |
| `records` | - | declared | - | Build records (event index table) from the shared internal records bundle. |
| `records_asymmetry_mask` | - | declared | - | Bool mask for waveform asymmetry selection. |
### How It Works

1. Bool mask for records that should enter normal detector hit finding.

## Configuration

| Name | Type | Default | Unit | Tracked | Deprecated | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `channel_config` | `dict` | `None` | - | yes | no | 按 (board, channel) 的通道角色配置；role='detector' 进入正常 hit，role='veto' 仅作为 veto 通道保留。 |
## Output

array output with fields: value.

| Field | DType | Unit | Meaning |
| --- | --- | --- | --- |
| `value` | `bool` | None | Boolean mask: True for records assigned to detector channel role |
## Usage

### Minimal Example

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins import profiles

ctx = Context(config={"data_root": "DAQ", "daq_adapter": "vx2730"})
ctx.register(*profiles.cpu_default())
result = ctx.get_data("run_001", "records_detector_mask")
```

示例使用 `run_id="run_001"` 和文档默认运行画像；真实数据路径与配置应以当前实验设置为准。

## Operational Notes

### Behavior

- RecordsDetectorMaskPlugin 类实现 - detector 通道角色掩码。
### Failure Modes

- 任一声明依赖（`records`, `records_asymmetry_mask`）缺失或字段不符合输入契约时，执行会失败。
- 配置校验或输出 schema 校验失败时，结果不会被视为有效插件产物。
### Downstream Impact

没有声明直接的内置消费者。

## Maintenance

### Change Playbook

1. 保持 `provides`、依赖和输出字段语义稳定，或同步所有下游消费者。
2. 行为、配置或输出契约改变时升级插件 `version`。
3. 修改插件源码后重新生成 Auto、Agent 和 HTML 参考。
### Validation

```bash
waveform-docs generate plugins-agent --plugin records_detector_mask
waveform-docs check coverage --strict --fail-on-warning
```
