---
schema_version: 2
document_type: "plugin_reference"
profile: "agent"
provides: "hit_grouped"
plugin_class: "HitGroupedPlugin"
module: "waveform_analysis.core.plugins.builtin.hit_grouped.plugin"
version: "0.5.0"
summary: "Group merged hits across channels into event-level coincidence windows."
depends_on: ["hit_merged", "hit_merged_components", "hit_threshold"]
declared_depends_on: ["hit_merged", "hit_merged_components", "hit_threshold"]
resolved_depends_on: ["hit_merged", "hit_merged_components", "hit_threshold"]
dependency_profile: "declared"
dependency_profile_values: {}
dependency_config_keys: []
output_kind: "dataframe"
execution_kind: "static"
narrative_source: "source"
narrative_source_reason: null
source_fingerprint: "df20ffd52da9fd37ad428c9ec21b7ceab4aea5b856b0129a6dc79ce3aa49d0db"
generated: true
---
# hit_grouped

## Overview

Group merged hits across channels into event-level coincidence windows.
Plugin to group merged hits across channels using absolute hit windows.

| Item | Value |
| --- | --- |
| Provides | `hit_grouped` |
| Plugin Class | `HitGroupedPlugin` |
| Module | `waveform_analysis.core.plugins.builtin.hit_grouped.plugin` |
| Version | `0.5.0` |
| Category | 特征提取 |
| Output Container | `dataframe` |
| Execution Mode | `static` |
| Save Policy | `always` |
| Uses Run Config | no |
| Timeout | `none` |
| Side Effect | no |
| Narrative Source | `source` |
| Source Fingerprint | `df20ffd52da9fd37ad428c9ec21b7ceab4aea5b856b0129a6dc79ce3aa49d0db` |

### Dependencies

默认文档画像：`declared`。

| Dependency | Version Constraint | Resolution | Required Fields | Description |
| --- | --- | --- | --- | --- |
| `hit_merged` | - | declared | - | Merge nearby threshold hits per channel with time-gap and max-width constraints. |
| `hit_merged_components` | - | declared | - | Return per-cluster component hit indices for hit_merged rows. |
| `hit_threshold` | - | declared | - | Threshold-only hit detector with THRESHOLD_HIT_DTYPE output. |
### How It Works

1. Plugin to group merged hits across channels using absolute hit windows.

## Configuration

| Name | Type | Default | Unit | Tracked | Deprecated | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `time_window_ns` | `float` | `100.0` | - | yes | no | Maximum absolute time separation in nanoseconds for grouping hits. |
| `dt` | `int` | `None` | - | yes | no | 采样间隔（ns）。仅在输入 hit_merged 缺少 dt 字段时作为兼容补充。 |
## Output

Grouped hit coincidence table.

| Field | DType | Unit | Meaning |
| --- | --- | --- | --- |
| container | `dataframe` | - | Grouped hit coincidence table. |
## Usage

### Minimal Example

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins import profiles

ctx = Context(config={"data_root": "DAQ", "daq_adapter": "vx2730"})
ctx.register(*profiles.cpu_default())
result = ctx.get_data("run_001", "hit_grouped")
```

示例使用 `run_id="run_001"` 和文档默认运行画像；真实数据路径与配置应以当前实验设置为准。

## Operational Notes

### Behavior

- HitGroupedPlugin 类实现 - 按绝对 hit 窗口将多通道 merged hits 分组。
### Failure Modes

- 任一声明依赖（`hit_merged`, `hit_merged_components`, `hit_threshold`）缺失或字段不符合输入契约时，执行会失败。
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
waveform-docs generate plugins-agent --plugin hit_grouped
waveform-docs check coverage --strict --fail-on-warning
```
