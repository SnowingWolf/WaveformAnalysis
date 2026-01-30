# EventsPlugin

> Provide event index data backed by the records bundle.

## Overview

| Property | Value |
|----------|-------|
| **Provides** | `events` |
| **Version** | `0.1.0` |
| **Category** | 事件分析 |
| **Accelerator** | CPU (NumPy/SciPy) |
| **Streaming** | No |
| **Side Effect** | No |

## Dependencies

This plugin has no dependencies.

## Configuration Options

| Option | Type | Default | Units | Description |
|--------|------|---------|-------|-------------|
| `events_part_size` | `int` | `200000` | - | Max events per shard in the records bundle; <=0 disables sharding. |
| `events_dt_ns` | `int` | `None` | - | Sample interval in ns (defaults to adapter rate or 1ns). |


## Output Schema

**Output Type**: `structured_array`

| Field | Type | Units | Description |
|-------|------|-------|-------------|
| `timestamp` | `int64` | - | - |
| `pid` | `int32` | - | - |
| `channel` | `int16` | - | - |
| `baseline` | `float64` | - | - |
| `baseline_upstream` | `float64` | - | - |
| `event_id` | `int64` | - | - |
| `dt` | `int32` | - | - |
| `trigger_type` | `int16` | - | - |
| `flags` | `uint32` | - | - |
| `wave_offset` | `int64` | - | - |
| `event_length` | `int32` | - | - |
| `time` | `int64` | - | - |

## Usage Example

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import EventsPlugin

# Create context and register plugin
ctx = Context(config={"data_root": "DAQ"})
ctx.register(EventsPlugin())

# Configure plugin (optional)
ctx.set_config({
    "events_part_size": 200000,
    "events_dt_ns": None,
}, plugin_name="events")

# Get data
data = ctx.get_data("run_001", "events")
```

## Module

- **Module Path**: `waveform_analysis.core.plugins.builtin.cpu.events`

---

*This documentation was auto-generated from plugin metadata.*
