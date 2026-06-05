# hit_merged_components (HitMergedComponentsPlugin)

> Agent-first 插件契约文档。面向自动化执行与改动评估。

## Agent Contract

| Item | Value |
|------|-------|
| Provides | `hit_merged_components` |
| Depends On | `hit_merged`, `hit_threshold` |
| Output Kind | `structured_array` |
| Version | `1.1.0` |
| Module | `waveform_analysis.core.plugins.builtin.cpu.hit_merge` |
| Accelerator | `cpu` |

## Inputs

- `hit_merged`
- `hit_threshold`

## Outputs

| Field | DType |
|-------|-------|
| `merged_index` | `int64` |
| `hit_index` | `int64` |

## Config

| Name | Type | Default | Note |
|------|------|---------|------|
| `validate_components` | `bool` | `False` | 校验 hit_merged 的 component_offset/component_count 与 cluster rows 是否一致。 |

## Execution Path

`hit_merged_components` 依赖链入口：
`hit_merged -> hit_threshold -> hit_merged_components`

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
waveform-docs generate plugins-agent --plugin hit_merged_components

# 覆盖率检查
waveform-docs check coverage --strict
```
