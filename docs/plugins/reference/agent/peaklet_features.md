---
schema_version: 2
document_type: "plugin_reference"
profile: "agent"
provides: "peaklet_features"
plugin_class: "PeakletFeaturesPlugin"
module: "waveform_analysis.core.plugins.builtin.peaklet_features.plugin"
version: "5.0.0"
summary: "Compute peaklet waveform features from ragged signal pools."
depends_on: ["peaklet_waveforms", "peaklet_waveform_pool", "peaklets"]
declared_depends_on: ["peaklet_waveforms", "peaklet_waveform_pool", "peaklets"]
resolved_depends_on: ["peaklet_waveforms", "peaklet_waveform_pool", "peaklets"]
dependency_profile: "declared"
dependency_profile_values: {}
dependency_config_keys: []
output_kind: "structured_array"
execution_kind: "static"
narrative_source: "source"
narrative_source_reason: null
source_fingerprint: "48ec6eaa661dde02dd57860f1e35fa97d1b20268fa4bac149b83d889d58a1725"
generated: true
---
# peaklet_features

## Overview

Compute peaklet waveform features from ragged signal pools.
Compute waveform-derived features from ragged peaklet waveforms.

| Item | Value |
| --- | --- |
| Provides | `peaklet_features` |
| Plugin Class | `PeakletFeaturesPlugin` |
| Module | `waveform_analysis.core.plugins.builtin.peaklet_features.plugin` |
| Version | `5.0.0` |
| Category | 峰构建 |
| Output Container | `structured_array` |
| Execution Mode | `static` |
| Save Policy | `always` |
| Uses Run Config | no |
| Timeout | `none` |
| Side Effect | no |
| Narrative Source | `source` |
| Source Fingerprint | `48ec6eaa661dde02dd57860f1e35fa97d1b20268fa4bac149b83d889d58a1725` |

### Dependencies

默认文档画像：`declared`。

| Dependency | Version Constraint | Resolution | Required Fields | Description |
| --- | --- | --- | --- | --- |
| `peaklet_waveforms` | - | declared | - | Build peaklet waveform index rows from records-backed hit_merged samples. Supports cross-record hits via component expansion. |
| `peaklet_waveform_pool` | - | declared | - | Return the flattened float32 signal pool paired with peaklet_waveforms. Configure waveform construction on peaklet_waveforms. |
| `peaklets` | - | declared | - | Build lightweight cross-channel peaklets from hit_merged intervals. |
### How It Works

1. Compute waveform-derived features from ragged peaklet waveforms.

## Configuration

| Name | Type | Default | Unit | Tracked | Deprecated | Description |
| --- | --- | --- | --- | --- | --- | --- |
| - | - | - | - | - | - | 此插件没有插件级配置。 |
## Output

structured_array output with fields: peak_id, time_start, time_end, time_peak, center_time, rise_time, fall_time, width_25_75, ....

| Field | DType | Unit | Meaning |
| --- | --- | --- | --- |
| `peak_id` | `int64` | None | Peaklet identifier |
| `time_start` | `int64` | ps | Absolute start time of the peaklet (ps) |
| `time_end` | `int64` | ps | Absolute end time of the peaklet (ps) |
| `time_peak` | `int64` | ps | Time of the maximum sample value (ps) |
| `center_time` | `int64` | ps | Center time of the peaklet (ps) |
| `rise_time` | `float32` | ns | Rise time (ns) |
| `fall_time` | `float32` | ns | Fall time between the 50% and 90% cumulative-area quantiles (ns) |
| `width_25_75` | `float32` | ns | Width between 25% and 75% of the peak (ns) |
| `rise_time_10_50` | `float32` | ns | Rise time from 10% to 50% (ns) |
| `range_90p_area` | `float32` | ns | Time range covering 90% of the waveform area (ns) |
| `area` | `float32` | ADC counts | Total waveform area |
| `height` | `float32` | ADC counts | Maximum waveform height |
| `width` | `float32` | ns | Pulse width (ns) |
## Usage

### Minimal Example

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins import profiles

ctx = Context(config={"data_root": "DAQ", "daq_adapter": "vx2730"})
ctx.register(*profiles.cpu_default())
result = ctx.get_data("run_001", "peaklet_features")
```

示例使用 `run_id="run_001"` 和文档默认运行画像；真实数据路径与配置应以当前实验设置为准。

## Operational Notes

### Behavior

- peaklet_features bundle - provides 'peaklet_features'。
### Failure Modes

- 任一声明依赖（`peaklet_waveforms`, `peaklet_waveform_pool`, `peaklets`）缺失或字段不符合输入契约时，执行会失败。
- 配置校验或输出 schema 校验失败时，结果不会被视为有效插件产物。
### Downstream Impact

直接消费者：`peaklet_channels`、`peaks`
## Maintenance

### Change Playbook

1. 保持 `provides`、依赖和输出字段语义稳定，或同步所有下游消费者。
2. 行为、配置或输出契约改变时升级插件 `version`。
3. 修改插件源码后重新生成 Auto、Agent 和 HTML 参考。
### Validation

```bash
waveform-docs generate plugins-agent --plugin peaklet_features
waveform-docs check coverage --strict --fail-on-warning
```
