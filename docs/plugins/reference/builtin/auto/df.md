# DataFramePlugin

> Plugin to build the initial single-channel events DataFrame.

## Overview

| Property | Value |
|----------|-------|
| **Provides** | `df` |
| **Version** | `1.3.0` |
| **Category** | 数据导出 |
| **Accelerator** | CPU (NumPy/SciPy) |
| **Streaming** | No |
| **Side Effect** | No |

## Dependencies

This plugin depends on the following data:

- [`st_waveforms`](st_waveforms.md)
- [`basic_features`](basic_features.md)

## Configuration Options

| Option | Type | Default | Units | Description |
|--------|------|---------|-------|-------------|
| `gain_adc_per_pe` | `dict` | `None` | - | 按通道配置 ADC/PE 增益，如 {0: 12.5, 1: 13.2}。显式设置优先；未显式设置时可从 `<run_path>/run_config.json` 的 `calibration.gain_adc_per_pe` 读取。 |


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
