# HitGroupedPlugin

> Group merged hits across channels into event-level coincidence windows.

## Overview

| Property | Value |
|----------|-------|
| **Provides** | `hit_grouped` |
| **Version** | `0.3.0` |
| **Category** | 特征提取 |
| **Accelerator** | CPU (NumPy/SciPy) |
| **Streaming** | No |
| **Side Effect** | No |

## Dependencies

This plugin depends on the following data:

- [`hit_merged`](hit_merged.md)

## Configuration Options

| Option | Type | Default | Units | Description |
|--------|------|---------|-------|-------------|
| `time_window_ns` | `float` | `100.0` | - | - |
| `dt` | `int` | `None` | - | 采样间隔（ns）。仅在输入 hit_merged 缺少 dt 字段时作为兼容补充。 |



## Usage Example

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import HitGroupedPlugin

# Create context and register plugin
ctx = Context(config={"data_root": "DAQ"})
ctx.register(HitGroupedPlugin())

# Configure plugin (optional)
ctx.set_config({
    "time_window_ns": 100.0,
    "dt": None,
}, plugin_name="hit_grouped")

# Get data
data = ctx.get_data("run_001", "hit_grouped")
```

## Module

- **Module Path**: `waveform_analysis.core.plugins.builtin.cpu.event_analysis`

---

*This documentation was auto-generated from plugin metadata.*
