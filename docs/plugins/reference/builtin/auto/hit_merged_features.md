# HitMergedFeaturesPlugin

> Compute per-hit_merged local waveform features from records-backed samples.

## Overview

| Property | Value |
|----------|-------|
| **Provides** | `hit_merged_features` |
| **Version** | `0.4.0` |
| **Category** | 特征提取 |
| **Accelerator** | CPU (NumPy/SciPy) |
| **Streaming** | No |
| **Side Effect** | No |

## Dependencies

This plugin has no dependencies.

## Configuration Options

| Option | Type | Default | Units | Description |
|--------|------|---------|-------|-------------|
| `wave_source` | `str` | `records` | - | 波形来源。hit_merged_features 当前正式支持 records。 |
| `use_filtered` | `bool` | `False` | - | 是否使用 wave_pool_filtered 计算局部特征。 |
| `dt` | `int` | `None` | - | 保留兼容配置；特征优先使用 records/hits 的 dt |
| `gain_adc_per_pe` | `dict` | `None` | - | 按硬件通道配置 ADC/PE 增益，键请使用 "board:channel"，例如 {"0:0": 12.5, "0:1": 13.2}。设置后会新增 area_pe/height_pe 列。 |
| `normalize_to_pe` | `bool` | `False` | - | 是否将 area/height 直接归一化为 PE 单位。False (默认): area/height 保持 ADC 单位，area_pe/height_pe 输出 PE 单位。True: area/height 归一化为 PE 单位，area_pe/height_pe 为 NaN。 |


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
| `area_pe` | `float32` | - | - |
| `height_pe` | `float32` | - | - |

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

- **Module Path**: `waveform_analysis.core.plugins.builtin.hit.hit_merged_features`

---

*This documentation was auto-generated from plugin metadata.*
