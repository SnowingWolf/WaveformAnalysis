# PeakletPlugin

> Build cross-channel peaklets and compute pulse-level features.

## Overview

| Property | Value |
|----------|-------|
| **Provides** | `peaklets` |
| **Version** | `0.1.0` |
| **Category** | 特征提取 |
| **Accelerator** | CPU (NumPy/SciPy) |
| **Streaming** | Yes |
| **Side Effect** | No |

## Dependencies

This plugin depends on the following data:

- [`hit_merged`](hit_merged.md)
- [`hit_merged_components`](hit_merged_components.md)
- [`hit_threshold`](hit_threshold.md)
- [`records`](records.md)
- [`wave_pool`](wave_pool.md)

## Configuration Options

| Option | Type | Default | Units | Description |
|--------|------|---------|-------|-------------|
| `time_window_ns` | `float` | `100.0` | - | 跨通道 peaklet 合并时间窗口 |
| `max_total_width_ns` | `float` | `10000.0` | - | peaklet 最大总宽度 |
| `use_filtered` | `bool` | `False` | - | 是否使用 wave_pool_filtered 计算特征 |
| `dt` | `int` | `None` | - | 保留兼容配置；特征优先使用 records/hits 的 dt |


## Output Schema

**Output Type**: `structured_array`

| Field | Type | Units | Description |
|-------|------|-------|-------------|
| `time_start` | `int64` | - | - |
| `time_end` | `int64` | - | - |
| `center_time` | `int64` | - | - |
| `max_time` | `int64` | - | - |
| `area` | `float32` | - | - |
| `height` | `float32` | - | - |
| `width` | `float32` | - | - |
| `rise_time` | `float32` | - | - |
| `fall_time` | `float32` | - | - |
| `n_hits` | `int32` | - | - |
| `n_channels` | `int32` | - | - |
| `component_offset` | `int64` | - | - |
| `component_count` | `int32` | - | - |

## Usage Example

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import PeakletPlugin

# Create context and register plugin
ctx = Context(config={"data_root": "DAQ"})
ctx.register(PeakletPlugin())

# Configure plugin (optional)
ctx.set_config({
    "time_window_ns": 100.0,
    "max_total_width_ns": 10000.0,
    "use_filtered": False,
}, plugin_name="peaklets")

# Get data
data = ctx.get_data("run_001", "peaklets")
```

## Module

- **Module Path**: `waveform_analysis.core.plugins.builtin.cpu.peaklets`

---

*This documentation was auto-generated from plugin metadata.*
