---
schema_version: 2
document_type: "plugin_reference"
profile: "auto"
provides: "hit_merged"
plugin_class: "HitMergePlugin"
module: "waveform_analysis.core.plugins.builtin.hit_merged.plugin"
version: "2.1.0"
summary: "Merge nearby threshold hits per channel with time-gap and max-width constraints."
depends_on: ["hit_threshold"]
declared_depends_on: ["hit_threshold"]
resolved_depends_on: ["hit_threshold"]
dependency_profile: "declared"
dependency_profile_values: {}
dependency_config_keys: []
output_kind: "structured_array"
execution_kind: "static"
narrative_source: "published"
narrative_source_reason: null
source_fingerprint: "22ed871847fb6de92e3657287d9e7436adbe23d4f1cc5fa3010cabc54dc41678"
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
| Module | `waveform_analysis.core.plugins.builtin.hit_merged.plugin` |
| Version | `2.1.0` |
| Category | 特征提取 |
| Output Container | `structured_array` |
| Execution Mode | `static` |
| Save Policy | `always` |
| Uses Run Config | no |
| Timeout | `none` |
| Side Effect | no |
| Narrative Source | `published` |
| Source Fingerprint | `22ed871847fb6de92e3657287d9e7436adbe23d4f1cc5fa3010cabc54dc41678` |

### Dependencies

默认文档画像：`declared`。

| Dependency | Version Constraint | Resolution | Required Fields | Description |
| --- | --- | --- | --- | --- |
| `hit_threshold` | - | declared | - | Threshold-only hit detector with THRESHOLD_HIT_DTYPE output. |
### How It Works

1. 识别可合并的片段：`hit_threshold` 中的每一行都是一个过阈信号片段；插件判断哪些相邻片段应视为同一次通道响应。
2. 保持通道与采样刻度一致：只合并同一 `(board, channel)` 的片段；采样间隔不同的片段始终分开，避免把不同时间刻度的信号混在一起。
3. 按时间连接相邻片段：两个片段之间的空档不超过 `merge_gap_ns` 时，可以接入同一个合并窗口。将 `merge_gap_ns` 设为 `<= 0` 会关闭合并。
4. 限制链式合并的总时长：即使每一对相邻片段都很接近，只要合并后的完整窗口超过 `max_total_width_ns`，后续片段仍会从新的 `hit_merged` 开始。
5. 选择代表 hit：一个合并窗口包含多个片段时，选取最接近窗口时间中心的原始 hit，继承它的 position、timestamp、channel 和 record_id。
6. 记录窗口与成员关系：输出保存合并后的时间范围及成员索引；若成员跨越多个 record，则没有唯一的 sample 窗口，`sample_start`、`sample_end` 和 `width` 会标记为无效值。

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
from waveform_analysis.core.plugins import profiles

ctx = Context(config={"data_root": "DAQ", "daq_adapter": "vx2730"})
ctx.register(*profiles.cpu_default())
result = ctx.get_data("run_001", "hit_merged")
```

示例使用 `run_id="run_001"` 和文档默认运行画像；真实数据路径与配置应以当前实验设置为准。

### Downstream Consumers

- `hit_grouped`
- `hit_merge_clusters`
- `hit_merged_components`
- `hit_merged_features`
- `peaklet_channels`
- `peaklet_components`
- `peaklet_waveforms`
- `peaklets`
