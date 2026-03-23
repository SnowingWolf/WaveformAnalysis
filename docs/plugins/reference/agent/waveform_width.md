# waveform_width (WaveformWidthPlugin)

> Agent-first 插件契约文档。面向自动化执行与改动评估。

## Agent Contract

| Item | Value |
|------|-------|
| Provides | `waveform_width` |
| Depends On | - |
| Output Kind | `structured_array` |
| Version | `2.2.0` |
| Module | `waveform_analysis.core.plugins.builtin.cpu.waveform_width` |
| Accelerator | `cpu` |

## Inputs

- 无依赖输入（source plugin）

## Outputs

| Field | DType |
|-------|-------|
| `rise_time` | `float32` |
| `fall_time` | `float32` |
| `total_width` | `float32` |
| `rise_time_samples` | `float32` |
| `fall_time_samples` | `float32` |
| `total_width_samples` | `float32` |
| `peak_position` | `int64` |
| `peak_height` | `float32` |
| `timestamp` | `int64` |
| `board` | `int16` |
| `channel` | `int16` |
| `event_index` | `int64` |

## Config

| Name | Type | Default | Note |
|------|------|---------|------|
| `use_filtered` | `bool` | `False` | 是否使用滤波后的波形（需要先注册 FilteredWaveformsPlugin） |
| `sampling_rate` | `float` | `None` | 采样率（GHz），未显式设置时优先从 DAQ 适配器推断 |
| `daq_adapter` | `str` | `None` | DAQ 适配器名称（用于自动推断采样率） |
| `rise_low` | `float` | `0.1` | 上升时间的低阈值比例（默认 10%） |
| `rise_high` | `float` | `0.9` | 上升时间的高阈值比例（默认 90%） |
| `fall_high` | `float` | `0.9` | 下降时间的高阈值比例（默认 90%） |
| `fall_low` | `float` | `0.1` | 下降时间的低阈值比例（默认 10%） |
| `interpolation` | `bool` | `True` | 是否使用线性插值提高时间计算精度 |

## Execution Path

`waveform_width` 依赖链入口：
`SOURCE -> waveform_width`

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
waveform-docs generate plugins-agent --plugin waveform_width

# 覆盖率检查
waveform-docs check coverage --strict
```
