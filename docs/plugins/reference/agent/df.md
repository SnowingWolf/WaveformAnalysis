# df (DataFramePlugin)

> Agent-first 插件契约文档。面向自动化执行与改动评估。

## Agent Contract

| Item | Value |
|------|-------|
| Provides | `df` |
| Depends On | `st_waveforms`, `basic_features` |
| Output Kind | `unknown` |
| Version | `1.3.0` |
| Module | `waveform_analysis.core.plugins.builtin.cpu.dataframe` |
| Accelerator | `cpu` |

## Inputs

- `st_waveforms`
- `basic_features`

## Outputs

- 无结构化字段信息（`unknown`）

## Config

| Name | Type | Default | Note |
|------|------|---------|------|
| `gain_adc_per_pe` | `dict` | `None` | 按通道配置 ADC/PE 增益，如 {0: 12.5, 1: 13.2}。显式设置优先；未显式设置时可从 `<run_path>/run_config.json` 的 `calibration.gain_adc_per_pe` 读取。 |

## Execution Path

`df` 依赖链入口：
`st_waveforms -> basic_features -> df`

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
waveform-docs generate plugins-agent --plugin df

# 覆盖率检查
waveform-docs check coverage --strict
```
