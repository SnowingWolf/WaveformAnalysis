# EventFramePlugin

> Build an events DataFrame from the events bundle.

## Overview

| Property | Value |
|----------|-------|
| **Provides** | `events_df` |
| **Version** | `0.5.0` |
| **Category** | 事件分析 |
| **Accelerator** | CPU (NumPy/SciPy) |
| **Streaming** | No |
| **Side Effect** | No |

## Dependencies

This plugin depends on the following data:

- [`events`](events.md)

## Configuration Options

| Option | Type | Default | Units | Description |
|--------|------|---------|-------|-------------|
| `peaks_range` | `tuple` | `(40, 90)` | - | Peak range in samples (start, end); end=None uses full length. |
| `charge_range` | `tuple` | `(0, None)` | - | Charge range in samples (start, end); end=None uses full length. |
| `include_event_id` | `bool` | `True` | - | Include event_id column in events_df output. |
| `fixed_baseline` | `dict` | `None` | - | 按通道固定 baseline 值，如 {0: 8192, 1: 8200}。设置后覆盖动态 baseline 用于 height/area 计算。 |
| `gain_adc_per_pe` | `dict` | `None` | - | 按通道配置 ADC/PE 增益，如 {0: 12.5, 1: 13.2}。显式设置优先；未显式设置时可从 `<run_path>/run_config.json` 的 `calibration.gain_adc_per_pe` 读取。 |



## Usage Example

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import EventFramePlugin

# Create context and register plugin
ctx = Context(config={"data_root": "DAQ"})
ctx.register(EventFramePlugin())

# Configure plugin (optional)
ctx.set_config({
    "peaks_range": (40, 90),
    "charge_range": (0, None),
    "include_event_id": True,
}, plugin_name="events_df")

# Get data
data = ctx.get_data("run_001", "events_df")
```

## Module

- **Module Path**: `waveform_analysis.core.plugins.builtin.cpu.events`

---

*This documentation was auto-generated from plugin metadata.*
