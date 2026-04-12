# hit_merge_clusters (HitMergeClustersPlugin)

> Agent-first 插件契约文档。面向自动化执行与改动评估。

## Agent Contract

| Item | Value |
|------|-------|
| Provides | `hit_merge_clusters` |
| Depends On | `hit_threshold` |
| Output Kind | `structured_array` |
| Version | `0.1.0` |
| Module | `waveform_analysis.core.plugins.builtin.cpu.hit_merge` |
| Accelerator | `cpu` |

## Inputs

- `hit_threshold`

## Outputs

| Field | DType |
|-------|-------|
| `cluster_index` | `int64` |
| `hit_index` | `int64` |

## Config

| Name | Type | Default | Note |
|------|------|---------|------|
| `merge_gap_ns` | `float` | `0.0` | 最大边界间距（ns），<=0 表示不合并 |
| `max_total_width_ns` | `float` | `10000.0` | 链式合并后的最大总宽度（ns） |
| `dt` | `int` | `None` | 采样间隔（ns）。仅在输入 hit_threshold 缺少 dt 字段时作为兼容补充。 |

## Execution Path

`hit_merge_clusters` 依赖链入口：
`hit_threshold -> hit_merge_clusters`

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
waveform-docs generate plugins-agent --plugin hit_merge_clusters

# 覆盖率检查
waveform-docs check coverage --strict
```
