# events (EventPlugin)

> Agent-first 插件契约文档。面向自动化执行与改动评估。

## Agent Contract

| Item | Value |
|------|-------|
| Provides | `events` |
| Depends On | `s1_s2_pairs`, `position_reconstruction` |
| Output Kind | `structured_array` |
| Version | `0.0.0` |
| Module | `waveform_analysis.core.plugins.builtin.cpu.event` |
| Accelerator | `cpu` |

## Source Notes

完整事件重建插件

整合 S1-S2 配对、位置重建和事件级别特征。

此插件是事件分析链的最终阶段，整合所有前置分析结果，
输出完整的物理事件记录，包含：
- S1/S2 信号特征
- 空间位置信息
- 事件拓扑特征（预留）
- 质量评估指标

第一版 (v0.0.0) 仅建立数据结构和 lineage，高级特征预留接口。

事件重建流程：
1. 从 s1_s2_pairs 获取选定配对
2. 从 position_reconstruction 获取位置信息
3. 复制基本特征
4. 评估事件质量
5. 输出完整事件记录

Author: Claude Code
Version: 0.0.0 (Placeholder for lineage)

## Inputs

- `s1_s2_pairs`
- `position_reconstruction`

## Outputs

| Field | DType | Meaning |
|-------|-------|---------|
| `event_id` | `int64` | - |
| `event_number` | `int64` | - |
| `run_id` | `<U32` | - |
| `pair_id` | `int64` | - |
| `s1_peak_id` | `int64` | - |
| `s2_peak_id` | `int64` | - |
| `x` | `float32` | - |
| `y` | `float32` | - |
| `z` | `float32` | - |
| `r` | `float32` | - |
| `drift_time` | `float32` | - |
| `s1_time` | `float64` | - |
| `s2_time` | `float64` | - |
| `s1_area` | `float32` | - |
| `s2_area` | `float32` | - |
| `log10_s2_s1` | `float32` | - |
| `s1_n_channels` | `int16` | - |
| `s2_n_channels` | `int16` | - |
| `s1_area_fraction_top` | `float32` | - |
| `s2_area_fraction_top` | `float32` | - |
| `s1_rise_time` | `float32` | - |
| `s2_rise_time` | `float32` | - |
| `n_s1_candidates` | `int32` | - |
| `n_s2_candidates` | `int32` | - |
| `flags` | `uint32` | - |

## Config

| Name | Type | Default | Note |
|------|------|---------|------|
| `min_s1` | `float` | `0.0` | 最小 S1 阈值（用于质量筛选） |
| `min_s2` | `float` | `0.0` | 最小 S2 阈值（用于质量筛选） |
| `fiducial_radius` | `(<class 'float'>, <class 'NoneType'>)` | `None` | 基准体积半径 (mm)。None 表示不应用 |
| `fiducial_z_range` | `(<class 'tuple'>, <class 'NoneType'>)` | `None` | 基准体积 Z 范围 (z_min, z_max) mm。None 表示不应用 |

## Execution Path

`events` 依赖链入口：
`s1_s2_pairs -> position_reconstruction -> events`

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
waveform-docs generate plugins-agent --plugin events

# 覆盖率检查
waveform-docs check coverage --strict
```
