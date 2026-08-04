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
波形宽度计算插件 - 基于峰值检测结果计算上升/下降时间。

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

1. 计算波形宽度特征
2. 基于 HitFinderPlugin 的峰值检测结果，计算每个峰值的上升/下降时间。

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
| `rise_time` | `float32` | ns | Rise time from 10% to 90% of peak height (ns) |
| `fall_time` | `float32` | ns | Fall time from 90% to 10% of peak height (ns) |
| `total_width` | `float32` | ns | Total width from 10% rise to 10% fall (ns) |
| `rise_time_samples` | `float32` | samples | Rise time in sample counts |
| `fall_time_samples` | `float32` | samples | Fall time in sample counts |
| `total_width_samples` | `float32` | samples | Total width in sample counts |
| `peak_position` | `int64` | samples | Peak position as sample index |
| `peak_height` | `float32` | ADC counts | Peak height above baseline |
| `timestamp` | `int64` | ps | Event timestamp in picoseconds |
| `board` | `int16` | None | Hardware board index |
| `channel` | `int16` | None | Physical channel number |
| `record_id` | `int64` | None | Source record identifier |
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
