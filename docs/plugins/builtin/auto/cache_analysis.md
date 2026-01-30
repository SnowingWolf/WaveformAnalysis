# CacheAnalysisPlugin

> Analyze cache usage and return summary, entries, and diagnostics.

## Overview

| Property | Value |
|----------|-------|
| **Provides** | `cache_analysis` |
| **Version** | `0.1.0` |
| **Category** | 缓存分析 |
| **Accelerator** | CPU (NumPy/SciPy) |
| **Streaming** | No |
| **Side Effect** | Yes |

## Dependencies

This plugin has no dependencies.

## Configuration Options

| Option | Type | Default | Units | Description |
|--------|------|---------|-------|-------------|
| `scan_all_runs` | `bool` | `False` | - | Scan all runs instead of only the requested run_id. |
| `data_name` | `str` | `None` | - | Optional data name filter for cache entries. |
| `min_size_bytes` | `int` | `None` | - | Minimum cache entry size in bytes for filtering. |
| `max_size_bytes` | `int` | `None` | - | Maximum cache entry size in bytes for filtering. |
| `min_age_days` | `float` | `None` | - | Minimum cache entry age in days for filtering. |
| `max_age_days` | `float` | `None` | - | Maximum cache entry age in days for filtering. |
| `compressed_only` | `bool` | `None` | - | Filter entries by compression state (True/False). |
| `include_entries` | `bool` | `True` | - | Include per-entry details in the result payload. |
| `max_entries` | `int` | `None` | - | Limit the number of entries returned (largest by size). |
| `include_metadata` | `bool` | `False` | - | Include full metadata dict for each cache entry. |
| `include_diagnostics` | `bool` | `False` | - | Run cache diagnostics and include issue list. |
| `export_format` | `str` | `None` | - | Export report to output_dir as 'json' or 'csv'. |
| `export_name` | `str` | `cache_analysis` | - | Base filename for exported report. |
| `export_path` | `str` | `None` | - | Explicit export path. Overrides export_name/output_dir. |
| `verbose` | `bool` | `False` | - | Print scan and diagnostic progress. |



## Usage Example

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import CacheAnalysisPlugin

# Create context and register plugin
ctx = Context(config={"data_root": "DAQ"})
ctx.register(CacheAnalysisPlugin())

# Configure plugin (optional)
ctx.set_config({
    "scan_all_runs": False,
    "data_name": None,
    "min_size_bytes": None,
}, plugin_name="cache_analysis")

# Get data
data = ctx.get_data("run_001", "cache_analysis")
```

## Module

- **Module Path**: `waveform_analysis.core.plugins.builtin.cpu.cache_analysis`

---

*This documentation was auto-generated from plugin metadata.*