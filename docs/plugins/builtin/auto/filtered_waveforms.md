# FilteredWaveformsPlugin

> Apply filtering to waveforms using Butterworth or Savitzky-Golay filters.

## Overview

| Property | Value |
|----------|-------|
| **Provides** | `filtered_waveforms` |
| **Version** | `1.0.2` |
| **Category** | 波形处理 |
| **Accelerator** | CPU (NumPy/SciPy) |
| **Streaming** | No |
| **Side Effect** | No |

## Dependencies

This plugin depends on the following data:

- [`st_waveforms`](st_waveforms.md)

## Configuration Options

| Option | Type | Default | Units | Description |
|--------|------|---------|-------|-------------|
| `filter_type` | `str` | `SG` | - | 滤波器类型: 'BW' 或 'SG' |
| `lowcut` | `float` | `0.1` | - | BW 低频截止 |
| `highcut` | `float` | `0.5` | - | BW 高频截止 |
| `fs` | `float` | `0.5` | - | BW 采样率（GHz） |
| `filter_order` | `int` | `4` | - | BW 阶数 |
| `sg_window_size` | `int` | `11` | - | SG 窗口大小（奇数） |
| `sg_poly_order` | `int` | `2` | - | SG 多项式阶数 |
| `daq_adapter` | `str` | `None` | - | DAQ 适配器名称（用于自动推断采样率） |


## Output Schema

**Output Type**: `structured_array`

| Field | Type | Units | Description |
|-------|------|-------|-------------|
| `wave` | `('<f4', (0,))` | - | - |

## Usage Example

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import FilteredWaveformsPlugin

# Create context and register plugin
ctx = Context(config={"data_root": "DAQ"})
ctx.register(FilteredWaveformsPlugin())

# Configure plugin (optional)
ctx.set_config({
    "filter_type": 'SG',
    "lowcut": 0.1,
    "highcut": 0.5,
}, plugin_name="filtered_waveforms")

# Get data
data = ctx.get_data("run_001", "filtered_waveforms")
```

## Module

- **Module Path**: `waveform_analysis.core.plugins.builtin.cpu.filtering`

---

*This documentation was auto-generated from plugin metadata.*