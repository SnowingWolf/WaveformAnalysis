---
schema_version: 2
document_type: "plugin_reference"
profile: "auto"
provides: "df_paired"
plugin_class: "PairedEventsPlugin"
module: "waveform_analysis.core.plugins.builtin.df_paired.plugin"
version: "0.0.1"
summary: "Pair grouped events across channels for coincidence analysis."
depends_on: ["df_events"]
declared_depends_on: ["df_events"]
resolved_depends_on: ["df_events"]
dependency_profile: "declared"
dependency_profile_values: {}
dependency_config_keys: []
output_kind: "dataframe"
execution_kind: "static"
narrative_source: "source"
narrative_source_reason: null
source_fingerprint: "117c8bed7f0d8fefd58975b248ce4eeec9fd864a04f022c18ec6a2e8b27c50b9"
generated: true
---
# df_paired

## Overview

Pair grouped events across channels for coincidence analysis.
Plugin to pair events across channels.

| Item | Value |
| --- | --- |
| Provides | `df_paired` |
| Plugin Class | `PairedEventsPlugin` |
| Module | `waveform_analysis.core.plugins.builtin.df_paired.plugin` |
| Version | `0.0.1` |
| Category | 事件分析 |
| Output Container | `dataframe` |
| Execution Mode | `static` |
| Save Policy | `always` |
| Uses Run Config | no |
| Timeout | `none` |
| Side Effect | no |
| Narrative Source | `source` |
| Source Fingerprint | `117c8bed7f0d8fefd58975b248ce4eeec9fd864a04f022c18ec6a2e8b27c50b9` |

### Dependencies

默认文档画像：`declared`。

| Dependency | Version Constraint | Resolution | Required Fields | Description |
| --- | --- | --- | --- | --- |
| `df_events` | - | declared | - | Group events across channels within a configurable time window. |
### How It Works

1. 配对跨通道的符合事件
2. 识别满足时间符合条件的多通道事件对，用于符合测量分析。

## Configuration

| Name | Type | Default | Unit | Tracked | Deprecated | Description |
| --- | --- | --- | --- | --- | --- | --- |
| - | - | - | - | - | - | 此插件没有插件级配置。 |
## Output

Paired coincidence event table.

| Field | DType | Unit | Meaning |
| --- | --- | --- | --- |
| container | `dataframe` | - | Paired coincidence event table. |
## Usage

### Minimal Example

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins import profiles

ctx = Context(config={"data_root": "DAQ", "daq_adapter": "vx2730"})
ctx.register(*profiles.cpu_default())
result = ctx.get_data("run_001", "df_paired")
```

示例使用 `run_id="run_001"` 和文档默认运行画像；真实数据路径与配置应以当前实验设置为准。

### Downstream Consumers

- 没有声明直接的内置消费者。
