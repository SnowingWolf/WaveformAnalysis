# hit_grouped (HitGroupedPlugin)

> Agent-first 插件契约文档。面向自动化执行与改动评估。

## Agent Contract

| Item | Value |
|------|-------|
| Provides | `hit_grouped` |
| Depends On | `hit_merged`, `hit_merged_components`, `hit_threshold` |
| Output Kind | `unknown` |
| Version | `0.5.0` |
| Module | `waveform_analysis.core.plugins.builtin.cpu.event_analysis` |
| Accelerator | `cpu` |

## Inputs

- `hit_merged`
- `hit_merged_components`
- `hit_threshold`

## Outputs

- 无结构化字段信息（`unknown`）

## Config

| Name | Type | Default | Note |
|------|------|---------|------|
| `time_window_ns` | `float` | `100.0` | - |
| `dt` | `int` | `None` | 采样间隔（ns）。仅在输入 hit_merged 缺少 dt 字段时作为兼容补充。 |

## Execution Path

`hit_grouped` 依赖链入口：
`hit_merged -> hit_merged_components -> hit_threshold -> hit_grouped`

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
waveform-docs generate plugins-agent --plugin hit_grouped

# 覆盖率检查
waveform-docs check coverage --strict
```
