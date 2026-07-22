# position_reconstruction (PositionReconstructionPlugin)

> Agent-first 插件契约文档。面向自动化执行与改动评估。

## Agent Contract

| Item | Value |
|------|-------|
| Provides | `position_reconstruction` |
| Depends On | `s1_s2_pairs` |
| Output Kind | `structured_array` |
| Version | `0.2.1` |
| Module | `waveform_analysis.core.plugins.builtin.cpu.position_reconstruction` |
| Accelerator | `cpu` |

## Source Notes

位置重建插件（向量化优化版本）

基于 S1-S2 配对的空间位置重建。

此插件从选定的 S1-S2 配对中提取位置信息，计算事件的三维空间坐标 (x, y, z)。

核心功能：
- 从 s1_s2_pairs 中提取 selected 配对
- 计算 Z 坐标（基于漂移时间）
- 计算 XY 坐标（电荷重心法，基于 S2 光分布）
- 输出位置重建结果及质量指标

位置重建方法：
- Z: 基于漂移时间和漂移速度
- XY: 电荷重心法 (Center of Gravity, CoG)
  使用 S2 信号在各 PMT 通道的分布，应用增益校正后计算加权重心

性能优化（v0.2.0）：
- 向量化 XY 计算，避免 Python 循环
- 批量加载通道数据
- 预计算 PMT 映射表
- 使用 NumPy 广播加速计算

版本历史：
- v0.0.0: 数据结构定义，仅 Z 坐标占位
- v0.1.0: 实现 CoG XY 重建，集成 PMT 几何布局
- v0.2.0: 向量化优化，性能提升 10-100x
- v0.2.1: 修正默认漂移速度单位，确保 drift_time_ns 输出的 Z 坐标为 mm

Author: Claude Code
Version: 0.2.1

## Inputs

- `s1_s2_pairs`

## Outputs

| Field | DType | Meaning |
|-------|-------|---------|
| `event_id` | `int64` | - |
| `pair_id` | `int64` | - |
| `s1_peak_id` | `int64` | - |
| `s2_peak_id` | `int64` | - |
| `x` | `float32` | - |
| `y` | `float32` | - |
| `z` | `float32` | - |
| `r` | `float32` | - |
| `x_err` | `float32` | - |
| `y_err` | `float32` | - |
| `z_err` | `float32` | - |
| `xy_chi2` | `float32` | - |
| `xy_ndf` | `int16` | - |
| `z_quality` | `float32` | - |
| `position_goodness` | `float32` | - |
| `xy_method` | `<U16` | - |
| `z_method` | `<U16` | - |
| `drift_time_ns` | `float32` | - |
| `s2_area` | `float32` | - |
| `s2_n_channels` | `int16` | - |
| `flags` | `uint32` | - |

## Config

| Name | Type | Default | Note |
|------|------|---------|------|
| `drift_velocity` | `float` | `0.0013` | 漂移速度 (mm/ns)，用于 Z 坐标计算。典型值：液氙 ~0.001 mm/ns, 液氩 ~0.0013 mm/ns |
| `min_s2_area_for_xy` | `float` | `100.0` | XY 重建所需的最小 S2 面积 (PE) |
| `edge_threshold_mm` | `float` | `5.0` | 边缘事件判定阈值：距离 TPC 边界的最小距离 (mm) |
| `detector_radius_mm` | `float` | `62.5` | 探测器有效半径 (mm)，用于边缘事件检测 |

## Execution Path

`position_reconstruction` 依赖链入口：
`s1_s2_pairs -> position_reconstruction`

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
waveform-docs generate plugins-agent --plugin position_reconstruction

# 覆盖率检查
waveform-docs check coverage --strict
```
