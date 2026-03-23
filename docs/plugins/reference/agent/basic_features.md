# basic_features (BasicFeaturesPlugin)

> Agent-first 插件契约文档。面向自动化执行与改动评估。

## Agent Contract

| Item | Value |
|------|-------|
| Provides | `basic_features` |
| Depends On | - |
| Output Kind | `structured_array` |
| Version | `3.4.0` |
| Module | `waveform_analysis.core.plugins.builtin.cpu.basic_features` |
| Accelerator | `cpu` |

## Inputs

- 无依赖输入（source plugin）

## Outputs

| Field | DType |
|-------|-------|
| `height` | `float32` |
| `amp` | `float32` |
| `area` | `float32` |
| `timestamp` | `int64` |
| `channel` | `int16` |
| `event_index` | `int64` |

## Config

| Name | Type | Default | Note |
|------|------|---------|------|
| `height_range` | `tuple` | `(40, 90)` | 高度计算范围 (start, end) |
| `area_range` | `tuple` | `(0, None)` | 面积计算范围 (start, end)，end=None 表示积分到波形末端 |
| `use_filtered` | `bool` | `False` | 是否使用 filtered_waveforms（需要先注册 FilteredWaveformsPlugin） |
| `wave_source` | `str` | `auto` | 波形数据源: auto|records|st_waveforms|filtered_waveforms |
| `polarity` | `str` | `auto` | 信号极性: auto | positive | negative |
| `channel_metadata` | `dict` | `None` | 每通道元数据映射（支持 run_id 分层），用于按通道选择 polarity |
| `fixed_baseline` | `dict` | `None` | 按通道固定 baseline 值，如 {0: 8192, 1: 8200}。设置后覆盖动态 baseline 用于 height/area 计算。 |

## Execution Path

`basic_features` 依赖链入口：
`SOURCE -> basic_features`

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
waveform-docs generate plugins-agent --plugin basic_features

# 覆盖率检查
waveform-docs check coverage --strict
```
