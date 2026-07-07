# S1S2PairCandidatesPlugin

> Generate all physically allowed S1-S2 pairing candidates

## Overview

| Property | Value |
|----------|-------|
| **Provides** | `s1_s2_pair_candidates` |
| **Version** | `0.1.2` |
| **Category** | 事件分析 |
| **Accelerator** | CPU (NumPy/SciPy) |
| **Streaming** | No |
| **Side Effect** | No |

## Dependencies

This plugin depends on the following data:

- [`peak_classification`](peak_classification.md)
- [`peaks`](peaks.md)

## Configuration Options

| Option | Type | Default | Units | Description |
|--------|------|---------|-------|-------------|
| `max_drift_time` | `float` | `50000.0` | - | 最大漂移时间 (ns). 典型液氙 TPC 约 50 μs |
| `min_drift_time` | `float` | `0.0` | - | 最小漂移时间 (ns). 用于过滤噪声 |
| `time_field` | `str` | `center_time` | - | 使用的时间字段 |
| `min_s1_area` | `(<class 'float'>, <class 'NoneType'>)` | `None` | - | S1 最小面积阈值 (可选) |
| `min_s2_area` | `(<class 'float'>, <class 'NoneType'>)` | `None` | - | S2 最小面积阈值 (可选) |
| `allow_orphan_s1` | `bool` | `False` | - | 是否输出孤立 S1 (无 S2 配对) |
| `allow_orphan_s2` | `bool` | `False` | - | 是否输出孤立 S2 (无 S1 配对) |


## Output Schema

**Output Type**: `structured_array`

| Field | Type | Units | Description |
|-------|------|-------|-------------|
| `pair_id` | `int64` | - | - |
| `s1_peak_id` | `int64` | - | - |
| `s2_peak_id` | `int64` | - | - |
| `s1_index` | `int32` | - | - |
| `s2_index` | `int32` | - | - |
| `s1_time` | `int64` | - | - |
| `s2_time` | `int64` | - | - |
| `drift_time` | `int64` | - | - |
| `drift_time_ns` | `float32` | - | - |
| `s1_area` | `float32` | - | - |
| `s2_area` | `float32` | - | - |
| `log10_s2_s1` | `float32` | - | - |
| `s1_width` | `float32` | - | - |
| `s2_width` | `float32` | - | - |
| `s1_n_channels` | `int16` | - | - |
| `s2_n_channels` | `int16` | - | - |
| `score_total` | `float32` | - | - |
| `score_time` | `float32` | - | - |
| `score_s1_quality` | `float32` | - | - |
| `score_s2_quality` | `float32` | - | - |
| `score_ratio` | `float32` | - | - |
| `score_pattern` | `float32` | - | - |
| `score_ambiguity` | `float32` | - | - |
| `rank_for_s1` | `int32` | - | - |
| `rank_for_s2` | `int32` | - | - |
| `n_s1_candidates_for_s2` | `int32` | - | - |
| `n_s2_candidates_for_s1` | `int32` | - | - |
| `delta_score_to_next_best` | `float32` | - | - |
| `flags` | `uint32` | - | - |
| `selected` | `bool` | - | - |

## Usage Example

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import S1S2PairCandidatesPlugin

# Create context and register plugin
ctx = Context(config={"data_root": "DAQ"})
ctx.register(S1S2PairCandidatesPlugin())

# Configure plugin (optional)
ctx.set_config({
    "max_drift_time": 50000.0,
    "min_drift_time": 0.0,
    "time_field": 'center_time',
}, plugin_name="s1_s2_pair_candidates")

# Get data
data = ctx.get_data("run_001", "s1_s2_pair_candidates")
```

## Module

- **Module Path**: `waveform_analysis.core.plugins.builtin.cpu.s1_s2_pair_candidates`

---

*This documentation was auto-generated from plugin metadata.*
