# records_asymmetry_mask (RecordsAsymmetryMaskPlugin)

> Agent-first 插件契约文档。面向自动化执行与改动评估。

## Agent Contract

| Item | Value |
|------|-------|
| Provides | `records_asymmetry_mask` |
| Depends On | `records`, `wave_pool` |
| Output Kind | `array` |
| Version | `0.2.0` |
| Module | `waveform_analysis.core.plugins.builtin.cpu.records_asymmetry` |
| Accelerator | `cpu` |

## Inputs

- `records`
- `wave_pool`

## Outputs

| Field | DType | Meaning |
|-------|-------|---------|
| `value` | `bool` | - |

## Config

| Name | Type | Default | Note |
|------|------|---------|------|
| `asymmetry_cut_min` | `float` | `0.7` | Keep records with asymmetry >= this value. |
| `asymmetry_parallel` | `bool` | `True` | Use Numba prange parallel loop. |
| `asymmetry_chunk_size` | `int` | `200000` | Number of records processed per Numba call. |
| `asymmetry_num_threads` | `int` | `0` | Numba thread count. <=0 keeps current Numba default. |
| `asymmetry_polarity_mode` | `str` | `auto` | Polarity handling mode: 'auto' (extract from records['polarity']), 'negative' (baseline - w_min), 'positive' (w_max - baseline). |

## Execution Path

`records_asymmetry_mask` 依赖链入口：
`records -> wave_pool -> records_asymmetry_mask`

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
waveform-docs generate plugins-agent --plugin records_asymmetry_mask

# 覆盖率检查
waveform-docs check coverage --strict
```
