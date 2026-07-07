# PeakletComponentsPlugin

> Return per-peaklet component hit_merged indices.

## Overview

| Property | Value |
|----------|-------|
| **Provides** | `peaklet_components` |
| **Version** | `1.3.0` |
| **Category** | 特征提取 |
| **Accelerator** | CPU (NumPy/SciPy) |
| **Streaming** | No |
| **Side Effect** | No |

## Dependencies

This plugin depends on the following data:

- [`hit_merged`](hit_merged.md)

## Configuration Options

| Option | Type | Default | Units | Description |
|--------|------|---------|-------|-------------|
| `time_window_ns` | `float` | `100.0` | - | 跨通道 peaklet 合并时间窗口 |
| `max_total_width_ns` | `float` | `10000.0` | - | peaklet 最大总宽度 |
| `dt` | `int` | `None` | - | 保留兼容配置；优先使用输入 hit_merged 的 dt |

## Output Schema

**Output Type**: `structured_array`

| Field | Type | Units | Description |
|-------|------|-------|-------------|
| `peak_id` | `int64` | - | - |
| `merged_index` | `int64` | - | - |

## Usage Example

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import PeakletComponentsPlugin

# Create context and register plugin
ctx = Context(config={"data_root": "DAQ"})
ctx.register(PeakletComponentsPlugin())

# Configure plugin (optional)
ctx.set_config({
    "time_window_ns": 100.0,
    "max_total_width_ns": 10000.0,
    "dt": None,
}, plugin_name="peaklet_components")

# Get data
data = ctx.get_data("run_001", "peaklet_components")
```

## Module

- **Module Path**: `waveform_analysis.core.plugins.builtin.peaks.peaklets`

---

*This documentation was auto-generated from plugin metadata.*
