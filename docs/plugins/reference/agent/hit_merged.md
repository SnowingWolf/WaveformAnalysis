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
| `merge_gap_ns` | `float` | `0.0` | - | yes | no | Maximum boundary gap in ns; values `<= 0` disable merging. |
| `max_total_width_ns` | `float` | `10000.0` | - | yes | no | Maximum total absolute cluster width in ns for chained merges. |
| `dt` | `int` | `None` | - | yes | no | Compatibility fallback sampling interval in ns, used only when `hit_threshold` lacks a `dt` field. |
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

Consumers: `hit_merged_components`, `hit_merged_features`, `hit_grouped`, `peaklets`, `peaklet_components`- Field semantics and row ordering changes propagate to component expansion, waveform feature extraction, cross-channel grouping, and peaklet membership.
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
