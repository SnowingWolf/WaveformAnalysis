# basic_features (BasicFeaturesPlugin)

> Agent-first 插件契约文档。面向自动化执行与改动评估。

## Agent Contract

| Item | Value |
|------|-------|
| Provides | `basic_features` |
| Depends On | - |
| Output Kind | `structured_array` |
| Version | `4.1.0` |
| Module | `waveform_analysis.core.plugins.builtin.cpu.basic_features` |
| Accelerator | `cpu` |

## Source Notes

Basic Features Plugin - 基础特征计算插件

**加速器**: CPU (NumPy)
**功能**: 计算波形的基础特征（height/area）

本模块包含基础特征计算插件，从结构化波形中提取：
- height: 脉冲高度（baseline - min(wave)），信号偏离基线的幅度
- amp: 峰峰值振幅（max - min）
- area: 波形面积（积分）
- max_abs_diff: 波形相邻采样点差分绝对值最大值

支持可选的滤波波形输入，可配置计算范围。

设计原则：
- 逐条处理 record，支持任意长度波形
- 不使用 padding，避免 padding 影响 area 计算
- 内存占用最低，最适合 records streaming
- 通道配置缓存，避免重复解析

## Inputs

- 无依赖输入（source plugin）

## Outputs

| Field | DType | Meaning |
|-------|-------|---------|
| `height` | `float32` | - |
| `amp` | `float32` | - |
| `area` | `float32` | - |
| `max_abs_diff` | `float32` | - |
| `timestamp` | `int64` | - |
| `board` | `int16` | - |
| `channel` | `int16` | - |
| `record_id` | `int64` | - |

## Config

| Name | Type | Default | Note |
|------|------|---------|------|
| `height_range` | `tuple` | `(40, 90)` | 高度计算范围 (start, end) |
| `area_range` | `tuple` | `(0, None)` | 面积计算范围 (start, end)，end=None 表示积分到波形末端 |
| `use_filtered` | `bool` | `False` | 是否使用 filtered_waveforms（需要先注册 FilteredWaveformsPlugin） |
| `wave_source` | `str` | `auto` | 波形数据源: auto|records|st_waveforms|filtered_waveforms |
| `fixed_baseline` | `dict` | `None` | 已废弃；按硬件通道固定 baseline 请改用 channel_config。 |
| `channel_config` | `dict` | `None` | 按 (board, channel) 的插件通道覆盖配置，可覆盖 fixed_baseline。 |
| `compute_max_abs_diff` | `bool` | `True` | 是否计算 max_abs_diff（关闭可减少一次全波形扫描，提升性能） |
| `batch_size` | `int` | `10000` | 批处理大小：当 records 数量超过此值时，分批处理以降低内存峰值 |

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
