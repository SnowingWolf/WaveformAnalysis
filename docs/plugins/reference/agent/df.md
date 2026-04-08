# df (DataFramePlugin)

> Agent-first 插件契约文档。面向自动化执行与改动评估。

## Agent Contract

| Item | Value |
|------|-------|
| Provides | `df` |
| Depends On | - |
| Output Kind | `unknown` |
| Version | `1.7.0` |
| Module | `waveform_analysis.core.plugins.builtin.cpu.dataframe` |
| Accelerator | `cpu` |

## Inputs

- 无依赖输入（source plugin）

## Outputs

- 无结构化字段信息（`unknown`）

## Config

| Name | Type | Default | Note |
|------|------|---------|------|
| `use_filtered` | `bool` | `False` | 是否使用 filtered_waveforms（需要先注册 FilteredWaveformsPlugin） |
| `wave_source` | `str` | `auto` | 波形数据源: auto|records|st_waveforms|filtered_waveforms |
| `gain_adc_per_pe` | `dict` | `None` | 按硬件通道配置 ADC/PE 增益，键请使用 "board:channel"，例如 {"0:0": 12.5, "0:1": 13.2}。设置后会新增 area_pe/height_pe 列。 |

## Execution Path

`df` 依赖链入口：
`SOURCE -> df`

## Failure Modes

- 依赖数据缺失或字段不匹配，导致 compute 阶段报错
- 配置值类型/范围不合法，触发参数校验异常
- 输出 dtype 变更但版本未升级，可能导致缓存命中异常

## Change Playbook

1. 修改 `options`/`output_dtype`/核心算法后同步提升 `version`
2. 保持 `provides` 稳定；若必须变更，更新依赖插件与文档索引
3. 新增/删除输出字段时，同时更新消费方插件和回归测试；当前 DataFrame 默认包含 `record_id`

## Validation

```bash
# 单插件文档再生成
waveform-docs generate plugins-agent --plugin df

# 覆盖率检查
waveform-docs check coverage --strict
```
