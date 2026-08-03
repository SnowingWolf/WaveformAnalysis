---
schema_version: 1
document_type: "plugin_reference"
profile: "agent"
provides: "hit_merged"
plugin_class: "HitMergePlugin"
module: "waveform_analysis.core.plugins.builtin.hit.hit_merge"
version: "2.1.0"
summary: "Merge nearby threshold hits per channel with time-gap and max-width constraints."
depends_on: ["hit_threshold"]
output_kind: "structured_array"
generated: true
---
# hit_merged

## Overview

Merge nearby threshold hits per channel with time-gap and max-width constraints.
HitMergePlugin 是波形分析中最核心的后处理插件之一，负责将 hit_threshold 产出的过阈 hit 按时间邻近性合并为统一的 hit_merged 记录。它不直接修改原始 hit_threshold 数据，而是生成新的结构化输出，同时提供 cluster 级别的成员关系（hit_merge_clusters）供下游诊断使用。

该插件由三部分协同工作：HitMergePlugin（主合并逻辑）、HitMergeClustersPlugin（导出 cluster 成员关系）和 HitMergedComponentsPlugin（验证与展开 component）。合并策略的核心是"同板同通道、同 dt、邻近链式合并"——即只有相同 (board, channel) 且采样间隔相同的 hit 才能归入同一 cluster，并通过时间 gap 和总宽度限制控制 cluster 的生长。

合并窗口的中点 anchor 策略确保上下游一致：多 hit cluster 选取最接近合并时间窗口中心的 hit 作为 anchor，写入 position、timestamp、channel、record_id 等关键字段。跨 record 时，sample_start/sample_end/width 标记为 -1，time_start/time_end 始终有效。

该插件不依赖外部级联状态，所有合并判断完全由配置 merge_gap_ns、max_total_width_ns 和 dt 推导的绝对时间窗口决定。

| Item | Value |
| --- | --- |
| Provides | `hit_merged` |
| Plugin Class | `HitMergePlugin` |
| Module | `waveform_analysis.core.plugins.builtin.hit.hit_merge` |
| Version | `2.1.0` |
| Category | 特征提取 |
| Accelerator | CPU (NumPy/SciPy) |
| Output Kind | `structured_array` |

| Dependency | Version Constraint | Resolution | Required Fields | Description |
| --- | --- | --- | --- | --- |
| `hit_threshold` | - | declared | - | Threshold-only hit detector with THRESHOLD_HIT_DTYPE output. |
### How It Works

1. **识别可合并片段**：`hit_threshold` 每行为过阈片段，判断哪些相邻片段应合并为同一次通道响应。
2. **保持通道/刻度一致**：仅合并同一 `(board, channel)`、相同 `dt` 的片段，避免混入不同时间刻度。
3. **按时间连接**：空档 ≤ `merge_gap_ns` 才接入同窗口；`merge_gap_ns` ≤ 0 时关闭合并。
4. **限制链式总时长**：合并窗口超过 `max_total_width_ns` 时，后续片段另起新的 `hit_merged`。
5. **选择代表 hit**：取最接近窗口中心的原始 hit，继承其 position、timestamp、channel、record_id。
6. **记录窗口与成员**：输出时间范围与成员索引；跨 record 时 `sample_start`、`sample_end`、`width` 为 -1。

## Configuration

| Name | Type | Default | Unit | Tracked | Deprecated | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `merge_gap_ns` | `float` | `0.0` | - | yes | no | Maximum boundary gap in ns; values `<= 0` disable merging. |
| `max_total_width_ns` | `float` | `10000.0` | - | yes | no | Maximum total absolute cluster width in ns for chained merges. |
| `dt` | `int` | `None` | - | yes | no | Compatibility fallback sampling interval in ns, used only when `hit_threshold` lacks a `dt` field. |
## Output

structured_array output with fields: merged_id, position, time_start, time_end, sample_start, sample_end, width, dt, ....

