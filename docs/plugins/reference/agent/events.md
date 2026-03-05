# events (EventsPlugin)

> Agent-first 插件契约文档。面向自动化执行与改动评估。

## Agent Contract

| Item | Value |
|------|-------|
| Provides | `events` |
| Depends On | - |
| Output Kind | `structured_array` |
| Version | `2.0.0` |
| Module | `waveform_analysis.core.plugins.builtin.cpu.events` |
| Accelerator | `cpu` |

## Inputs

- 无依赖输入（source plugin）

## Outputs

| Field | DType |
|-------|-------|
| `timestamp` | `int64` |
| `pid` | `int32` |
| `channel` | `int16` |
| `baseline` | `float64` |
| `baseline_upstream` | `float64` |
| `event_id` | `int64` |
| `dt` | `int32` |
| `trigger_type` | `int16` |
| `flags` | `uint32` |
| `wave_offset` | `int64` |
| `event_length` | `int32` |
| `time` | `int64` |

## Config

| Name | Type | Default | Note |
|------|------|---------|------|
| `events_part_size` | `int` | `200000` | Max events per shard in the records bundle; <=0 disables sharding. |
| `events_dt_ns` | `int` | `None` | Sample interval in ns (defaults to adapter rate or 1ns). |
| `use_filtered` | `bool` | `False` | 是否使用 filtered_waveforms（需要先注册 FilteredWaveformsPlugin） |

## Execution Path

`events` 依赖链入口：
`SOURCE -> events`

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
waveform-docs generate plugins-agent --plugin events

# 覆盖率检查
waveform-docs check coverage --strict
```
