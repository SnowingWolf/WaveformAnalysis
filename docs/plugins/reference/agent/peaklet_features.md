# peaklet_features (PeakletFeaturesPlugin)

> Agent-first 插件契约文档。面向自动化执行与改动评估。

## Agent Contract

| Item | Value |
|------|-------|
| Provides | `peaklet_features` |
| Depends On | `peaklet_waveforms`, `peaklet_waveform_pool`, `peaklets` |
| Output Kind | `structured_array` |
| Version | `1.0.0` |
| Module | `waveform_analysis.core.plugins.builtin.cpu.peaklets` |
| Accelerator | `cpu` |

## Inputs

- `peaklet_waveforms`
- `peaklet_waveform_pool`
- `peaklets`

## Outputs

| Field | DType | Meaning |
|-------|-------|---------|
| `peaklet_index` | `int64` | - |
| `max_time` | `int64` | - |
| `area` | `float32` | - |
| `height` | `float32` | - |
| `width` | `float32` | - |
| `rise_time` | `float32` | - |
| `fall_time` | `float32` | - |

## Config

- 无可配置项

## Execution Path

`peaklet_features` 依赖链入口：
`peaklet_waveforms -> peaklet_waveform_pool -> peaklets -> peaklet_features`

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
waveform-docs generate plugins-agent --plugin peaklet_features

# 覆盖率检查
waveform-docs check coverage --strict
```
