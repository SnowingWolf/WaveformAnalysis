# hit_merged_features (HitMergedFeaturesPlugin)

> Agent-first 插件契约文档。面向自动化执行与改动评估。

## Agent Contract

| Item | Value |
|------|-------|
| Provides | `hit_merged_features` |
| Depends On | `hit_merged`, `hit_merged_components`, `hit_threshold`, `records`, `wave_pool` |
| Output Kind | `structured_array` |
| Version | `0.2.0` |
| Module | `waveform_analysis.core.plugins.builtin.cpu.hit_merged_features` |
| Accelerator | `cpu` |

## Inputs

- `hit_merged`
- `hit_merged_components`
- `hit_threshold`
- `records`
- `wave_pool`

## Outputs

| Field | DType | Meaning |
|-------|-------|---------|
| `merged_index` | `int64` | - |
| `board` | `int16` | - |
| `channel` | `int16` | - |
| `record_id` | `int64` | - |
| `time_start` | `int64` | - |
| `time_end` | `int64` | - |
| `center_time` | `int64` | - |
| `max_time` | `int64` | - |
| `area` | `float32` | - |
| `height` | `float32` | - |
| `width` | `float32` | - |
| `rise_time` | `float32` | - |
| `fall_time` | `float32` | - |
| `n_hits` | `int32` | - |
| `valid` | `int8` | - |

## Config

| Name | Type | Default | Note |
|------|------|---------|------|
| `wave_source` | `str` | `records` | 波形来源。hit_merged_features 当前正式支持 records。 |
| `use_filtered` | `bool` | `False` | 是否使用 wave_pool_filtered 计算局部特征。 |
| `dt` | `int` | `None` | 保留兼容配置；特征优先使用 records/hits 的 dt |

## Execution Path

`hit_merged_features` 依赖链入口：
`hit_merged -> hit_merged_components -> hit_threshold -> records -> wave_pool -> hit_merged_features`

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
waveform-docs generate plugins-agent --plugin hit_merged_features

# 覆盖率检查
waveform-docs check coverage --strict
```
