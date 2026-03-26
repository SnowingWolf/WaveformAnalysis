# hit_threshold (ThresholdHitPlugin)

> Agent-first 插件契约文档。面向自动化执行与改动评估。

## Agent Contract

| Item | Value |
|------|-------|
| Provides | `hit_threshold` |
| Depends On | - |
| Output Kind | `structured_array` |
| Version | `0.7.0` |
| Module | `waveform_analysis.core.plugins.builtin.cpu.hit_finder` |
| Accelerator | `cpu` |

## Inputs

- 无依赖输入（source plugin）

## Outputs

| Field | DType |
|-------|-------|
| `position` | `int64` |
| `height` | `float32` |
| `integral` | `float32` |
| `edge_start` | `float32` |
| `edge_end` | `float32` |
| `width` | `float32` |
| `timestamp` | `int64` |
| `board` | `int16` |
| `channel` | `int16` |
| `record_id` | `int64` |

## Config

| Name | Type | Default | Note |
|------|------|---------|------|
| `threshold` | `float` | `10.0` | Hit 检测阈值 |
| `use_filtered` | `bool` | `False` | 是否使用 filtered_waveforms（需要先注册 FilteredWaveformsPlugin） |
| `wave_source` | `str` | `auto` | 波形数据源: auto|records|st_waveforms|filtered_waveforms |
| `polarity` | `str` | `negative` | 信号极性：negative 表示 baseline-wave；positive 表示 wave-baseline |
| `left_extension` | `int` | `2` | Hit 左侧扩展点数 |
| `right_extension` | `int` | `2` | Hit 右侧扩展点数 |
| `sampling_interval_ns` | `float` | `2.0` | 采样间隔（ns），用于计算 timestamp（内部换算到 ps） |
| `channel_config` | `dict` | `None` | 按 (board, channel) 的插件通道覆盖配置，可覆盖 polarity/threshold。 |

## Execution Path

`hit_threshold` 依赖链入口：
`SOURCE -> hit_threshold`

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
waveform-docs generate plugins-agent --plugin hit_threshold

# 覆盖率检查
waveform-docs check coverage --strict
```
