---
schema_version: 2
document_type: "plugin_reference"
profile: "agent"
provides: "energy_reconstruction"
plugin_class: "EnergyReconstructionPlugin"
module: "waveform_analysis.core.plugins.builtin.energy_reconstruction.plugin"
version: "0.1.0"
summary: "Reconstruct energy from selected S1-S2 pairs"
depends_on: ["s1_s2_pairs"]
declared_depends_on: ["s1_s2_pairs"]
resolved_depends_on: ["s1_s2_pairs"]
dependency_profile: "declared"
dependency_profile_values: {}
dependency_config_keys: []
output_kind: "structured_array"
execution_kind: "static"
narrative_source: "source"
narrative_source_reason: null
source_fingerprint: "875523fbb2f5b85815c754ab1ccd3f8d700d2811b630c7b38d66ed6c94a0bd56"
generated: true
---
# energy_reconstruction

## Overview

Reconstruct energy from selected S1-S2 pairs
能量重建插件（结构占位版本）

从选定的 S1-S2 配对重建事件能量。

输入: - s1_s2_pairs: S1-S2 配对结果（仅处理 selected=True 的配对）

输出: - energy_reconstruction: 能量重建结果

v0.1.0 功能: - 定义完整的输出结构与接口 - 筛选 selected 配对并填充身份与可观测字段 - 能量字段填占位值 NaN，标志 FLAG_ENERGY_NOT_IMPLEMENTED

未来版本计划: - v0.2.0: 实现基于面积的线性标定能量重建 - v1.0.0: 位置相关能量校正（电场、光收集效率）

| Item | Value |
| --- | --- |
| Provides | `energy_reconstruction` |
| Plugin Class | `EnergyReconstructionPlugin` |
| Module | `waveform_analysis.core.plugins.builtin.energy_reconstruction.plugin` |
| Version | `0.1.0` |
| Category | 其他 |
| Output Container | `structured_array` |
| Execution Mode | `static` |
| Save Policy | `always` |
| Uses Run Config | no |
| Timeout | `none` |
| Side Effect | no |
| Narrative Source | `source` |
| Source Fingerprint | `875523fbb2f5b85815c754ab1ccd3f8d700d2811b630c7b38d66ed6c94a0bd56` |

### Dependencies

默认文档画像：`declared`。

| Dependency | Version Constraint | Resolution | Required Fields | Description |
| --- | --- | --- | --- | --- |
| `s1_s2_pairs` | - | declared | - | Select best S1-S2 pairs from candidates |
### How It Works

1. 执行能量重建（结构占位）
2. v0.1.0 实现: 1. 筛选 selected=True 的配对 2. 填充身份字段与可观测字段 3. 能量字段填占位值 NaN，标记算法未实现

## Configuration

| Name | Type | Default | Unit | Tracked | Deprecated | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `s1_energy_scale` | `float` | `1.0` | - | yes | no | S1 面积到能量的转换系数 (keV/PE)，占位默认值；范围：0.0 至 +∞ |
| `s2_energy_scale` | `float` | `1.0` | - | yes | no | S2 面积到能量的转换系数 (keV/PE)，占位默认值；范围：0.0 至 +∞ |
## Output

structured_array output with fields: event_id, pair_id, s1_peak_id, s2_peak_id, s1_energy, s2_energy, total_energy, s1_energy_fraction, ....

| Field | DType | Unit | Meaning |
| --- | --- | --- | --- |
| `event_id` | `int64` | None | Unique event identifier |
| `pair_id` | `int64` | None | S1-S2 pair identifier |
| `s1_peak_id` | `int64` | None | S1 peak identifier |
| `s2_peak_id` | `int64` | None | S2 peak identifier |
| `s1_energy` | `float32` | keV | S1 energy |
| `s2_energy` | `float32` | keV | S2 energy |
| `total_energy` | `float32` | keV | Total reconstructed energy |
| `s1_energy_fraction` | `float32` | None | S1 energy fraction of total |
| `s1_energy_err` | `float32` | keV | S1 energy uncertainty |
| `s2_energy_err` | `float32` | keV | S2 energy uncertainty |
| `total_energy_err` | `float32` | keV | Total energy uncertainty |
| `energy_chi2` | `float32` | None | Chi-squared for energy reconstruction fit |
| `energy_ndf` | `int16` | None | Degrees of freedom for energy reconstruction |
| `energy_goodness` | `float32` | None | Overall energy reconstruction quality (0 to 1) |
| `s1_method` | `<U16` | None | S1 energy reconstruction method (area_scale, none) |
| `s2_method` | `<U16` | None | S2 energy reconstruction method (area_scale, none) |
| `s1_area` | `float32` | ADC counts | S1 raw area used for energy calibration |
| `s2_area` | `float32` | ADC counts | S2 raw area used for energy calibration |
| `s1_n_channels` | `int16` | None | Number of S1 channels |
| `s2_n_channels` | `int16` | None | Number of S2 channels |
| `drift_time_ns` | `float32` | ns | Drift time in nanoseconds |
| `flags` | `uint32` | None | Bit-field energy reconstruction status flags |
## Usage

### Minimal Example

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins import profiles

ctx = Context(config={"data_root": "DAQ", "daq_adapter": "vx2730"})
ctx.register(*profiles.cpu_default())
result = ctx.get_data("run_001", "energy_reconstruction")
```

示例使用 `run_id="run_001"` 和文档默认运行画像；真实数据路径与配置应以当前实验设置为准。

## Operational Notes

### Behavior

- 能量重建插件（结构占位版本）
- 基于 S1-S2 配对的能量重建。
### Failure Modes

- 任一声明依赖（`s1_s2_pairs`）缺失或字段不符合输入契约时，执行会失败。
- 配置校验或输出 schema 校验失败时，结果不会被视为有效插件产物。
### Downstream Impact

没有声明直接的内置消费者。

## Maintenance

### Change Playbook

1. 保持 `provides`、依赖和输出字段语义稳定，或同步所有下游消费者。
2. 行为、配置或输出契约改变时升级插件 `version`。
3. 修改插件源码后重新生成 Auto、Agent 和 HTML 参考。
### Validation

```bash
waveform-docs generate plugins-agent --plugin energy_reconstruction
waveform-docs check coverage --strict --fail-on-warning
```
