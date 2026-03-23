# waveform_width_integral (WaveformWidthIntegralPlugin)

> Agent-first 插件契约文档。面向自动化执行与改动评估。

## Agent Contract

| Item | Value |
|------|-------|
| Provides | `waveform_width_integral` |
| Depends On | - |
| Output Kind | `structured_array` |
| Version | `2.3.0` |
| Module | `waveform_analysis.core.plugins.builtin.cpu.waveform_width_integral` |
| Accelerator | `cpu` |

## Inputs

- 无依赖输入（source plugin）

## Outputs

| Field | DType |
|-------|-------|
| `t_low` | `float32` |
| `t_high` | `float32` |
| `width` | `float32` |
| `t_low_samples` | `float32` |
| `t_high_samples` | `float32` |
| `width_samples` | `float32` |
| `q_total` | `float64` |
| `timestamp` | `int64` |
| `board` | `int16` |
| `channel` | `int16` |
| `event_index` | `int64` |

## Config

| Name | Type | Default | Note |
|------|------|---------|------|
| `q_low` | `float` | `0.1` | 低分位点（默认 0.10） |
| `q_high` | `float` | `0.9` | 高分位点（默认 0.90） |
| `polarity` | `str` | `auto` | 信号极性: auto | positive | negative |
| `use_filtered` | `bool` | `False` | 是否使用 filtered_waveforms（若启用，baseline 仍来自 st_waveforms） |
| `wave_source` | `str` | `auto` | 波形数据源: auto|records|st_waveforms|filtered_waveforms |
| `sampling_rate` | `float` | `0.5` | 采样率（GHz），用于换算时间（ns） |
| `dt` | `float` | `None` | 采样间隔（ns），优先级高于 sampling_rate |
| `daq_adapter` | `str` | `None` | DAQ 适配器名称（用于自动推断采样率） |
| `channel_metadata` | `dict` | `None` | 每通道元数据映射（支持 run_id 分层），用于按通道选择 polarity |

## Execution Path

`waveform_width_integral` 依赖链入口：
`SOURCE -> waveform_width_integral`

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
waveform-docs generate plugins-agent --plugin waveform_width_integral

# 覆盖率检查
waveform-docs check coverage --strict
```
