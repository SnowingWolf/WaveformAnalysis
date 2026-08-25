---
schema_version: 2
document_type: "plugin_reference"
profile: "agent"
provides: "hit_merge_clusters"
plugin_class: "HitMergeClustersPlugin"
module: "waveform_analysis.core.plugins.builtin.hit_merge_clusters.plugin"
version: "1.1.0"
summary: "Export cluster membership rows using the authoritative hit_merged configuration."
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
source_fingerprint: "d1fae75c79a4fa137eedc0e65d087fe8039eef2093cd0ccfca4c700a6f161925"
generated: true
---
# hit_merge_clusters

## Overview

Export cluster membership rows using the authoritative hit_merged configuration.
Internal flat cluster membership for hit merge outputs.

| Item | Value |
| --- | --- |
| Provides | `hit_merge_clusters` |
| Plugin Class | `HitMergeClustersPlugin` |
| Module | `waveform_analysis.core.plugins.builtin.hit_merge_clusters.plugin` |
| Version | `1.1.0` |
| Category | 特征提取 |
| Output Container | `structured_array` |
| Execution Mode | `static` |
| Save Policy | `always` |
| Uses Run Config | no |
| Timeout | `none` |
| Side Effect | no |
| Narrative Source | `source` |
| Source Fingerprint | `d1fae75c79a4fa137eedc0e65d087fe8039eef2093cd0ccfca4c700a6f161925` |

### Dependencies

默认文档画像：`declared`。

| Dependency | Version Constraint | Resolution | Required Fields | Description |
| --- | --- | --- | --- | --- |
| `hit_merged` | - | declared | - | Merge nearby threshold hits per channel with time-gap and max-width constraints. |
| `hit_threshold` | - | declared | - | Threshold-only hit detector with THRESHOLD_HIT_DTYPE output. |
### How It Works

1. Internal flat cluster membership for hit merge outputs.

## Configuration

| Name | Type | Default | Unit | Tracked | Deprecated | Description |
| --- | --- | --- | --- | --- | --- | --- |
| - | - | - | - | - | - | 此插件没有插件级配置。 |
## Output

structured_array output with fields: cluster_index, hit_index.

| Field | DType | Unit | Meaning |
| --- | --- | --- | --- |
| `cluster_index` | `int64` | None | Index of the merged cluster, matching merged_id |
| `hit_index` | `int64` | None | Row index in the source hit_threshold array |
## Usage

### Minimal Example

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins import profiles

ctx = Context(config={"data_root": "DAQ", "daq_adapter": "vx2730"})
ctx.register(*profiles.cpu_default())
result = ctx.get_data("run_001", "hit_merge_clusters")
```

示例使用 `run_id="run_001"` 和文档默认运行画像；真实数据路径与配置应以当前实验设置为准。

## Operational Notes

### Behavior

- HitMergeClustersPlugin 类实现 - 导出 hit merge 的 cluster 成员关系。
### Failure Modes

- 任一声明依赖（`hit_merged`, `hit_threshold`）缺失或字段不符合输入契约时，执行会失败。
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
waveform-docs generate plugins-agent --plugin hit_merge_clusters
waveform-docs check coverage --strict --fail-on-warning
```
