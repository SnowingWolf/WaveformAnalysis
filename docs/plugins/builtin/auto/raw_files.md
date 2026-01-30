# RawFileNamesPlugin

> Scan the data directory and group raw CSV files by channel number.

## Overview

| Property | Value |
|----------|-------|
| **Provides** | `raw_files` |
| **Version** | `0.0.2` |
| **Category** | 数据加载 |
| **Accelerator** | CPU (NumPy/SciPy) |
| **Streaming** | No |
| **Side Effect** | No |

## Dependencies

This plugin has no dependencies.

## Configuration Options

| Option | Type | Default | Units | Description |
|--------|------|---------|-------|-------------|
| `data_root` | `str` | `DAQ` | - | Root directory for data |
| `daq_adapter` | `str` | `vx2730` | - | DAQ adapter name (e.g., 'vx2730') |



## Usage Example

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import RawFileNamesPlugin

# Create context and register plugin
ctx = Context(config={"data_root": "DAQ"})
ctx.register(RawFileNamesPlugin())

# Configure plugin (optional)
ctx.set_config({
    "data_root": 'DAQ',
    "daq_adapter": 'vx2730',
}, plugin_name="raw_files")

# Get data
data = ctx.get_data("run_001", "raw_files")
```

## Module

- **Module Path**: `waveform_analysis.core.plugins.builtin.cpu.waveforms`

---

*This documentation was auto-generated from plugin metadata.*