# DataFramePlugin

> Build the initial single-channel events DataFrame.

## Overview

| Property | Value |
|----------|-------|
| **Provides** | `df` |
| **Version** | `1.6.0` |
| **Category** | 数据导出 |
| **Accelerator** | CPU (NumPy/SciPy) |
| **Streaming** | No |
| **Side Effect** | No |

## Dependencies

This plugin has no dependencies.

## Configuration Options

| Option | Type | Default | Units | Description |
|--------|------|---------|-------|-------------|
| `use_filtered` | `bool` | `False` | - | 是否使用 filtered_waveforms（需要先注册 FilteredWaveformsPlugin） |
| `wave_source` | `str` | `auto` | - | 波形数据源: auto|records|st_waveforms|filtered_waveforms |
| `gain_adc_per_pe` | `dict` | `None` | - | 按硬件通道配置 ADC/PE 增益，键请使用 "board:channel"，例如 {"0:0": 12.5, "0:1": 13.2}。设置后会新增 area_pe/height_pe 列。 |



## Usage Example

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import DataFramePlugin

# Create context and register plugin
ctx = Context(config={"data_root": "DAQ"})
ctx.register(DataFramePlugin())

# Configure plugin (optional)
ctx.set_config({
    "use_filtered": False,
    "wave_source": 'auto',
    "gain_adc_per_pe": None,
}, plugin_name="df")

# Get data
data = ctx.get_data("run_001", "df")
```

## Module

- **Module Path**: `waveform_analysis.core.plugins.builtin.cpu.dataframe`

---

*This documentation was auto-generated from plugin metadata.*
