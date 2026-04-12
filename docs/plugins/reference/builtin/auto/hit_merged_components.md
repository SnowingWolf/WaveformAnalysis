# HitMergedComponentsPlugin

> Return per-cluster component hit indices for hit_merged rows.

## Overview

| Property | Value |
|----------|-------|
| **Provides** | `hit_merged_components` |
| **Version** | `0.1.0` |
| **Category** | 特征提取 |
| **Accelerator** | CPU (NumPy/SciPy) |
| **Streaming** | No |
| **Side Effect** | No |

## Dependencies

This plugin depends on the following data:

- [`hit_merge_clusters`](hit_merge_clusters.md)
- [`hit_merged`](hit_merged.md)

## Configuration Options

This plugin has no configuration options.

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

# Get data
data = ctx.get_data("run_001", "hit_merged_components")
```

## Module

- **Module Path**: `waveform_analysis.core.plugins.builtin.cpu.hit_merge`

---

*This documentation was auto-generated from plugin metadata.*