| Field | DType | Unit | Meaning |
| --- | --- | --- | --- |
| `merged_id` | `int64` | None | Unique identifier for the merged hit record, equal to row index |
| `position` | `int64` | samples | Anchor hit position; for multi-hit clusters, nearest to window midpoint |
| `time_start` | `int64` | ps | Absolute start time in picoseconds of the merged window |
| `time_end` | `int64` | ps | Absolute end time in picoseconds of the merged window |
| `sample_start` | `int32` | samples | Merged sample-window start; -1 when spanning multiple records |
| `sample_end` | `int32` | samples | Merged sample-window end; -1 when spanning multiple records |
| `width` | `float32` | samples | Merged sample-window width; -1.0 when spanning records |
| `dt` | `int32` | ns | Resolved sample interval in nanoseconds |
| `timestamp` | `int64` | ps | Anchor hit timestamp in picoseconds |
| `board` | `int16` | None | Hardware board from the anchor hit |
| `channel` | `int16` | None | Hardware channel from the anchor hit |
| `record_id` | `int64` | None | Anchor hit record identifier |
| `component_offset` | `int64` | None | Start row in hit_merge_clusters for this cluster |
| `component_count` | `int32` | None | Number of component rows in hit_merge_clusters for this cluster |
| `is_single_record` | `bool` | None | True when all component hits belong to the same record |
## Usage

### Minimal Example

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import HitMergePlugin

ctx = Context(config={"data_root": "DAQ"})
ctx.register(HitMergePlugin())
data = ctx.get_data("run_001", "hit_merged")
```

## Operational Notes

### Behavior

- Only hits with the same `(board, channel)` are eligible for merging; boardless inputs use board `0` as the compatibility value.
- `merge_gap_ns <= 0` disables merging and maps each `hit_threshold` row to one `hit_merged` row.
- The merge decision uses absolute hit windows derived from `timestamp`, sample window fields, `dt`, and the configured pre-trigger offset.
- Hits with different resolved `dt` values are not merged into the same cluster.
- `max_total_width_ns` limits the total absolute width of chained merges, so a locally adjacent hit can still start a new cluster when the accumulated window would exceed the limit.
### Failure Modes

- `hit_threshold` is missing required `channel` data, so same-channel grouping cannot be resolved.
- `hit_threshold` lacks `dt` and no compatible `dt` config fallback is available.
- Canonical cluster rows are not ordered by contiguous, gap-free `cluster_index` values.
- Cluster rows reference hit indices that are outside the materialized `hit_threshold` array.
### Downstream Impact

Consumers: `hit_grouped`, `hit_merge_clusters`, `hit_merged_components`, `hit_merged_features`, `peaklet_components`, `peaklets`
- Field semantics and row ordering changes propagate to component expansion, waveform feature extraction, cross-channel grouping, and peaklet membership.
- Changing `component_offset`/`component_count` requires matching updates to `hit_merge_clusters` ordering and all component consumer tests.
- Changing anchor-field semantics affects downstream `position`, `timestamp`, `record_id`, and channel aggregation behavior.

## Maintenance

### Change Playbook

1. v2.1.0: Added `merged_id` field as unique identifier equal to row index. This is a backward-compatible addition; downstream plugins auto-adapt via dtype.names checks.
2. v2.0.0: Added `time_start`, `time_end`, `is_single_record` fields to support cross-record merging.
3. Changing merge behavior, output field semantics, or dtype requires a `version` bump because cache lineage depends on the plugin contract.
4. Keep `hit_merged` and `hit_merged_components` in sync; membership ordering is part of the downstream contract.
5. After contract changes, regenerate agent docs and run targeted tests for `hit_merge`, `hit_merged_components`, `hit_merged_features`, `hit_grouped`, and `peaklets` consumers as appropriate.
### Validation

```bash
waveform-docs generate plugins-agent --plugin hit_merged
waveform-docs check coverage --strict --fail-on-warning
```
