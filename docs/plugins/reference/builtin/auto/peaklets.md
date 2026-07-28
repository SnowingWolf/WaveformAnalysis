---
schema_version: 1
document_type: "plugin_reference"
profile: "auto"
provides: "peaklets"
plugin_class: "PeakletPlugin"
module: "waveform_analysis.core.plugins.builtin.peaks.peaklets"
version: "1.2.0"
summary: "Build lightweight cross-channel peaklets from hit_merged intervals."
depends_on: ["hit_merged", "peaklet_components"]
output_kind: "structured_array"
generated: true
---
# peaklets

## Overview

Build lightweight cross-channel peaklets from hit_merged intervals.
| Item | Value |
| --- | --- |
| Provides | `peaklets` |
| Plugin Class | `PeakletPlugin` |
| Module | `waveform_analysis.core.plugins.builtin.peaks.peaklets` |
| Version | `1.2.0` |
| Category | 峰构建 |
| Accelerator | CPU (NumPy/SciPy) |
| Output Kind | `structured_array` |

| Dependency | Version Constraint | Resolution | Required Fields | Description |
| --- | --- | --- | --- | --- |
| `hit_merged` | - | declared | - | Merge nearby threshold hits per channel with time-gap and max-width constraints. |
| `peaklet_components` | - | declared | - | Return per-peaklet component hit_merged indices. |
### How It Works


## Configuration

| Name | Type | Default | Unit | Tracked | Deprecated | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `time_window_ns` | `float` | `100.0` | - | yes | no | 跨通道 peaklet 合并时间窗口 |
| `max_total_width_ns` | `float` | `10000.0` | - | yes | no | peaklet 最大总宽度 |
| `dt` | `int` | `None` | - | yes | no | 保留兼容配置；优先使用输入 hit_merged 的 dt |
## Output

structured_array output with fields: time_start, time_end, center_time, n_hits, n_channels, component_offset, component_count.

| Field | DType | Unit | Meaning |
| --- | --- | --- | --- |
| `time_start` | `int64` | - | Earliest absolute start time across component hits (ps) |
| `time_end` | `int64` | - | Latest absolute end time across component hits (ps) |
| `center_time` | `int64` | - | Midpoint of time_start and time_end (ps) |
| `n_hits` | `int32` | - | Total number of component hits in the peaklet |
| `n_channels` | `int32` | - | Number of distinct (board, channel) pairs in the peaklet |
| `component_offset` | `int64` | - | Start row in peaklet_components for this peaklet |
| `component_count` | `int32` | - | Number of component rows in peaklet_components for this peaklet |
## Usage

### Minimal Example

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import PeakletPlugin

ctx = Context(config={"data_root": "DAQ"})
ctx.register(PeakletPlugin())
data = ctx.get_data("run_001", "peaklets")
```
### Downstream Consumers

- `peaklet_channels`
- `peaklet_features`
- `peaks`
