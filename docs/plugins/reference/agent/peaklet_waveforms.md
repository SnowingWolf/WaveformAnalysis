# peaklet_waveforms (PeakletWaveformPlugin)

> Agent-first 插件契约文档。面向自动化执行与改动评估。

## Agent Contract

| Item | Value |
|------|-------|
| Provides | `peaklet_waveforms` |
| Depends On | - |
| Output Kind | `structured_array` |
| Version | `1.3.1` |
| Module | `waveform_analysis.core.plugins.builtin.peaks.peaklets` |
| Accelerator | `cpu` |

## Source Notes

Peaklet clustering, ragged waveforms, features, and final peaks.

## Inputs

- 无依赖输入（source plugin）

## Outputs

| Field | DType | Meaning |
|-------|-------|---------|
| `peak_id` | `int64` | - |
| `time_start` | `int64` | - |
| `time_end` | `int64` | - |
| `dt` | `int32` | - |
| `wave_offset` | `int64` | - |
| `wave_length` | `int32` | - |

## Config

| Name | Type | Default | Note |
|------|------|---------|------|
| `use_filtered` | `bool` | `False` | 是否使用 wave_pool_filtered 构建 peaklet 波形 |
| `clip_negative_signal` | `bool` | `False` | 是否将 baseline/polarity 转换后的负信号裁剪为 0。默认保留负值。 |
| `debug_numba` | `bool` | `False` | 调试 peaklet waveform Numba 路径；启用后 Numba 异常直接抛出。 |
| `log_waveform_diagnostics` | `bool` | `False` | 记录 peaklet waveform 构建统计和耗时诊断信息。 |
| `n_workers` | `int` | `1` | 并行处理的进程数。1=单进程，0=自动（使用 CPU 核心数-1），>1=指定进程数 |
| `parallel_threshold` | `int` | `5000` | 启用并行化的最小 peaklet 数量。少于此数量时使用单进程 |

## Execution Path

`peaklet_waveforms` 依赖链入口：
`SOURCE -> peaklet_waveforms`

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
waveform-docs generate plugins-agent --plugin peaklet_waveforms

# 覆盖率检查
waveform-docs check coverage --strict
```
