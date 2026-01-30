# EventsGroupedPlugin

> Group events_df into multi-channel events by time window.

## Overview

| Property | Value |
|----------|-------|
| **Provides** | `events_grouped` |
| **Version** | `0.1.0` |
| **Category** | 事件分析 |
| **Accelerator** | CPU (NumPy/SciPy) |
| **Streaming** | No |
| **Side Effect** | No |

## Dependencies

This plugin depends on the following data:

- [`events_df`](events_df.md)

## Configuration Options

| Option | Type | Default | Units | Description |
|--------|------|---------|-------|-------------|
| `time_window_ns` | `float` | `100.0` | - | Grouping window in ns (converted to ps internally). |
| `use_numba` | `bool` | `True` | - | Use numba-accelerated boundary search when available. |
| `n_processes` | `int` | `None` | - | Worker processes for grouping; None or <=1 disables it. |



## Usage Example

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import EventsGroupedPlugin

# Create context and register plugin
ctx = Context(config={"data_root": "DAQ"})
ctx.register(EventsGroupedPlugin())

# Configure plugin (optional)
ctx.set_config({
    "time_window_ns": 100.0,
    "use_numba": True,
    "n_processes": None,
}, plugin_name="events_grouped")

# Get data
data = ctx.get_data("run_001", "events_grouped")
```

## Module

- **Module Path**: `waveform_analysis.core.plugins.builtin.cpu.events`

---

*This documentation was auto-generated from plugin metadata.*