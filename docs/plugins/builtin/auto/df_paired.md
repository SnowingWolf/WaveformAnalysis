# PairedEventsPlugin

> Plugin to pair events across channels.

## Overview

| Property | Value |
|----------|-------|
| **Provides** | `df_paired` |
| **Version** | `0.0.0` |
| **Category** | 事件分析 |
| **Accelerator** | CPU (NumPy/SciPy) |
| **Streaming** | No |
| **Side Effect** | No |

## Dependencies

This plugin depends on the following data:

- [`df_events`](df_events.md)

## Configuration Options

This plugin has no configuration options.


## Usage Example

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import PairedEventsPlugin

# Create context and register plugin
ctx = Context(config={"data_root": "DAQ"})
ctx.register(PairedEventsPlugin())

# Get data
data = ctx.get_data("run_001", "df_paired")
```

## Module

- **Module Path**: `waveform_analysis.core.plugins.builtin.cpu.event_analysis`

---

*This documentation was auto-generated from plugin metadata.*