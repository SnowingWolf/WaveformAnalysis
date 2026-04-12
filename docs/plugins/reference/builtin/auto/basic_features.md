# BasicFeaturesPlugin

> Compute basic height, amplitude, and area features from waveform data.

## Overview

| Property | Value |
|----------|-------|
| **Provides** | `basic_features` |
| **Version** | `3.9.0` |
| **Category** | 特征提取 |
| **Accelerator** | CPU (NumPy/SciPy) |
| **Streaming** | No |
| **Side Effect** | No |

## Dependencies

This plugin has no dependencies.

## Configuration Options

| Option | Type | Default | Units | Description |
|--------|------|---------|-------|-------------|
| `height_range` | `tuple` | `(40, 90)` | - | 高度计算范围 (start, end) |
| `area_range` | `tuple` | `(0, None)` | - | 面积计算范围 (start, end)，end=None 表示积分到波形末端 |
| `use_filtered` | `bool` | `False` | - | 是否使用 filtered_waveforms（需要先注册 FilteredWaveformsPlugin） |
| `wave_source` | `str` | `auto` | - | 波形数据源: auto|records|st_waveforms|filtered_waveforms |
| `fixed_baseline` | `dict` | `None` | - | 已废弃；按硬件通道固定 baseline 请改用 channel_config。 |
| `channel_config` | `dict` | `None` | - | 按 (board, channel) 的插件通道覆盖配置，可覆盖 fixed_baseline。 |


## Output Schema

**Output Type**: `structured_array`

| Field | Type | Units | Description |
|-------|------|-------|-------------|
| `height` | `float32` | - | - |
| `amp` | `float32` | - | - |
| `area` | `float32` | - | - |
| `timestamp` | `int64` | - | - |
| `board` | `int16` | - | - |
| `channel` | `int16` | - | - |
| `event_index` | `int64` | - | - |

## Usage Example

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import BasicFeaturesPlugin

# Create context and register plugin
ctx = Context(config={"data_root": "DAQ"})
ctx.register(BasicFeaturesPlugin())

# Configure plugin (optional)
ctx.set_config({
    "height_range": (40, 90),
    "area_range": (0, None),
    "use_filtered": False,
}, plugin_name="basic_features")

# Get data
data = ctx.get_data("run_001", "basic_features")
```

## Module

- **Module Path**: `waveform_analysis.core.plugins.builtin.cpu.basic_features`

---

*This documentation was auto-generated from plugin metadata.*
