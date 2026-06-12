# peaks (PeaksPlugin)

> Agent-first 插件契约文档。面向自动化执行与改动评估。

## Agent Contract

| Item | Value |
|------|-------|
| Provides | `peaks` |
| Depends On | `peaklets`, `peaklet_features`, `peaklet_channels` |
| Output Kind | `structured_array` |
| Version | `4.0.0` |
| Module | `waveform_analysis.core.plugins.builtin.cpu.peaklets` |
| Accelerator | `cpu` |

## Inputs

- `peaklets`
- `peaklet_features`
- `peaklet_channels`

## Outputs

| Field | DType | Meaning |
|-------|-------|---------|
| `peak_id` | `int64` | - |
| `time_start` | `int64` | - |
| `time_end` | `int64` | - |
| `time_peak` | `int64` | - |
| `center_time` | `int64` | - |
| `rise_time` | `float32` | - |
| `fall_time` | `float32` | - |
| `width_25_75` | `float32` | - |
| `rise_time_10_50` | `float32` | - |
| `range_90p_area` | `float32` | - |
| `area` | `float32` | - |
| `height` | `float32` | - |
| `width` | `float32` | - |
| `n_hits` | `int32` | - |
| `n_channels` | `int32` | - |

## Config

- 无可配置项

## Execution Path

`peaks` 依赖链入口：
`peaklets -> peaklet_features -> peaklet_channels -> peaks`

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
waveform-docs generate plugins-agent --plugin peaks

# 覆盖率检查
waveform-docs check coverage --strict
```
