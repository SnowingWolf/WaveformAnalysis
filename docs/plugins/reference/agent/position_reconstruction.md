---
schema_version: 1
document_type: "plugin_reference"
profile: "agent"
provides: "position_reconstruction"
plugin_class: "PositionReconstructionPlugin"
module: "waveform_analysis.core.plugins.builtin.cpu.position_reconstruction"
version: "0.2.1"
summary: "Reconstruct 3D position from S1-S2 pairs using vectorized CoG method"
depends_on: ["s1_s2_pairs"]
output_kind: "structured_array"
generated: true
---
# position_reconstruction

## Overview

Reconstruct 3D position from S1-S2 pairs using vectorized CoG method

| Item | Value |
| --- | --- |
| Provides | `position_reconstruction` |
| Plugin Class | `PositionReconstructionPlugin` |
| Module | `waveform_analysis.core.plugins.builtin.cpu.position_reconstruction` |
| Version | `0.2.1` |
| Category | 其他 |
| Accelerator | CPU (NumPy/SciPy) |
| Output Kind | `structured_array` |

| Dependency | Version Constraint | Resolution | Required Fields | Description |
| --- | --- | --- | --- | --- |
| `s1_s2_pairs` | - | declared | - | - |
## Configuration

| Name | Type | Default | Unit | Tracked | Deprecated | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `drift_velocity` | `float` | `0.0013` | - | yes | no | 漂移速度 (mm/ns)，用于 Z 坐标计算。典型值：液氙 ~0.001 mm/ns, 液氩 ~0.0013 mm/ns |
| `min_s2_area_for_xy` | `float` | `100.0` | - | yes | no | XY 重建所需的最小 S2 面积 (PE) |
| `edge_threshold_mm` | `float` | `5.0` | - | yes | no | 边缘事件判定阈值：距离 TPC 边界的最小距离 (mm) |
| `detector_radius_mm` | `float` | `62.5` | - | yes | no | 探测器有效半径 (mm)，用于边缘事件检测 |
## Output

| Field | DType | Unit | Meaning |
| --- | --- | --- | --- |
| `event_id` | `int64` | - | - |
| `pair_id` | `int64` | - | - |
| `s1_peak_id` | `int64` | - | - |
| `s2_peak_id` | `int64` | - | - |
| `x` | `float32` | - | - |
| `y` | `float32` | - | - |
| `z` | `float32` | - | - |
| `r` | `float32` | - | - |
| `x_err` | `float32` | - | - |
| `y_err` | `float32` | - | - |
| `z_err` | `float32` | - | - |
| `xy_chi2` | `float32` | - | - |
| `xy_ndf` | `int16` | - | - |
| `z_quality` | `float32` | - | - |
| `position_goodness` | `float32` | - | - |
| `xy_method` | `<U16` | - | - |
| `z_method` | `<U16` | - | - |
| `drift_time_ns` | `float32` | - | - |
| `s2_area` | `float32` | - | - |
| `s2_n_channels` | `int16` | - | - |
| `flags` | `uint32` | - | - |
## Usage

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import PositionReconstructionPlugin

ctx = Context(config={"data_root": "DAQ"})
ctx.register(PositionReconstructionPlugin())
data = ctx.get_data("run_001", "position_reconstruction")
```

## Operational Notes

### Behavior

- 位置重建插件（向量化优化版本）

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
### Failure Modes

- Dependency data, configuration, or output contract validation may fail explicitly.
### Downstream Impact

-
## Maintenance

### Change Playbook

1. Keep `provides` and dependency semantics stable or update all consumers.
2. Bump `version` for behavior, configuration, or output contract changes.
3. Regenerate auto, agent, and web references after metadata changes.
### Validation

```bash
waveform-docs generate plugins-agent --plugin position_reconstruction
waveform-docs check coverage --strict --fail-on-warning
```
