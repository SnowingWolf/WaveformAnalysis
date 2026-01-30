# WaveformWidthPlugin

> Calculate rise/fall time based on peak detection results.

## Overview

| Property | Value |
|----------|-------|
| **Provides** | `waveform_width` |
| **Version** | `1.0.1` |
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
| `sampling_rate` | `float` | `None` | - | 采样率（GHz），未显式设置时优先从 DAQ 适配器推断 |
| `daq_adapter` | `str` | `None` | - | DAQ 适配器名称（用于自动推断采样率） |
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
| `channel` | `int16` | - | - |
| `event_index` | `int64` | - | - |

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
    "daq_adapter": None,
}, plugin_name="waveform_width")

# Get data
data = ctx.get_data("run_001", "waveform_width")
```

## Module

- **Module Path**: `waveform_analysis.core.plugins.builtin.cpu.waveform_width`

---

*This documentation was auto-generated from plugin metadata.*