---
schema_version: 1
document_type: "plugin_reference"
profile: "auto"
provides: "cache_analysis"
plugin_class: "CacheAnalysisPlugin"
module: "waveform_analysis.core.plugins.builtin.cpu.cache_analysis"
version: "0.1.0"
summary: "Analyze cache usage and return summary, entries, and diagnostics."
depends_on: []
output_kind: "dict"
generated: true
---
# cache_analysis

## Overview

Analyze cache usage and return summary, entries, and diagnostics.

| Item | Value |
| --- | --- |
| Provides | `cache_analysis` |
| Plugin Class | `CacheAnalysisPlugin` |
| Module | `waveform_analysis.core.plugins.builtin.cpu.cache_analysis` |
| Version | `0.1.0` |
| Category | 缓存分析 |
| Accelerator | CPU (NumPy/SciPy) |
| Output Kind | `dict` |

| Dependency | Version Constraint | Resolution | Required Fields | Description |
| --- | --- | --- | --- | --- |
| - | - | - | - | - |
## Configuration

| Name | Type | Default | Unit | Tracked | Deprecated | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `scan_all_runs` | `bool` | `False` | - | yes | no | Scan all runs instead of only the requested run_id. |
| `data_name` | `str` | `None` | - | yes | no | Optional data name filter for cache entries. |
| `min_size_bytes` | `int` | `None` | - | yes | no | Minimum cache entry size in bytes for filtering. |
| `max_size_bytes` | `int` | `None` | - | yes | no | Maximum cache entry size in bytes for filtering. |
| `min_age_days` | `float` | `None` | - | yes | no | Minimum cache entry age in days for filtering. |
| `max_age_days` | `float` | `None` | - | yes | no | Maximum cache entry age in days for filtering. |
| `compressed_only` | `bool` | `None` | - | yes | no | Filter entries by compression state (True/False). |
| `include_entries` | `bool` | `True` | - | yes | no | Include per-entry details in the result payload. |
| `max_entries` | `int` | `None` | - | yes | no | Limit the number of entries returned (largest by size). |
| `include_metadata` | `bool` | `False` | - | yes | no | Include full metadata dict for each cache entry. |
| `include_diagnostics` | `bool` | `False` | - | yes | no | Run cache diagnostics and include issue list. |
| `export_format` | `str` | `None` | - | yes | no | Export report to output_dir as 'json' or 'csv'. |
| `export_name` | `str` | `cache_analysis` | - | yes | no | Base filename for exported report. |
| `export_path` | `str` | `None` | - | yes | no | Explicit export path. Overrides export_name/output_dir. |
| `verbose` | `bool` | `False` | - | yes | no | Print scan and diagnostic progress. |
## Output

| Field | DType | Unit | Meaning |
| --- | --- | --- | --- |
| - | `dict` | - | Analyze cache usage and return summary, entries, and diagnostics. |
## Usage

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import CacheAnalysisPlugin

ctx = Context(config={"data_root": "DAQ"})
ctx.register(CacheAnalysisPlugin())
data = ctx.get_data("run_001", "cache_analysis")
```
