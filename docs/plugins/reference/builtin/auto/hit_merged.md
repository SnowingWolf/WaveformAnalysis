---
schema_version: 1
document_type: "plugin_reference"
profile: "auto"
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
| `hit_threshold` | - | declared | - | - |
## Configuration

| Name | Type | Default | Unit | Tracked | Deprecated | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `merge_gap_ns` | `float` | `0.0` | - | yes | no | 最大边界间距（ns），<=0 表示不合并 |
| `max_total_width_ns` | `float` | `10000.0` | - | yes | no | 链式合并后的最大总宽度（ns） |
| `dt` | `int` | `None` | - | yes | no | 采样间隔（ns）。仅在输入 hit_threshold 缺少 dt 字段时作为兼容补充。 |
## Output

| Field | DType | Unit | Meaning |
| --- | --- | --- | --- |
| `merged_id` | `int64` | - | Unique identifier for this hit_merged record, equal to its row index (0-based) in the output array. Used for tracking and referencing specific merged hits. |
| `position` | `int64` | - | Anchor hit position; for multi-hit clusters this is the hit closest to the merged window midpoint. |
| `time_start` | `int64` | - | Absolute start time (ps) of the merged window; always valid regardless of whether components span records. |
| `time_end` | `int64` | - | Absolute end time (ps) of the merged window; always valid regardless of whether components span records. |
| `sample_start` | `int32` | - | Merged sample window start when all components belong to one record; `-1` when the cluster spans records. |
| `sample_end` | `int32` | - | Merged sample window end when all components belong to one record; `-1` when the cluster spans records. |
| `width` | `float32` | - | Merged sample-window width; `-1.0` when the cluster spans records or otherwise cannot resolve a direct sample window. |
| `dt` | `int32` | - | Resolved sampling interval from the anchor hit or compatible `dt` configuration fallback. |
| `timestamp` | `int64` | - | Anchor hit timestamp; for multi-hit clusters this follows the same anchor rule as `position`. |
| `board` | `int16` | - | Hardware board from the anchor hit; boardless inputs use compatibility value `0`. |
| `channel` | `int16` | - | Hardware channel from the anchor hit; merging never crosses channel boundaries. |
| `record_id` | `int64` | - | Anchor hit record id, not necessarily a shared record id for every component. |
| `component_offset` | `int64` | - | Start row in `hit_merge_clusters` for this cluster's contiguous membership rows. |
| `component_count` | `int32` | - | Number of contiguous `hit_merge_clusters` membership rows for this cluster. |
| `is_single_record` | `bool` | - | True when all component hits belong to the same record (fast path available); False when spanning records. |
## Usage

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import HitMergePlugin

ctx = Context(config={"data_root": "DAQ"})
ctx.register(HitMergePlugin())
data = ctx.get_data("run_001", "hit_merged")
```
