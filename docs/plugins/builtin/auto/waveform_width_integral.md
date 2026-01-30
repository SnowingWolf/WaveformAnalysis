# WaveformWidthIntegralPlugin

> Event-wise integral quantile width using st_waveforms baseline.

## Overview

| Property | Value |
|----------|-------|
| **Provides** | `waveform_width_integral` |
| **Version** | `1.1.0` |
| **Category** | 波形处理 |
| **Accelerator** | CPU (NumPy/SciPy) |
| **Streaming** | No |
| **Side Effect** | No |

## Dependencies

This plugin has no dependencies.

## Configuration Options

| Option | Type | Default | Units | Description |
|--------|------|---------|-------|-------------|
| `q_low` | `float` | `0.1` | - | 低分位点（默认 0.10） |
| `q_high` | `float` | `0.9` | - | 高分位点（默认 0.90） |
| `polarity` | `str` | `auto` | - | 信号极性: auto | positive | negative |
| `use_filtered` | `bool` | `False` | - | 是否使用 filtered_waveforms（若启用，baseline 仍来自 st_waveforms） |
| `sampling_rate` | `float` | `0.5` | - | 采样率（GHz），用于换算时间（ns） |
| `dt` | `float` | `None` | - | 采样间隔（ns），优先级高于 sampling_rate |
| `daq_adapter` | `str` | `None` | - | DAQ 适配器名称（用于自动推断采样率） |


## Output Schema

**Output Type**: `structured_array`

| Field | Type | Units | Description |
|-------|------|-------|-------------|
| `t_low` | `float32` | - | - |
| `t_high` | `float32` | - | - |
| `width` | `float32` | - | - |
| `t_low_samples` | `float32` | - | - |
| `t_high_samples` | `float32` | - | - |
| `width_samples` | `float32` | - | - |
| `q_total` | `float64` | - | - |
| `timestamp` | `int64` | - | - |
| `channel` | `int16` | - | - |
| `event_index` | `int64` | - | - |

## Usage Example

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import WaveformWidthIntegralPlugin

# Create context and register plugin
ctx = Context(config={"data_root": "DAQ"})
ctx.register(WaveformWidthIntegralPlugin())

# Configure plugin (optional)
ctx.set_config({
    "q_low": 0.1,
    "q_high": 0.9,
    "polarity": 'auto',
}, plugin_name="waveform_width_integral")

# Get data
data = ctx.get_data("run_001", "waveform_width_integral")
```

## Module

- **Module Path**: `waveform_analysis.core.plugins.builtin.cpu.waveform_width_integral`

---

*This documentation was auto-generated from plugin metadata.*