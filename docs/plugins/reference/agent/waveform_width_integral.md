---
schema_version: 1
document_type: "plugin_reference"
profile: "agent"
provides: "waveform_width_integral"
plugin_class: "WaveformWidthIntegralPlugin"
module: "waveform_analysis.core.plugins.builtin.cpu.waveform_width_integral"
version: "2.7.0"
summary: "Event-wise integral quantile width using st_waveforms or filtered_waveforms."
depends_on: []
output_kind: "structured_array"
generated: true
---
# waveform_width_integral

## Overview

Event-wise integral quantile width using st_waveforms or filtered_waveforms.
| Item | Value |
| --- | --- |
| Provides | `waveform_width_integral` |
| Plugin Class | `WaveformWidthIntegralPlugin` |
| Module | `waveform_analysis.core.plugins.builtin.cpu.waveform_width_integral` |
| Version | `2.7.0` |
| Category | 波形处理 |
| Accelerator | CPU (NumPy/SciPy) |
| Output Kind | `structured_array` |

| Dependency | Version Constraint | Resolution | Required Fields | Description |
| --- | --- | --- | --- | --- |
| - | - | - | - | No declared inputs. |
### How It Works


## Configuration

| Name | Type | Default | Unit | Tracked | Deprecated | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `q_low` | `float` | `0.1` | - | yes | no | 低分位点（默认 0.10） |
| `q_high` | `float` | `0.9` | - | yes | no | 高分位点（默认 0.90） |
| `use_filtered` | `bool` | `False` | - | yes | no | 是否使用 filtered_waveforms（若启用，baseline 仍来自 st_waveforms） |
| `wave_source` | `str` | `auto` | - | yes | no | 波形数据源: auto\|records\|st_waveforms\|filtered_waveforms |
| `sampling_rate` | `float` | `0.5` | - | yes | no | 采样率（GHz），用于换算时间（ns） |
| `dt` | `float` | `None` | - | yes | no | 采样间隔（ns），优先级高于 sampling_rate |
## Output

structured_array output with fields: t_low, t_high, width, t_low_samples, t_high_samples, width_samples, q_total, timestamp, ....

| Field | DType | Unit | Meaning |
| --- | --- | --- | --- |
| `t_low` | `float32` | - | Low-quantile integral point (ns, corresponding to q_low) |
| `t_high` | `float32` | - | High-quantile integral point (ns, corresponding to q_high) |
| `width` | `float32` | - | t_high minus t_low (ns) |
| `t_low_samples` | `float32` | - | Low-quantile integral point in sample index |
| `t_high_samples` | `float32` | - | High-quantile integral point in sample index |
| `width_samples` | `float32` | - | Pulse width in sample counts |
| `q_total` | `float64` | - | Total baseline-subtracted charge (integral) |
| `timestamp` | `int64` | - | ADC event timestamp |
| `board` | `int16` | - | Hardware board index |
| `channel` | `int16` | - | Physical channel number |
| `record_id` | `int64` | - | Source record identifier |
## Usage

### Minimal Example

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import WaveformWidthIntegralPlugin

ctx = Context(config={"data_root": "DAQ"})
ctx.register(WaveformWidthIntegralPlugin())
data = ctx.get_data("run_001", "waveform_width_integral")
```

## Operational Notes

### Behavior

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
waveform-docs generate plugins-agent --plugin waveform_width_integral
waveform-docs check coverage --strict --fail-on-warning
```
