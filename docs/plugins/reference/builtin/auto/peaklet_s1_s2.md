# PeakletS1S2ClassifierPlugin

> Classify peaks into S1/S2 using multi-dimensional features.

## Overview

| Property | Value |
|----------|-------|
| **Provides** | `peaklet_s1_s2` |
| **Version** | `1.0.0` |
| **Category** | 特征提取 |
| **Accelerator** | CPU (NumPy/SciPy) |
| **Streaming** | No |
| **Side Effect** | No |

## Dependencies

This plugin depends on the following data:

- [`peaks`](peaks.md)

## Configuration Options

| Option | Type | Default | Units | Description |
|--------|------|---------|-------|-------------|
| `s1_ranges` | `dict` | `None` | - | S1 特征范围字典。键为特征名，值为 (min, max) 元组。例如: {'width': (0, 100), 'area': (0, 500), 'n_hits': (1, 10)}。默认 None 时，使用默认分类规则：凡不满足 S2 条件的都判为 S1。 |
| `s2_ranges` | `dict` | `{'n_hits': (8, None), 'rise_time_10_50': (100.01, None)}` | - | S2 特征范围字典。键为特征名，值为 (min, max) 元组。例如: {'width': (300, None), 'area': (1000, None), 'n_hits': (8, None)}。默认: {'n_hits': (8, None), 'rise_time_10_50': (100.01, None)} - 即 n_hits >= 8 且 rise_time_10_50 > 100 ns 判定为 S2。None 表示不配置 S2 判断条件。 |
| `conflict_policy` | `str` | `prefer_s1` | - | 当同时满足 S1 和 S2 条件时的处理策略。默认 prefer_s1。 |
| `default_label` | `str` | `s1` | - | 当不满足任何配置条件时的默认标签。默认 's1' - 即凡不满足 S2 条件的都判为 S1（适用于默认配置）。 |
| `strict` | `bool` | `False` | - | 如果为 True，至少需要配置一个 S1 或 S2 的判断条件。 |


## Output Schema

**Output Type**: `structured_array`

| Field | Type | Units | Description |
|-------|------|-------|-------------|
| `peak_id` | `int64` | - | - |
| `label` | `int8` | - | - |

## Usage Example

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import PeakletS1S2ClassifierPlugin

# Create context and register plugin
ctx = Context(config={"data_root": "DAQ"})
ctx.register(PeakletS1S2ClassifierPlugin())

# Configure plugin (optional)
ctx.set_config({
    "s1_ranges": None,
    "s2_ranges": {'n_hits': (8, None), 'rise_time_10_50': (100.01, None)},
    "conflict_policy": 'prefer_s1',
}, plugin_name="peaklet_s1_s2")

# Get data
data = ctx.get_data("run_001", "peaklet_s1_s2")
```

## Module

- **Module Path**: `waveform_analysis.core.plugins.builtin.cpu.peaklet_s1_s2_classifier`

---

*This documentation was auto-generated from plugin metadata.*
