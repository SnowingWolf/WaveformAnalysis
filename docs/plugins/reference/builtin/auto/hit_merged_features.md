# HitMergedFeaturesPlugin

> Compute per-hit_merged local waveform features from records-backed samples.

## Overview

| Property | Value |
|----------|-------|
| **Provides** | `hit_merged_features` |
| **Version** | `0.1.0` |
| **Category** | 特征提取 |
| **Accelerator** | CPU (NumPy/SciPy) |
| **Streaming** | No |
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
| `wave_source` | `str` | `records` | - | 波形来源。hit_merged_features 当前正式支持 records。 |
| `use_filtered` | `bool` | `False` | - | 是否使用 wave_pool_filtered 计算局部特征。 |
| `dt` | `int` | `None` | - | 保留兼容配置；特征优先使用 records/hits 的 dt |


## Output Schema

**Output Type**: `structured_array`

| Field | Type | Units | Description |
|-------|------|-------|-------------|
| `merged_index` | `int64` | - | - |
| `board` | `int16` | - | - |
| `channel` | `int16` | - | - |
| `record_id` | `int64` | - | - |
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
| `valid` | `int8` | - | - |

## Usage Example

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import HitMergedFeaturesPlugin

# Create context and register plugin
ctx = Context(config={"data_root": "DAQ"})
ctx.register(HitMergedFeaturesPlugin())

# Configure plugin (optional)
ctx.set_config({
    "wave_source": 'records',
    "use_filtered": False,
    "dt": None,
}, plugin_name="hit_merged_features")

# Get data
data = ctx.get_data("run_001", "hit_merged_features")
```

## Module

- **Module Path**: `waveform_analysis.core.plugins.builtin.cpu.hit_merged_features`

---

*This documentation was auto-generated from plugin metadata.*
