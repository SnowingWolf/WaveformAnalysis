---
schema_version: 1
document_type: "plugin_reference"
profile: "auto"
provides: "waveform_width_integral"
plugin_class: "WaveformWidthIntegralPlugin"
module: "waveform_analysis.core.plugins.builtin.waveform_width_integral.plugin"
version: "2.7.0"
summary: "Event-wise integral quantile width using st_waveforms or filtered_waveforms."
depends_on: []
output_kind: "structured_array"
generated: true
---
# waveform_width_integral

## Overview

Event-wise integral quantile width using st_waveforms or filtered_waveforms.
事件级积分分位数宽度 (Event-wise Integral Quantile Width)。

| Item | Value |
| --- | --- |
| Provides | `waveform_width_integral` |
| Plugin Class | `WaveformWidthIntegralPlugin` |
| Module | `waveform_analysis.core.plugins.builtin.waveform_width_integral.plugin` |
| Version | `2.7.0` |
| Category | 波形处理 |
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
| `t_low` | `float32` | ns | Low-quantile integral point (ns, corresponding to q_low) |
| `t_high` | `float32` | ns | High-quantile integral point (ns, corresponding to q_high) |
| `width` | `float32` | ns | t_high minus t_low (ns) |
| `t_low_samples` | `float32` | samples | Low-quantile integral point in sample index |
| `t_high_samples` | `float32` | samples | High-quantile integral point in sample index |
| `width_samples` | `float32` | samples | Pulse width in sample counts |
| `q_total` | `float64` | ADC counts | Total baseline-subtracted charge (integral) |
| `timestamp` | `int64` | ps | ADC event timestamp |
| `board` | `int16` | None | Hardware board index |
| `channel` | `int16` | None | Physical channel number |
| `record_id` | `int64` | None | Source record identifier |
## Usage

### Minimal Example

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.waveform_width_integral import WaveformWidthIntegralPlugin

ctx = Context(config={"data_root": "DAQ"})
ctx.register(WaveformWidthIntegralPlugin())
data = ctx.get_data("run_001", "waveform_width_integral")
```
### Downstream Consumers

- Terminal output; no direct builtin consumer is declared.
