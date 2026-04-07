# hit_merged (HitMergePlugin)

> Agent-first 插件契约文档。面向自动化执行与改动评估。

## Agent Contract

| Item | Value |
|------|-------|
| Provides | `hit_merged` |
| Depends On | `hit_threshold` |
| Output Kind | `structured_array` |
| Version | `0.8.0` |
| Module | `waveform_analysis.core.plugins.builtin.cpu.hit_merge` |
| Accelerator | `cpu` |

## Inputs

- `hit_threshold`

## Outputs

| Field | DType |
|-------|-------|
| `position` | `int64` |
| `height` | `float32` |
| `integral` | `float32` |
| `sample_start` | `int32` |
| `sample_end` | `int32` |
| `width` | `float32` |
| `dt` | `int32` |
| `rise_time` | `float32` |
| `fall_time` | `float32` |
| `timestamp` | `int64` |
| `board` | `int16` |
| `channel` | `int16` |
| `record_id` | `int64` |
| `component_offset` | `int64` |
| `component_count` | `int32` |

说明：
单 `record_id` 合并时，`sample_start` / `sample_end` 为安全半开样本窗口 `[start, end)`。
跨 `record_id` 合并时，`sample_start = sample_end = -1`、`width = -1`，消费方需要通过
`hit_merged_components` 回查到组件 `hit_threshold` 行，再恢复真实波形窗口。

## Config

| Name | Type | Default | Note |
|------|------|---------|------|
| `merge_gap_ns` | `float` | `0.0` | 最大边界间距（ns），<=0 表示不合并 |
| `max_total_width_ns` | `float` | `10000.0` | 链式合并后的最大总宽度（ns） |
| `dt` | `int` | `None` | 采样间隔（ns）。仅在输入 hit_threshold 缺少 dt 字段时作为兼容补充。 |

## Execution Path

`hit_merged` 依赖链入口：
`hit_threshold -> hit_merged`

## Failure Modes

- 依赖数据缺失或字段不匹配，导致 compute 阶段报错
- 跨记录合并被误当作单记录连续窗口消费，导致波形演示逻辑错误
- 输出 dtype 变更但版本未升级，可能导致缓存命中异常

## Change Playbook

1. 修改 `options`/`output_dtype`/核心算法后同步提升 `version`
2. 保持 `provides` 稳定；若必须变更，更新依赖插件与文档索引
3. 新增/删除输出字段时，同时更新消费方插件和回归测试

## Validation

```bash
# 单插件文档再生成
waveform-docs generate plugins-agent --plugin hit_merged

# 覆盖率检查
waveform-docs check coverage --strict
```
