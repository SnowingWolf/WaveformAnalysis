---
schema_version: 1
document_type: "plugin_reference"
profile: "auto"
provides: "waveform_width"
plugin_class: "WaveformWidthPlugin"
module: "waveform_analysis.core.plugins.builtin.cpu.waveform_width"
version: "3.0.0"
summary: "Calculate rise/fall time based on peak detection results."
depends_on: []
output_kind: "structured_array"
generated: true
---
# waveform_width

## Overview

Calculate rise/fall time based on peak detection results.
| Item | Value |
| --- | --- |
| Provides | `waveform_width` |
| Plugin Class | `WaveformWidthPlugin` |
| Module | `waveform_analysis.core.plugins.builtin.cpu.waveform_width` |
| Version | `3.0.0` |
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
| `use_filtered` | `bool` | `False` | - | yes | no | 是否使用滤波后的波形（需要先注册 FilteredWaveformsPlugin） |
| `sampling_rate` | `float` | `None` | - | yes | no | 采样率（GHz）；未设置时默认使用 0.5 GHz |
| `rise_low` | `float` | `0.1` | - | yes | no | 上升时间的低阈值比例（默认 10%） |
| `rise_high` | `float` | `0.9` | - | yes | no | 上升时间的高阈值比例（默认 90%） |
| `fall_high` | `float` | `0.9` | - | yes | no | 下降时间的高阈值比例（默认 90%） |
| `fall_low` | `float` | `0.1` | - | yes | no | 下降时间的低阈值比例（默认 10%） |
| `interpolation` | `bool` | `True` | - | yes | no | 是否使用线性插值提高时间计算精度 |
## Output

structured_array output with fields: rise_time, fall_time, total_width, rise_time_samples, fall_time_samples, total_width_samples, peak_position, peak_height, ....

| Field | DType | Unit | Meaning |
| --- | --- | --- | --- |
| `rise_time` | `float32` | - | - |
| `fall_time` | `float32` | - | - |
| `total_width` | `float32` | - | - |
| `rise_time_samples` | `float32` | - | - |
| `fall_time_samples` | `float32` | - | - |
| `total_width_samples` | `float32` | - | - |
| `peak_position` | `int64` | - | - |
| `peak_height` | `float32` | - | - |
| `timestamp` | `int64` | - | - |
| `board` | `int16` | - | - |
| `channel` | `int16` | - | - |
| `record_id` | `int64` | - | - |
## Usage

### Minimal Example

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import WaveformWidthPlugin

ctx = Context(config={"data_root": "DAQ"})
ctx.register(WaveformWidthPlugin())
data = ctx.get_data("run_001", "waveform_width")
```
### Downstream Consumers

- Terminal output; no direct builtin consumer is declared.
