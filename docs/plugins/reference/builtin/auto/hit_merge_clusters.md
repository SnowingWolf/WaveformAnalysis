# HitMergeClustersPlugin

> Internal cluster membership rows shared by hit_merged outputs.

## Overview

| Property | Value |
|----------|-------|
| **Provides** | `hit_merge_clusters` |
| **Version** | `0.1.0` |
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
| `cluster_index` | `int64` | - | - |
| `hit_index` | `int64` | - | - |

## Usage Example

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import HitMergeClustersPlugin

# Create context and register plugin
ctx = Context(config={"data_root": "DAQ"})
ctx.register(HitMergeClustersPlugin())

# Configure plugin (optional)
ctx.set_config({
    "merge_gap_ns": 0.0,
    "max_total_width_ns": 10000.0,
    "dt": None,
}, plugin_name="hit_merge_clusters")

# Get data
data = ctx.get_data("run_001", "hit_merge_clusters")
```

## Module

- **Module Path**: `waveform_analysis.core.plugins.builtin.cpu.hit_merge`

---

*This documentation was auto-generated from plugin metadata.*
