# HitMergedComponentsPlugin

> Return per-cluster component hit indices for hit_merged rows.

## Overview

| Property | Value |
|----------|-------|
| **Provides** | `hit_merged_components` |
| **Version** | `1.1.0` |
| **Category** | 特征提取 |
| **Accelerator** | CPU (NumPy/SciPy) |
| **Streaming** | No |
| **Side Effect** | No |

## Dependencies

This plugin depends on the following data:

- [`hit_merged`](hit_merged.md)
- [`hit_threshold`](hit_threshold.md)

## Configuration Options

| Option | Type | Default | Units | Description |
|--------|------|---------|-------|-------------|
| `validate_components` | `bool` | `False` | - | 校验 hit_merged 的 component_offset/component_count 与 cluster rows 是否一致。 |


## Output Schema

**Output Type**: `structured_array`

| Field | Type | Units | Description |
|-------|------|-------|-------------|
| `merged_index` | `int64` | - | - |
| `hit_index` | `int64` | - | - |

## Usage Example

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import HitMergedComponentsPlugin

# Create context and register plugin
ctx = Context(config={"data_root": "DAQ"})
ctx.register(HitMergedComponentsPlugin())

# Configure plugin (optional)
ctx.set_config({
    "validate_components": False,
}, plugin_name="hit_merged_components")

# Get data
data = ctx.get_data("run_001", "hit_merged_components")
```

## Module

- **Module Path**: `waveform_analysis.core.plugins.builtin.hit.hit_merge`

---

*This documentation was auto-generated from plugin metadata.*
