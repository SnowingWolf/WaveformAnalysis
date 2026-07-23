---
schema_version: 1
document_type: "plugin_reference"
profile: "auto"
provides: "peak_classification"
plugin_class: "PeakClassificationPlugin"
module: "waveform_analysis.core.plugins.builtin.cpu.peak_classification"
version: "1.2.1"
summary: "Classify peaks into S1/S2 using multi-dimensional features."
depends_on: ["peaks"]
output_kind: "structured_array"
generated: true
---
# peak_classification

## Overview

Classify peaks into S1/S2 using multi-dimensional features.
| Item | Value |
| --- | --- |
| Provides | `peak_classification` |
| Plugin Class | `PeakClassificationPlugin` |
| Module | `waveform_analysis.core.plugins.builtin.cpu.peak_classification` |
| Version | `1.2.1` |
| Category | 特征提取 |
| Accelerator | CPU (NumPy/SciPy) |
| Output Kind | `structured_array` |

| Dependency | Version Constraint | Resolution | Required Fields | Description |
| --- | --- | --- | --- | --- |
| `peaks` | - | declared | - | Build final peaks table from peaklets and waveform-derived features. |
### How It Works


## Configuration

| Name | Type | Default | Unit | Tracked | Deprecated | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `priority_order` | `list` | `['s1_s2', 's1', 's2']` | - | yes | no | 分类优先级顺序（列表），从高到低。例如: ['s1_s2', 's1', 's2'] 表示先判定 s1_s2，再判定 s1，最后判定 s2。可用值: 's1', 's2', 's1_s2' |
| `default_label` | `str` | `unknown` | - | yes | no | 当不满足任何配置条件时的默认标签。默认 'unknown'（推荐用于灵活分类）。 |
| `strict` | `bool` | `False` | - | yes | no | 如果为 True，至少需要配置一个 S1 或 S2 的判断条件。 |
| `s1_selection` | `dict` | `None` | - | yes | no | S1 分类配置。字典包含：- 'accept_any': 列表，每个元素是一个条件组（字典），满足任一组即为 S1 候选- 'reject_any': 列表，每个元素是一个条件组（字典），满足任一组即排除示例: {'accept_any': [{'width': (0, 100)}, {'area': (0, 500)}], 'reject_any': [{'width': (500, None)}]} |
| `s2_selection` | `dict` | `None` | - | yes | no | S2 分类配置，格式同 s1_selection。 |
| `s1_s2_selection` | `dict` | `None` | - | yes | no | S1_S2 分类配置，格式同 s1_selection。命中后优先标记为 S1_S2。 |
## Output

structured_array output with fields: peak_id, label.

| Field | DType | Unit | Meaning |
| --- | --- | --- | --- |
| `peak_id` | `int64` | - | Zero-based index of the input peaks row receiving this classification |
| `label` | `int8` | - | Classification code: 0=unknown, 1=S1, 2=S2, 3=S1_S2 |
## Usage

### Minimal Example

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import PeakClassificationPlugin

ctx = Context(config={"data_root": "DAQ"})
ctx.register(PeakClassificationPlugin())
data = ctx.get_data("run_001", "peak_classification")
```
### Downstream Consumers

- `s1_s2_pair_candidates`
