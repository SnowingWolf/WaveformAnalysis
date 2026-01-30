# DataFramePlugin

> Plugin to build the initial single-channel events DataFrame.

## Overview

| Property | Value |
|----------|-------|
| **Provides** | `df` |
| **Version** | `0.0.0` |
| **Category** | 数据导出 |
| **Accelerator** | CPU (NumPy/SciPy) |
| **Streaming** | No |
| **Side Effect** | No |

## Dependencies

This plugin depends on the following data:

- [`st_waveforms`](st_waveforms.md)
- [`basic_features`](basic_features.md)

## Configuration Options

This plugin has no configuration options.


## Usage Example

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import DataFramePlugin

# Create context and register plugin
ctx = Context(config={"data_root": "DAQ"})
ctx.register(DataFramePlugin())

# Get data
data = ctx.get_data("run_001", "df")
```

## Module

- **Module Path**: `waveform_analysis.core.plugins.builtin.cpu.dataframe`

---

*This documentation was auto-generated from plugin metadata.*