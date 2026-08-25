---
schema_version: 2
document_type: "plugin_reference"
profile: "agent"
provides: "hit_merged_components"
plugin_class: "HitMergedComponentsPlugin"
module: "waveform_analysis.core.plugins.builtin.hit_merged_components.plugin"
version: "1.1.0"
summary: "Return per-cluster component hit indices for hit_merged rows."
depends_on: ["hit_merged", "hit_threshold"]
declared_depends_on: ["hit_merged", "hit_threshold"]
resolved_depends_on: ["hit_merged", "hit_threshold"]
dependency_profile: "declared"
dependency_profile_values: {}
dependency_config_keys: []
output_kind: "structured_array"
execution_kind: "static"
narrative_source: "source"
narrative_source_reason: null
source_fingerprint: "9ec3069a90ba7e34e486ace53d577caf533f54668423fe3533770552cedd2db7"
generated: true
---
# hit_merged_components

## Overview

Return per-cluster component hit indices for hit_merged rows.
Return flat component hit indices for each hit_merged cluster.

| Item | Value |
| --- | --- |
| Provides | `hit_merged_components` |
| Plugin Class | `HitMergedComponentsPlugin` |
| Module | `waveform_analysis.core.plugins.builtin.hit_merged_components.plugin` |
| Version | `1.1.0` |
| Category | 特征提取 |
| Output Container | `structured_array` |
| Execution Mode | `static` |
| Save Policy | `always` |
| Uses Run Config | no |
| Timeout | `none` |
| Side Effect | no |
| Narrative Source | `source` |
| Source Fingerprint | `9ec3069a90ba7e34e486ace53d577caf533f54668423fe3533770552cedd2db7` |

### Dependencies

默认文档画像：`declared`。

| Dependency | Version Constraint | Resolution | Required Fields | Description |
| --- | --- | --- | --- | --- |
| `hit_merged` | - | declared | - | Merge nearby threshold hits per channel with time-gap and max-width constraints. |
| `hit_threshold` | - | declared | - | Threshold-only hit detector with THRESHOLD_HIT_DTYPE output. |
### How It Works

1. Return flat component hit indices for each hit_merged cluster.

## Configuration

| Name | Type | Default | Unit | Tracked | Deprecated | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `validate_components` | `bool` | `False` | - | yes | no | 校验 hit_merged 的 component_offset/component_count 与 cluster rows 是否一致。 |
## Output

structured_array output with fields: merged_index, hit_index.

| Field | DType | Unit | Meaning |
| --- | --- | --- | --- |
| `merged_index` | `int64` | None | Index of the merged hit record |
| `hit_index` | `int64` | None | Row index in the source hit_threshold array |
## Usage

### Minimal Example

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins import profiles

ctx = Context(config={"data_root": "DAQ", "daq_adapter": "vx2730"})
ctx.register(*profiles.cpu_default())
result = ctx.get_data("run_001", "hit_merged_components")
```

示例使用 `run_id="run_001"` 和文档默认运行画像；真实数据路径与配置应以当前实验设置为准。

## Operational Notes

### Behavior

- HitMergedComponentsPlugin 类实现 - 展开每个 hit_merged cluster 的 component hit 索引。
### Failure Modes

- 任一声明依赖（`hit_merged`, `hit_threshold`）缺失或字段不符合输入契约时，执行会失败。
- 配置校验或输出 schema 校验失败时，结果不会被视为有效插件产物。
### Downstream Impact

直接消费者：`hit_grouped`、`hit_merged_features`、`peaklet_channels`、`peaklet_waveforms`
## Maintenance

### Change Playbook

1. 保持 `provides`、依赖和输出字段语义稳定，或同步所有下游消费者。
2. 行为、配置或输出契约改变时升级插件 `version`。
3. 修改插件源码后重新生成 Auto、Agent 和 HTML 参考。
### Validation

```bash
waveform-docs generate plugins-agent --plugin hit_merged_components
waveform-docs check coverage --strict --fail-on-warning
```
