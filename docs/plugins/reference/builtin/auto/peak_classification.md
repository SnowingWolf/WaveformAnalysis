# PeakClassificationPlugin

> Classify peaks into S1/S2 using multi-dimensional features.

## Overview

| Property | Value |
|----------|-------|
| **Provides** | `peak_classification` |
| **Version** | `1.2.1` |
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
| `priority_order` | `list` | `['s1_s2', 's1', 's2']` | - | 分类优先级顺序（列表），从高到低。例如: ['s1_s2', 's1', 's2'] 表示先判定 s1_s2，再判定 s1，最后判定 s2。可用值: 's1', 's2', 's1_s2' |
| `default_label` | `str` | `unknown` | - | 当不满足任何配置条件时的默认标签。默认 'unknown'（推荐用于灵活分类）。 |
| `strict` | `bool` | `False` | - | 如果为 True，至少需要配置一个 S1 或 S2 的判断条件。 |
| `s1_selection` | `dict` | `None` | - | S1 分类配置。字典包含：- 'accept_any': 列表，每个元素是一个条件组（字典），满足任一组即为 S1 候选- 'reject_any': 列表，每个元素是一个条件组（字典），满足任一组即排除示例: {'accept_any': [{'width': (0, 100)}, {'area': (0, 500)}], 'reject_any': [{'width': (500, None)}]} |
| `s2_selection` | `dict` | `None` | - | S2 分类配置，格式同 s1_selection。 |
| `s1_s2_selection` | `dict` | `None` | - | S1_S2 分类配置，格式同 s1_selection。命中后优先标记为 S1_S2。 |


## Output Schema

**Output Type**: `structured_array`

| Field | Type | Units | Description |
|-------|------|-------|-------------|
| `peak_id` | `int64` | - | - |
| `label` | `int8` | - | - |

## Usage Example

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import PeakClassificationPlugin

# Create context and register plugin
ctx = Context(config={"data_root": "DAQ"})
ctx.register(PeakClassificationPlugin())

# Configure plugin (optional)
ctx.set_config({
    "priority_order": ['s1_s2', 's1', 's2'],
    "default_label": 'unknown',
    "strict": False,
}, plugin_name="peak_classification")

# Get data
data = ctx.get_data("run_001", "peak_classification")
```

## Module

- **Module Path**: `waveform_analysis.core.plugins.builtin.cpu.peak_classification`

---

*This documentation was auto-generated from plugin metadata.*
