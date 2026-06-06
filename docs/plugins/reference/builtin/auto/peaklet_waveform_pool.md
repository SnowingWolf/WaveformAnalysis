# PeakletWaveformPoolPlugin

> Return flattened float32 peaklet waveform signal pool.

## Overview

| Property | Value |
|----------|-------|
| **Provides** | `peaklet_waveform_pool` |
| **Version** | `1.0.0` |
| **Category** | 波形处理 |
| **Accelerator** | CPU (NumPy/SciPy) |
| **Streaming** | No |
| **Side Effect** | No |

## Dependencies

This plugin depends on the following data:

- [`peaklets`](peaklets.md)
- [`peaklet_components`](peaklet_components.md)
- [`hit_merged`](hit_merged.md)
- [`records`](records.md)
- [`wave_pool`](wave_pool.md)

## Configuration Options

| Option | Type | Default | Units | Description |
|--------|------|---------|-------|-------------|
| `use_filtered` | `bool` | `False` | - | 是否使用 wave_pool_filtered 构建 peaklet 波形 |


## Output Schema

**Output Type**: `array`

| Field | Type | Units | Description |
|-------|------|-------|-------------|
| `value` | `float32` | - | - |

## Usage Example

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import PeakletWaveformPoolPlugin

# Create context and register plugin
ctx = Context(config={"data_root": "DAQ"})
ctx.register(PeakletWaveformPoolPlugin())

# Configure plugin (optional)
ctx.set_config({
    "use_filtered": False,
}, plugin_name="peaklet_waveform_pool")

# Get data
data = ctx.get_data("run_001", "peaklet_waveform_pool")
```

## Module

- **Module Path**: `waveform_analysis.core.plugins.builtin.cpu.peaklets`

---

*This documentation was auto-generated from plugin metadata.*
