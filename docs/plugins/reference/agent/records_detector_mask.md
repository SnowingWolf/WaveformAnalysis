---
schema_version: 1
document_type: "plugin_reference"
profile: "agent"
provides: "records_detector_mask"
plugin_class: "RecordsDetectorMaskPlugin"
module: "waveform_analysis.core.plugins.builtin.records_detector_mask.plugin"
version: "0.1.0"
summary: "Bool mask for detector-channel records after channel-role splitting."
depends_on: ["records", "records_asymmetry_mask"]
output_kind: "array"
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
| Output Kind | `array` |

| Dependency | Version Constraint | Resolution | Required Fields | Description |
| --- | --- | --- | --- | --- |
| `records` | - | declared | - | Build records (event index table) from the shared internal records bundle. |
| `records_asymmetry_mask` | - | declared | - | Bool mask for waveform asymmetry selection. |
### How It Works


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
from waveform_analysis.core.plugins.builtin.records_detector_mask import RecordsDetectorMaskPlugin

ctx = Context(config={"data_root": "DAQ"})
ctx.register(RecordsDetectorMaskPlugin())
data = ctx.get_data("run_001", "records_detector_mask")
```

## Operational Notes

### Behavior

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
waveform-docs generate plugins-agent --plugin records_detector_mask
waveform-docs check coverage --strict --fail-on-warning
```
