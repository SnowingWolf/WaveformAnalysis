# HitMergePlugin

> Merge nearby threshold hits per channel with time-gap and max-width constraints.

## Overview

| Property | Value |
|----------|-------|
| **Provides** | `hit_merged` |
| **Version** | `0.6.0` |
| **Category** | 特征提取 |
| **Accelerator** | CPU (NumPy/SciPy) |
| **Streaming** | No |
| **Side Effect** | No |

## Dependencies

This plugin depends on the following data:

- [`hit_threshold`](hit_threshold.md)

## Configuration Options

| Option | Type | Default | Units | Description |
|--------|------|---------|-------|-------------|
| `merge_gap_ns` | `float` | `0.0` | - | 最大边界间距（ns），<=0 表示不合并 |
| `max_total_width_ns` | `float` | `10000.0` | - | 链式合并后的最大总宽度（ns） |
| `dt` | `int` | `None` | - | 采样间隔（ns）。仅在输入 hit_threshold 缺少 dt 字段时作为兼容补充。 |


## Output Schema

**Output Type**: `structured_array`

| Field | Type | Units | Description |
|-------|------|-------|-------------|
| `position` | `int64` | - | - |
| `height` | `float32` | - | - |
| `integral` | `float32` | - | - |
| `edge_start` | `float32` | - | - |
| `edge_end` | `float32` | - | - |
| `width` | `float32` | - | - |
| `dt` | `int32` | - | - |
| `rise_time` | `float32` | - | - |
| `fall_time` | `float32` | - | - |
| `timestamp` | `int64` | - | - |
| `board` | `int16` | - | - |
| `channel` | `int16` | - | - |
| `record_id` | `int64` | - | - |
| `record_sample_start` | `int32` | - | - |
| `record_sample_end` | `int32` | - | - |
| `wave_pool_start` | `int64` | - | - |
| `wave_pool_end` | `int64` | - | - |
| `component_offset` | `int64` | - | - |
| `component_count` | `int32` | - | - |

## Usage Example

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import HitMergePlugin

# Create context and register plugin
ctx = Context(config={"data_root": "DAQ"})
ctx.register(HitMergePlugin())

# Configure plugin (optional)
ctx.set_config({
    "merge_gap_ns": 0.0,
    "max_total_width_ns": 10000.0,
    "dt": None,
}, plugin_name="hit_merged")

# Get data
data = ctx.get_data("run_001", "hit_merged")
```

## Module

- **Module Path**: `waveform_analysis.core.plugins.builtin.cpu.hit_merge`

---

*This documentation was auto-generated from plugin metadata.*
