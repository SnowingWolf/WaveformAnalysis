---
schema_version: 1
document_type: "plugin_reference"
profile: "auto"
provides: "filtered_waveforms"
plugin_class: "FilteredWaveformsPlugin"
module: "waveform_analysis.core.plugins.builtin.cpu.filtering"
version: "3.0.0"
summary: "Apply filtering to waveforms using Butterworth or Savitzky-Golay filters."
depends_on: ["st_waveforms"]
output_kind: "structured_array"
generated: true
---
# filtered_waveforms

## Overview

Apply filtering to waveforms using Butterworth or Savitzky-Golay filters.
| Item | Value |
| --- | --- |
| Provides | `filtered_waveforms` |
| Plugin Class | `FilteredWaveformsPlugin` |
| Module | `waveform_analysis.core.plugins.builtin.cpu.filtering` |
| Version | `3.0.0` |
| Category | 波形处理 |
| Accelerator | CPU (NumPy/SciPy) |
| Output Kind | `structured_array` |

| Dependency | Version Constraint | Resolution | Required Fields | Description |
| --- | --- | --- | --- | --- |
| `st_waveforms` | - | declared | - | Extract waveforms from raw CSV files and structure them into NumPy structured arrays. |
### How It Works


## Configuration

| Name | Type | Default | Unit | Tracked | Deprecated | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `filter_type` | `str` | `SG` | - | yes | no | 滤波器类型: 'BW' 或 'SG' |
| `lowcut` | `float` | `0.1` | - | yes | no | BW 低频截止 |
| `highcut` | `float` | `0.5` | - | yes | no | BW 高频截止 |
| `fs` | `float` | `0.5` | - | yes | no | BW 采样率（GHz） |
| `filter_order` | `int` | `4` | - | yes | no | BW 阶数 |
| `sg_window_size` | `int` | `11` | - | yes | no | SG 窗口大小（奇数） |
| `sg_poly_order` | `int` | `2` | - | yes | no | SG 多项式阶数 |
| `max_workers` | `int` | `None` | - | yes | no | 并行工作线程数；None 使用 CPU 核心数，1 或 0 禁用并行 |
| `batch_size` | `int` | `0` | - | yes | no | 每批次事件数（0 表示不分批，整个通道一次处理） |
| `channel_config` | `dict` | `None` | - | yes | no | 按 (board, channel) 的插件通道覆盖配置，可覆盖滤波参数。 |
## Output

structured_array output with fields: baseline, baseline_upstream, polarity, timestamp, record_id, dt, event_length, board, ....

| Field | DType | Unit | Meaning |
| --- | --- | --- | --- |
| `baseline` | `float64` | - | Computed global waveform baseline for this record |
| `baseline_upstream` | `float64` | - | Upstream baseline value from preceding processing, optional |
| `polarity` | `<U8` | - | Hardware-truth signal polarity: positive \| negative \| unknown |
| `timestamp` | `int64` | - | ADC raw timestamp in picoseconds |
| `record_id` | `int64` | - | Sequential record identifier within the structured waveform array |
| `dt` | `int32` | - | Sample interval in nanoseconds, aligned to time |
| `event_length` | `int32` | - | Waveform length in samples |
| `board` | `int16` | - | Hardware board index |
| `channel` | `int16` | - | Physical channel number |
| `wave` | `('<f4', (1500,))` | - | Filtered ADC sample data as 1-D float32 array |
## Usage

### Minimal Example

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import FilteredWaveformsPlugin

ctx = Context(config={"data_root": "DAQ"})
ctx.register(FilteredWaveformsPlugin())
data = ctx.get_data("run_001", "filtered_waveforms")
```
### Downstream Consumers

- Terminal output; no direct builtin consumer is declared.
