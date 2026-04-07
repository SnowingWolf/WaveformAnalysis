# hit_merged_components (HitMergedComponentsPlugin)

> Agent-first 插件契约文档。面向自动化执行与改动评估。

## Agent Contract

| Item | Value |
|------|-------|
| Provides | `hit_merged_components` |
| Depends On | `hit_merge_clusters`, `hit_merged` |
| Output Kind | `structured_array` |
| Version | `0.1.0` |
| Module | `waveform_analysis.core.plugins.builtin.cpu.hit_merge` |
| Accelerator | `cpu` |

## Inputs

- `hit_merge_clusters`
- `hit_merged`

## Outputs

| Field | DType |
|-------|-------|
| `merged_index` | `int64` |
| `hit_index` | `int64` |

说明：
按 `component_offset/component_count` 的顺序平铺每个 `hit_merged` 的组件 hit 索引。消费方可用 `hit_index` 回查 `hit_threshold`，再用 `record_id + edge_start/edge_end` 取真实波形窗口。内部会复用共享的 cluster membership，避免为 `hit_merged_components` 重跑一次 hit merge 聚类。

## Config

- 无独立配置；复用 `hit_merged` 的合并配置语义。

## Validation

```bash
waveform-docs generate plugins-agent --plugin hit_merged_components
waveform-docs check coverage --strict
```
