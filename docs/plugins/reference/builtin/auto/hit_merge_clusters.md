# HitMergeClustersPlugin

> Export cluster membership rows using the authoritative hit_merged configuration.

## Overview

| Property | Value |
|----------|-------|
| **Provides** | `hit_merge_clusters` |
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

This plugin has no configuration options.

## Output Schema

**Output Type**: `structured_array`

| Field | Type | Units | Description |
|-------|------|-------|-------------|
| `cluster_index` | `int64` | - | - |
| `hit_index` | `int64` | - | - |

## Usage Example

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import HitMergeClustersPlugin

# Create context and register plugin
ctx = Context(config={"data_root": "DAQ"})
ctx.register(HitMergeClustersPlugin())

# Get data
data = ctx.get_data("run_001", "hit_merge_clusters")
```

## Module

- **Module Path**: `waveform_analysis.core.plugins.builtin.hit.hit_merge`

---

*This documentation was auto-generated from plugin metadata.*
