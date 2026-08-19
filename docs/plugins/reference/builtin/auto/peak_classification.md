---
schema_version: 1
document_type: "plugin_reference"
profile: "auto"
provides: "peak_classification"
plugin_class: "PeakClassificationPlugin"
module: "waveform_analysis.core.plugins.builtin.peak_classification.plugin"
version: "1.2.1"
summary: "Classify peaks into S1/S2 using multi-dimensional features."
depends_on: ["peaks"]
output_kind: "structured_array"
generated: true
---
# peak_classification

## Overview

Classify peaks into S1/S2 using multi-dimensional features.
基于 peaks 特征进行 S1/S2 分类。

| Item | Value |
| --- | --- |
| Provides | `peak_classification` |
| Plugin Class | `PeakClassificationPlugin` |
| Module | `waveform_analysis.core.plugins.builtin.peak_classification.plugin` |
| Version | `1.2.1` |
| Category | 特征提取 |
| Output Kind | `structured_array` |

| Dependency | Version Constraint | Resolution | Required Fields | Description |
| --- | --- | --- | --- | --- |
| `peaks` | - | declared | - | Build final peaks table from peaklets and waveform-derived features. |
### How It Works


## Configuration

| Name | Type | Default | Unit | Tracked | Deprecated | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `priority_order` | `list` | `['s1_s2', 's1', 's2']` | - | yes | no | 分类优先级顺序（列表，从高到低）。按顺序检查每个标签，返回第一个满足条件的类型。可用值: 's1', 's2', 's1_s2'。示例: ['s1_s2', 's1', 's2'] 先判定 s1_s2，再 s1，最后 s2；['s1', 's2', 's1_s2'] 则 S1 优先。 |
| `default_label` | `str` | `unknown` | - | yes | no | 当不满足任何配置条件时的默认标签。可选值: 'unknown', 's1', 's2'。默认 'unknown'（推荐，避免误判）。 |
| `strict` | `bool` | `False` | - | yes | no | 为 True 时，至少需要配置一个 s1_selection / s2_selection / s1_s2_selection，否则抛出 RuntimeError。 |
| `s1_selection` | `dict` | `None` | - | yes | no | S1 分类配置字典。accept_any: 条件组列表，满足任一组即候选（组间 OR）；reject_any: 条件组列表，满足任一组即排除；条件组内字段条件为 AND。可用字段: width, area, height, rise_time, fall_time, rise_time_10_50, width_25_75, range_90p_area, n_hits, n_channels。示例: {'accept_any': [{'width': (0, 100)}, {'area': (0, 500)}], 'reject_any': [{'width': (500, None)}]} |
| `s2_selection` | `dict` | `None` | - | yes | no | S2 分类配置，格式同 s1_selection。 |
| `s1_s2_selection` | `dict` | `None` | - | yes | no | S1_S2 分类配置，格式同 s1_selection。命中后优先标记为 S1_S2。 |
## Output

structured_array output with fields: peak_id, label.

| Field | DType | Unit | Meaning |
| --- | --- | --- | --- |
| `peak_id` | `int64` | None | Zero-based index of the input peaks row receiving this classification |
| `label` | `int8` | None | Classification code: 0=unknown, 1=S1, 2=S2, 3=S1_S2 |
## Usage

### Minimal Example

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.peak_classification import PeakClassificationPlugin

ctx = Context(config={"data_root": "DAQ"})
ctx.register(PeakClassificationPlugin())
data = ctx.get_data("run_001", "peak_classification")
```
### Downstream Consumers

- `s1_s2_pair_candidates`
