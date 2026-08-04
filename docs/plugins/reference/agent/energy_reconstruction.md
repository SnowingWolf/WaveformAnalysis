---
schema_version: 1
document_type: "plugin_reference"
profile: "agent"
provides: "energy_reconstruction"
plugin_class: "EnergyReconstructionPlugin"
module: "waveform_analysis.core.plugins.builtin.energy_reconstruction.plugin"
version: "0.1.0"
summary: "Reconstruct energy from selected S1-S2 pairs"
depends_on: ["s1_s2_pairs"]
output_kind: "structured_array"
generated: true
---
# energy_reconstruction

## Overview

Reconstruct energy from selected S1-S2 pairs
能量重建插件（结构占位版本）

| Item | Value |
| --- | --- |
| Provides | `energy_reconstruction` |
| Plugin Class | `EnergyReconstructionPlugin` |
| Module | `waveform_analysis.core.plugins.builtin.energy_reconstruction.plugin` |
| Version | `0.1.0` |
| Category | 其他 |
| Output Kind | `structured_array` |

| Dependency | Version Constraint | Resolution | Required Fields | Description |
| --- | --- | --- | --- | --- |
| `s1_s2_pairs` | - | declared | - | Select best S1-S2 pairs from candidates |
### How It Works

1. 执行能量重建（结构占位）
2. v0.1.0 实现: 1. 筛选 selected=True 的配对 2. 填充身份字段与可观测字段 3. 能量字段填占位值 NaN，标记算法未实现

## Configuration

| Name | Type | Default | Unit | Tracked | Deprecated | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `s1_energy_scale` | `float` | `1.0` | - | yes | no | S1 面积到能量的转换系数 (keV/PE)，占位默认值 |
| `s2_energy_scale` | `float` | `1.0` | - | yes | no | S2 面积到能量的转换系数 (keV/PE)，占位默认值 |
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
from waveform_analysis.core.plugins.builtin.energy_reconstruction import EnergyReconstructionPlugin

ctx = Context(config={"data_root": "DAQ"})
ctx.register(EnergyReconstructionPlugin())
data = ctx.get_data("run_001", "energy_reconstruction")
```

## Operational Notes

### Behavior

- 执行能量重建（结构占位）
- v0.1.0 实现: 1. 筛选 selected=True 的配对 2. 填充身份字段与可观测字段 3. 能量字段填占位值 NaN，标记算法未实现
### Failure Modes

- Dependency data, configuration, or output contract validation may fail explicitly.
### Downstream Impact

Terminal output; no direct builtin consumer is declared.


## Maintenance

### Change Playbook

1. Keep `provides` and dependency semantics stable or update all consumers.
2. Bump `version` for behavior, configuration, or output contract changes.
3. Regenerate auto, agent, and web references after metadata changes.
### Validation

```bash
waveform-docs generate plugins-agent --plugin energy_reconstruction
waveform-docs check coverage --strict --fail-on-warning
```
