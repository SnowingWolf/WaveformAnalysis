# S1S2PairSelectionPlugin

> Select best S1-S2 pairs from candidates

## Overview

| Property | Value |
|----------|-------|
| **Provides** | `s1_s2_pairs` |
| **Version** | `0.2.0` |
| **Category** | 事件分析 |
| **Accelerator** | CPU (NumPy/SciPy) |
| **Streaming** | No |
| **Side Effect** | No |

## Dependencies

This plugin depends on the following data:

- [`s1_s2_pair_candidates`](s1_s2_pair_candidates.md)

## Configuration Options

| Option | Type | Default | Units | Description |
|--------|------|---------|-------|-------------|
| `selection_mode` | `str` | `largest` | - | 选择策略: largest (最大S1), nearest (最近), best_score (综合), all (全部) |
| `close_competitor_threshold` | `float` | `0.1` | - | 次优候选接近阈值。delta_score < threshold 时标记 FLAG_CLOSE_COMPETITOR |
| `require_s2_larger_than_s1` | `bool` | `True` | - | 是否要求 S2_area > S1_area。这是液氙探测器的物理约束。 |


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
from waveform_analysis.core.plugins.builtin.cpu import S1S2PairSelectionPlugin

# Create context and register plugin
ctx = Context(config={"data_root": "DAQ"})
ctx.register(S1S2PairSelectionPlugin())

# Configure plugin (optional)
ctx.set_config({
    "selection_mode": 'largest',
    "close_competitor_threshold": 0.1,
    "require_s2_larger_than_s1": True,
}, plugin_name="s1_s2_pairs")

# Get data
data = ctx.get_data("run_001", "s1_s2_pairs")
```

## Module

- **Module Path**: `waveform_analysis.core.plugins.builtin.cpu.s1_s2_pair_selection`

---

*This documentation was auto-generated from plugin metadata.*
