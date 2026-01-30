# GroupedEventsPlugin

> Plugin to group events by time window.

## Overview

| Property | Value |
|----------|-------|
| **Provides** | `df_events` |
| **Version** | `0.0.0` |
| **Category** | 事件分析 |
| **Accelerator** | CPU (NumPy/SciPy) |
| **Streaming** | No |
| **Side Effect** | No |

## Dependencies

This plugin depends on the following data:

- [`df`](df.md)

## Configuration Options

| Option | Type | Default | Units | Description |
|--------|------|---------|-------|-------------|
| `time_window_ns` | `float` | `100.0` | - | - |



## Usage Example

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import GroupedEventsPlugin

# Create context and register plugin
ctx = Context(config={"data_root": "DAQ"})
ctx.register(GroupedEventsPlugin())

# Configure plugin (optional)
ctx.set_config({
    "time_window_ns": 100.0,
}, plugin_name="df_events")

# Get data
data = ctx.get_data("run_001", "df_events")
```

## Module

- **Module Path**: `waveform_analysis.core.plugins.builtin.cpu.event_analysis`

---

*This documentation was auto-generated from plugin metadata.*