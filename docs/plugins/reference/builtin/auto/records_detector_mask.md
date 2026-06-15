# RecordsDetectorMaskPlugin

> Bool mask for detector-channel records after channel-role splitting.

## Overview

| Property | Value |
|----------|-------|
| **Provides** | `records_detector_mask` |
| **Version** | `0.1.0` |
| **Category** | 记录处理 |
| **Accelerator** | CPU (NumPy/SciPy) |
| **Streaming** | No |
| **Side Effect** | No |

## Dependencies

This plugin depends on the following data:

- [`records`](records.md)
- [`records_asymmetry_mask`](records_asymmetry_mask.md)

## Configuration Options

| Option | Type | Default | Units | Description |
|--------|------|---------|-------|-------------|
| `channel_config` | `dict` | `None` | - | 按 (board, channel) 的通道角色配置；role='detector' 进入正常 hit，role='veto' 仅作为 veto 通道保留。 |


## Output Schema

**Output Type**: `array`

| Field | Type | Units | Description |
|-------|------|-------|-------------|
| `value` | `bool` | - | - |

## Usage Example

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import RecordsDetectorMaskPlugin

# Create context and register plugin
ctx = Context(config={"data_root": "DAQ"})
ctx.register(RecordsDetectorMaskPlugin())

# Configure plugin (optional)
ctx.set_config({
    "channel_config": None,
}, plugin_name="records_detector_mask")

# Get data
data = ctx.get_data("run_001", "records_detector_mask")
```

## Module

- **Module Path**: `waveform_analysis.core.plugins.builtin.cpu.records_channel_role`

---

*This documentation was auto-generated from plugin metadata.*
