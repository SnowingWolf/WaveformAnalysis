---
schema_version: 1
document_type: "plugin_reference"
profile: "agent"
provides: "events"
plugin_class: "EventPlugin"
module: "waveform_analysis.core.plugins.builtin.cpu.event"
version: "0.0.1"
summary: "Complete event reconstruction from S1-S2 pairs and position"
depends_on: ["s1_s2_pairs", "position_reconstruction"]
output_kind: "structured_array"
generated: true
---
# events

## Overview

Complete event reconstruction from S1-S2 pairs and position

| Item | Value |
| --- | --- |
| Provides | `events` |
| Plugin Class | `EventPlugin` |
| Module | `waveform_analysis.core.plugins.builtin.cpu.event` |
| Version | `0.0.1` |
| Category | 事件分析 |
| Accelerator | CPU (NumPy/SciPy) |
| Output Kind | `structured_array` |

| Dependency | Version Constraint | Resolution | Required Fields | Description |
| --- | --- | --- | --- | --- |
| `s1_s2_pairs` | - | declared | - | - |
| `position_reconstruction` | - | declared | - | - |
## Configuration

| Name | Type | Default | Unit | Tracked | Deprecated | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `min_s1` | `float` | `0.0` | - | yes | no | 最小 S1 阈值（用于质量筛选） |
| `min_s2` | `float` | `0.0` | - | yes | no | 最小 S2 阈值（用于质量筛选） |
| `fiducial_radius` | `(<class 'float'>, <class 'NoneType'>)` | `None` | - | yes | no | 基准体积半径 (mm)。None 表示不应用 |
| `fiducial_z_range` | `(<class 'tuple'>, <class 'NoneType'>)` | `None` | - | yes | no | 基准体积 Z 范围 (z_min, z_max) mm。None 表示不应用 |
## Output

| Field | DType | Unit | Meaning |
| --- | --- | --- | --- |
| `event_id` | `int64` | - | - |
| `event_number` | `int64` | - | - |
| `run_id` | `<U32` | - | - |
| `pair_id` | `int64` | - | - |
| `s1_peak_id` | `int64` | - | - |
| `s2_peak_id` | `int64` | - | - |
| `x` | `float32` | - | - |
| `y` | `float32` | - | - |
| `z` | `float32` | - | - |
| `r` | `float32` | - | - |
| `drift_time` | `float32` | - | - |
| `s1_time` | `float64` | - | - |
| `s2_time` | `float64` | - | - |
| `s1_area` | `float32` | - | - |
| `s2_area` | `float32` | - | - |
| `log10_s2_s1` | `float32` | - | - |
| `s1_n_channels` | `int16` | - | - |
| `s2_n_channels` | `int16` | - | - |
| `s1_area_fraction_top` | `float32` | - | - |
| `s2_area_fraction_top` | `float32` | - | - |
| `s1_rise_time` | `float32` | - | - |
| `s2_rise_time` | `float32` | - | - |
| `n_s1_candidates` | `int32` | - | - |
| `n_s2_candidates` | `int32` | - | - |
| `flags` | `uint32` | - | - |
## Usage

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import EventPlugin

ctx = Context(config={"data_root": "DAQ"})
ctx.register(EventPlugin())
data = ctx.get_data("run_001", "events")
```

## Operational Notes

### Behavior

- 完整事件重建插件

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
waveform-docs generate plugins-agent --plugin events
waveform-docs check coverage --strict --fail-on-warning
```
