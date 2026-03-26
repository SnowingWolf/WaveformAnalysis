# hit_merged (HitMergePlugin)

> Agent-first 插件契约文档。面向自动化执行与改动评估。

## Agent Contract

| Item | Value |
|------|-------|
| Provides | `hit_merged` |
| Depends On | `hit_threshold` |
| Output Kind | `structured_array` |
| Version | `0.4.0` |
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
| `edge_start` | `float32` |
| `edge_end` | `float32` |
| `width` | `float32` |
| `timestamp` | `int64` |
| `board` | `int16` |
| `channel` | `int16` |
| `record_id` | `int64` |

## Config

| Name | Type | Default | Note |
|------|------|---------|------|
| `merge_gap_ns` | `float` | `0.0` | 最大边界间距（ns），<=0 表示不合并 |
| `max_total_width_ns` | `float` | `10000.0` | 链式合并后的最大总宽度（ns） |
| `sampling_interval_ns` | `float` | `2.0` | 采样间隔（ns），用于样点边界与时间换算 |

## Execution Path

`hit_merged` 依赖链入口：
`hit_threshold -> hit_merged`

## Failure Modes

- 依赖数据缺失或字段不匹配，导致 compute 阶段报错
- 配置值类型/范围不合法，触发参数校验异常
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
