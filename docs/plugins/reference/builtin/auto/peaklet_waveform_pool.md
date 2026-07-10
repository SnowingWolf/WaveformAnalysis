# PeakletWaveformPoolPlugin

> Return the flattened float32 signal pool paired with peaklet_waveforms. Configure waveform construction on peaklet_waveforms.

## Overview

| Property | Value |
|----------|-------|
| **Provides** | `peaklet_waveform_pool` |
| **Version** | `2.0.0` |
| **Category** | 波形处理 |
| **Accelerator** | CPU (NumPy/SciPy) |
| **Streaming** | No |
| **Side Effect** | No |

## Dependencies

This plugin depends on the following data:

- [`peaklet_waveforms`](peaklet_waveforms.md)

## Configuration Options

This plugin has no configuration options.

## Output Schema

**Output Type**: `array`

| Field | Type | Units | Description |
|-------|------|-------|-------------|
| `value` | `float32` | - | - |

## Usage Example

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.plugin_sets import (
    plugins_hit,
    plugins_io,
    plugins_waveform,
)

ctx = Context(config={"data_root": "DAQ"})
ctx.register(*plugins_io(), *plugins_waveform(), *plugins_hit())

# Construction options belong to the canonical waveform producer.
ctx.set_config(
    {"use_filtered": False, "clip_negative_signal": False},
    plugin_name="peaklet_waveforms",
)
pool = ctx.get_data("run_001", "peaklet_waveform_pool")
```

## Module

- **Module Path**: `waveform_analysis.core.plugins.builtin.peaks.peaklets`

---

*This documentation was auto-generated from plugin metadata.*
