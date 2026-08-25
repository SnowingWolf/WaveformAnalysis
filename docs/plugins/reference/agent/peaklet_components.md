---
schema_version: 2
document_type: "plugin_reference"
profile: "agent"
provides: "peaklet_components"
plugin_class: "PeakletComponentsPlugin"
module: "waveform_analysis.core.plugins.builtin.peaklet_components.plugin"
version: "1.4.0"
summary: "Return per-peaklet component hit_merged indices."
depends_on: ["hit_merged"]
declared_depends_on: ["hit_merged"]
resolved_depends_on: ["hit_merged"]
dependency_profile: "declared"
dependency_profile_values: {}
dependency_config_keys: []
output_kind: "structured_array"
execution_kind: "static"
narrative_source: "source"
narrative_source_reason: null
source_fingerprint: "b7af9eb03d7904b533669172b2723fb3dda0a7ee6919db3fe259dd89e149d3d7"
generated: true
---
# peaklet_components

## Overview

Return per-peaklet component hit_merged indices.
Return flat peaklet-to-hit_merged membership rows.

| Item | Value |
| --- | --- |
| Provides | `peaklet_components` |
| Plugin Class | `PeakletComponentsPlugin` |
| Module | `waveform_analysis.core.plugins.builtin.peaklet_components.plugin` |
| Version | `1.4.0` |
| Category | 峰构建 |
| Output Container | `structured_array` |
| Execution Mode | `static` |
| Save Policy | `always` |
| Uses Run Config | no |
| Timeout | `none` |
| Side Effect | no |
| Narrative Source | `source` |
| Source Fingerprint | `b7af9eb03d7904b533669172b2723fb3dda0a7ee6919db3fe259dd89e149d3d7` |

### Dependencies

默认文档画像：`declared`。

| Dependency | Version Constraint | Resolution | Required Fields | Description |
| --- | --- | --- | --- | --- |
| `hit_merged` | - | declared | - | Merge nearby threshold hits per channel with time-gap and max-width constraints. |
### How It Works

1. Return flat peaklet-to-hit_merged membership rows.

## Configuration

| Name | Type | Default | Unit | Tracked | Deprecated | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `time_window_ns` | `float` | `100.0` | - | yes | no | 跨通道 peaklet 合并时间窗口 |
| `max_total_width_ns` | `float` | `10000.0` | - | yes | no | peaklet 最大总宽度 |
| `dt` | `int` | `None` | - | yes | no | 保留兼容配置；优先使用输入 hit_merged 的 dt |
## Output

structured_array output with fields: peak_id, merged_index.

| Field | DType | Unit | Meaning |
| --- | --- | --- | --- |
| `peak_id` | `int64` | None | Peaklet identifier, matching the row index in the peaklets table |
| `merged_index` | `int64` | None | Index of the hit_merged row belonging to this peaklet |
## Usage

### Minimal Example

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins import profiles

ctx = Context(config={"data_root": "DAQ", "daq_adapter": "vx2730"})
ctx.register(*profiles.cpu_default())
result = ctx.get_data("run_001", "peaklet_components")
```

示例使用 `run_id="run_001"` 和文档默认运行画像；真实数据路径与配置应以当前实验设置为准。

## Operational Notes

### Behavior

- peaklet_components bundle - provides 'peaklet_components'。
### Failure Modes

- 任一声明依赖（`hit_merged`）缺失或字段不符合输入契约时，执行会失败。
- 配置校验或输出 schema 校验失败时，结果不会被视为有效插件产物。
### Downstream Impact

直接消费者：`peaklet_channels`、`peaklet_waveforms`、`peaklets`
## Maintenance

### Change Playbook

1. 保持 `provides`、依赖和输出字段语义稳定，或同步所有下游消费者。
2. 行为、配置或输出契约改变时升级插件 `version`。
3. 修改插件源码后重新生成 Auto、Agent 和 HTML 参考。
### Validation

```bash
waveform-docs generate plugins-agent --plugin peaklet_components
waveform-docs check coverage --strict --fail-on-warning
```
