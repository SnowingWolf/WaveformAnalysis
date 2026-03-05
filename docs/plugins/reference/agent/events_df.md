# events_df (EventFramePlugin)

> Agent-first 插件契约文档。面向自动化执行与改动评估。

## Agent Contract

| Item | Value |
|------|-------|
| Provides | `events_df` |
| Depends On | `events` |
| Output Kind | `unknown` |
| Version | `0.3.0` |
| Module | `waveform_analysis.core.plugins.builtin.cpu.events` |
| Accelerator | `cpu` |

## Inputs

- `events`

## Outputs

- 无结构化字段信息（`unknown`）

## Config

| Name | Type | Default | Note |
|------|------|---------|------|
| `peaks_range` | `tuple` | `(40, 90)` | Peak range in samples (start, end); end=None uses full length. |
| `charge_range` | `tuple` | `(0, None)` | Charge range in samples (start, end); end=None uses full length. |
| `include_event_id` | `bool` | `True` | Include event_id column in events_df output. |
| `fixed_baseline` | `dict` | `None` | 按通道固定 baseline 值，如 {0: 8192, 1: 8200}。设置后覆盖动态 baseline 用于 height/area 计算。 |

## Execution Path

`events_df` 依赖链入口：
`events -> events_df`

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
waveform-docs generate plugins-agent --plugin events_df

# 覆盖率检查
waveform-docs check coverage --strict
```
