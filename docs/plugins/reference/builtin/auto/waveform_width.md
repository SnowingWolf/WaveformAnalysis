# WaveformWidthPlugin

> Calculate rise/fall time based on peak detection results.

## Overview

| Property | Value |
|----------|-------|
| **Provides** | `waveform_width` |
| **Version** | `3.0.0` |
| **Category** | 波形处理 |
| **Accelerator** | CPU (NumPy/SciPy) |
| **Streaming** | No |
| **Side Effect** | No |

## Dependencies

This plugin has no dependencies.

## Configuration Options

| Option | Type | Default | Units | Description |
|--------|------|---------|-------|-------------|
| `use_filtered` | `bool` | `False` | - | 是否使用滤波后的波形（需要先注册 FilteredWaveformsPlugin） |
| `sampling_rate` | `float` | `None` | - | 采样率（GHz）；未设置时默认使用 0.5 GHz |
| `rise_low` | `float` | `0.1` | - | 上升时间的低阈值比例（默认 10%） |
| `rise_high` | `float` | `0.9` | - | 上升时间的高阈值比例（默认 90%） |
| `fall_high` | `float` | `0.9` | - | 下降时间的高阈值比例（默认 90%） |
| `fall_low` | `float` | `0.1` | - | 下降时间的低阈值比例（默认 10%） |
| `interpolation` | `bool` | `True` | - | 是否使用线性插值提高时间计算精度 |


## Output Schema

**Output Type**: `structured_array`

| Field | Type | Units | Description |
|-------|------|-------|-------------|
| `rise_time` | `float32` | - | - |
| `fall_time` | `float32` | - | - |
| `total_width` | `float32` | - | - |
| `rise_time_samples` | `float32` | - | - |
| `fall_time_samples` | `float32` | - | - |
| `total_width_samples` | `float32` | - | - |
| `peak_position` | `int64` | - | - |
| `peak_height` | `float32` | - | - |
| `timestamp` | `int64` | - | - |
| `board` | `int16` | - | - |
| `channel` | `int16` | - | - |
| `record_id` | `int64` | - | - |

## Usage Example

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import WaveformWidthPlugin

# Create context and register plugin
ctx = Context(config={"data_root": "DAQ"})
ctx.register(WaveformWidthPlugin())

# Configure plugin (optional)
ctx.set_config({
    "use_filtered": False,
    "sampling_rate": None,
    "rise_low": 0.1,
}, plugin_name="waveform_width")

# Get data
data = ctx.get_data("run_001", "waveform_width")
```

## Module

- **Module Path**: `waveform_analysis.core.plugins.builtin.cpu.waveform_width`

---

*This documentation was auto-generated from plugin metadata.*
