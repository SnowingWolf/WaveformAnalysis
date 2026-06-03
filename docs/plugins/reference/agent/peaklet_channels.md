# peaklet_channels (PeakletChannelsPlugin)

> Agent-first 插件契约文档。面向自动化执行与改动评估。

## Agent Contract

| Item | Value |
|------|-------|
| Provides | `peaklet_channels` |
| Depends On | `peaklets`, `peaklet_components`, `hit_merged_features` |
| Output Kind | `structured_array` |
| Version | `0.1.0` |
| Module | `waveform_analysis.core.plugins.builtin.cpu.peaklet_channels` |
| Accelerator | `cpu` |

## Inputs

- `peaklets`
- `peaklet_components`
- `hit_merged_features`

## Outputs

| Field | DType |
|-------|-------|
| `peaklet_index` | `int64` |
| `board` | `int16` |
| `channel` | `int16` |
| `area` | `float32` |
| `height` | `float32` |
| `n_hits` | `int32` |
| `area_fraction` | `float32` |

## Config

- 无可配置项

## Execution Path

`peaklet_channels` 依赖链入口：
`peaklets -> peaklet_components -> hit_merged_features -> peaklet_channels`

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
waveform-docs generate plugins-agent --plugin peaklet_channels

# 覆盖率检查
waveform-docs check coverage --strict
```
