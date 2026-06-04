# RecordsAsymmetryMaskPlugin

> Bool mask for waveform asymmetry selection.

## Overview

| Property | Value |
|----------|-------|
| **Provides** | `records_asymmetry_mask` |
| **Version** | `0.1.0` |
| **Category** | 记录处理 |
| **Accelerator** | CPU (NumPy/SciPy) |
| **Streaming** | No |
| **Side Effect** | No |

## Dependencies

This plugin depends on the following data:

- [`records`](records.md)
- [`wave_pool`](wave_pool.md)

## Configuration Options

| Option | Type | Default | Units | Description |
|--------|------|---------|-------|-------------|
| `asymmetry_cut_min` | `float` | `0.7` | - | Keep records with asymmetry >= this value. |
| `asymmetry_parallel` | `bool` | `True` | - | Use Numba prange parallel loop. |
| `asymmetry_chunk_size` | `int` | `200000` | - | Number of records processed per Numba call. |
| `asymmetry_num_threads` | `int` | `0` | - | Numba thread count. <=0 keeps current Numba default. |


## Output Schema

**Output Type**: `array`

| Field | Type | Units | Description |
|-------|------|-------|-------------|
| `value` | `bool` | - | - |

## Usage Example

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import RecordsAsymmetryMaskPlugin

# Create context and register plugin
ctx = Context(config={"data_root": "DAQ"})
ctx.register(RecordsAsymmetryMaskPlugin())

# Configure plugin (optional)
ctx.set_config({
    "asymmetry_cut_min": 0.7,
    "asymmetry_parallel": True,
    "asymmetry_chunk_size": 200000,
}, plugin_name="records_asymmetry_mask")

# Get data
data = ctx.get_data("run_001", "records_asymmetry_mask")
```

## Module

- **Module Path**: `waveform_analysis.core.plugins.builtin.cpu.records_asymmetry`

---

*This documentation was auto-generated from plugin metadata.*
