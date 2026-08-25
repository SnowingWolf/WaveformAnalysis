---
schema_version: 2
document_type: "plugin_reference"
profile: "agent"
provides: "df_events"
plugin_class: "GroupedEventsPlugin"
module: "waveform_analysis.core.plugins.builtin.df_events.plugin"
version: "0.0.1"
summary: "Group events across channels within a configurable time window."
depends_on: ["df"]
declared_depends_on: ["df"]
resolved_depends_on: ["df"]
dependency_profile: "declared"
dependency_profile_values: {}
dependency_config_keys: []
output_kind: "dataframe"
execution_kind: "static"
narrative_source: "source"
narrative_source_reason: null
source_fingerprint: "d9db055c97dabb001dfa2e61ea513d922597fedeb20a34dc55d7b38aaaec1cff"
generated: true
---
# df_events

## Overview

Group events across channels within a configurable time window.
Plugin to group events by time window.

| Item | Value |
| --- | --- |
| Provides | `df_events` |
| Plugin Class | `GroupedEventsPlugin` |
| Module | `waveform_analysis.core.plugins.builtin.df_events.plugin` |
| Version | `0.0.1` |
| Category | 事件分析 |
| Output Container | `dataframe` |
| Execution Mode | `static` |
| Save Policy | `always` |
| Uses Run Config | no |
| Timeout | `none` |
| Side Effect | no |
| Narrative Source | `source` |
| Source Fingerprint | `d9db055c97dabb001dfa2e61ea513d922597fedeb20a34dc55d7b38aaaec1cff` |

### Dependencies

默认文档画像：`declared`。

| Dependency | Version Constraint | Resolution | Required Fields | Description |
| --- | --- | --- | --- | --- |
| `df` | - | declared | - | Build the initial single-channel events DataFrame. |
### How It Works

1. 按时间窗口分组多通道事件
2. 在指定的时间窗口内识别多通道同时触发的事件，并将它们分组。 支持 Numba 加速和多进程并行处理。

## Configuration

| Name | Type | Default | Unit | Tracked | Deprecated | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `time_window_ns` | `float` | `100.0` | - | yes | no | Maximum time separation in nanoseconds for grouping events. |
## Output

Grouped multi-channel event table.

| Field | DType | Unit | Meaning |
| --- | --- | --- | --- |
| container | `dataframe` | - | Grouped multi-channel event table. |
## Usage

### Minimal Example

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins import profiles

ctx = Context(config={"data_root": "DAQ", "daq_adapter": "vx2730"})
ctx.register(*profiles.cpu_default())
result = ctx.get_data("run_001", "df_events")
```

示例使用 `run_id="run_001"` 和文档默认运行画像；真实数据路径与配置应以当前实验设置为准。

## Operational Notes

### Behavior

- GroupedEventsPlugin 类实现 - 按时间窗口分组多通道事件。
### Failure Modes

- 任一声明依赖（`df`）缺失或字段不符合输入契约时，执行会失败。
- 配置校验或输出 schema 校验失败时，结果不会被视为有效插件产物。
### Downstream Impact

直接消费者：`df_paired`
## Maintenance

### Change Playbook

1. 保持 `provides`、依赖和输出字段语义稳定，或同步所有下游消费者。
2. 行为、配置或输出契约改变时升级插件 `version`。
3. 修改插件源码后重新生成 Auto、Agent 和 HTML 参考。
### Validation

```bash
waveform-docs generate plugins-agent --plugin df_events
waveform-docs check coverage --strict --fail-on-warning
```
