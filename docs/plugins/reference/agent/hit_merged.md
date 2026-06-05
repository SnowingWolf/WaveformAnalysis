# hit_merged (HitMergePlugin)

> Agent-first 插件契约文档。面向自动化执行与改动评估。

## Agent Contract

| Item | Value |
|------|-------|
| Provides | `hit_merged` |
| Depends On | `hit_threshold` |
| Output Kind | `structured_array` |
| Version | `1.2.0` |
| Module | `waveform_analysis.core.plugins.builtin.cpu.hit_merge` |
| Accelerator | `cpu` |

## Inputs

- `hit_threshold`

## Outputs

| Field | DType | Meaning |
|-------|-------|---------|
| `position` | `int64` | Anchor hit position; for multi-hit clusters this is the hit closest to the merged window midpoint. |
| `sample_start` | `int32` | Merged sample window start when all components belong to one record; `-1` when the direct sample window cannot be represented. |
| `sample_end` | `int32` | Merged sample window end when all components belong to one record; `-1` when the direct sample window cannot be represented. |
| `width` | `float32` | Merged sample-window width; `-1.0` when the cluster spans records or otherwise cannot resolve a direct sample window. |
| `dt` | `int32` | Resolved sampling interval from the anchor hit or compatible `dt` configuration fallback. |
| `timestamp` | `int64` | Anchor hit timestamp; for multi-hit clusters this follows the same anchor rule as `position`. |
| `board` | `int16` | Hardware board from the anchor hit; boardless inputs use compatibility value `0`. |
| `channel` | `int16` | Hardware channel from the anchor hit; merging never crosses channel boundaries. |
| `record_id` | `int64` | Anchor hit record id, not necessarily a shared record id for every component. |
| `component_offset` | `int64` | Start row in `hit_merge_clusters` for this cluster's contiguous membership rows. |
| `component_count` | `int32` | Number of contiguous `hit_merge_clusters` membership rows for this cluster. |

## Config

| Name | Type | Default | Note |
|------|------|---------|------|
| `merge_gap_ns` | `float` | `0.0` | Maximum boundary gap in ns; values `<= 0` disable merging. |
| `max_total_width_ns` | `float` | `10000.0` | Maximum total absolute cluster width in ns for chained merges. |
| `dt` | `int` | `None` | Compatibility fallback sampling interval in ns, used only when `hit_threshold` lacks a `dt` field. |

## Behavior Notes

- Only hits with the same `(board, channel)` are eligible for merging; boardless inputs use board `0` as the compatibility value.
- `merge_gap_ns <= 0` disables merging and maps each `hit_threshold` row to one `hit_merged` row.
- The merge decision uses absolute hit windows derived from `timestamp`, sample window fields, `dt`, and the configured pre-trigger offset.
- Hits with different resolved `dt` values are not merged into the same cluster.
- `max_total_width_ns` limits the total absolute width of chained merges, so a locally adjacent hit can still start a new cluster when the accumulated window would exceed the limit.

## Cluster Contract

- `hit_merged` computes canonical cluster membership from its own config; `hit_merge_clusters` exports the same membership rows for diagnostics and inspection.
- Rows consumed by one `hit_merged` row must be contiguous in the canonical membership order.
- `cluster_index` values must be sorted, contiguous, and gap-free from `0` to `len(hit_merged) - 1`.
- `component_offset` and `component_count` point back into the exact membership slice used by `hit_merged_components`.

## Downstream Impact

Consumers:
- `hit_merged_components`
- `hit_merged_features`
- `hit_grouped`
- `peaklets`
- `peaklet_components`

- Field semantics and row ordering changes propagate to component expansion, waveform feature extraction, cross-channel grouping, and peaklet membership.
- Changing `component_offset`/`component_count` requires matching updates to `hit_merge_clusters` ordering and all component consumer tests.
- Changing anchor-field semantics affects downstream `position`, `timestamp`, `record_id`, and channel aggregation behavior.

## Execution Path

`hit_merged` 依赖链入口：
`hit_threshold -> hit_merged`

## Failure Modes

- `hit_threshold` is missing required `channel` data, so same-channel grouping cannot be resolved.
- `hit_threshold` lacks `dt` and no compatible `dt` config fallback is available.
- Canonical cluster rows are not ordered by contiguous, gap-free `cluster_index` values.
- Cluster rows reference hit indices that are outside the materialized `hit_threshold` array.

## Change Playbook

1. Changing merge behavior, output field semantics, or dtype requires a `version` bump because cache lineage depends on the plugin contract.
2. Keep `hit_merged` and `hit_merged_components` in sync; membership ordering is part of the downstream contract.
3. After contract changes, regenerate agent docs and run targeted tests for `hit_merge`, `hit_merged_components`, `hit_merged_features`, `hit_grouped`, and `peaklets` consumers as appropriate.

## Validation

```bash
# 单插件文档再生成
waveform-docs generate plugins-agent --plugin hit_merged

# 覆盖率检查
waveform-docs check coverage --strict
```
