---
schema_version: 1
document_type: "plugin_reference"
profile: "agent"
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
| `peaks` | - | declared | - | - |
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

| Field | DType | Unit | Meaning |
| --- | --- | --- | --- |
| `peak_id` | `int64` | - | - |
| `label` | `int8` | - | - |
## Usage

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import PeakClassificationPlugin

ctx = Context(config={"data_root": "DAQ"})
ctx.register(PeakClassificationPlugin())
data = ctx.get_data("run_001", "peak_classification")
```

## Operational Notes

### Behavior

- 从 peaklet 特征进行 S1/S2 分类。

该插件基于 peaks 的多维特征进行信号类型甄别。

默认分类规则（基于 n_hits 和 rise_time_10_50）：
┌─────────────┬──────────────────┬──────────┬────────────────────────────────┐
│ n_hits      │ rise_time_10_50  │ 分类结果 │ 说明                           │
├─────────────┼──────────────────┼──────────┼────────────────────────────────┤
│ < 8         │ 任意             │ S1       │ 少量 hits（单通道或少量通道）  │
│ >= 8        │ <= 100 ns        │ S1       │ 多 hits 但快速上升（类 S1）    │
│ >= 8        │ > 100 ns         │ S2       │ 多 hits 且慢速上升（典型 S2）  │
└─────────────┴──────────────────┴──────────┴────────────────────────────────┘

物理意义：
- n_hits < 8: 信号集中在少量通道，典型的 S1 直接闪烁特征
- n_hits >= 8 且 rise_time_10_50 <= 100 ns: 多通道但快速上升，可能是强 S1
- n_hits >= 8 且 rise_time_10_50 > 100 ns: 多通道且慢速上升，典型 S2 电子漂移信号

分类标签：
- 0: Unknown（未知类型）
- 1: S1（闪烁信号）
- 2: S2（电离信号）
- 3: S1_S2（混合信号或分类冲突）
### Failure Modes

- Dependency data, configuration, or output contract validation may fail explicitly.
### Downstream Impact

-
## Maintenance

### Change Playbook

1. Keep `provides` and dependency semantics stable or update all consumers.
2. Bump `version` for behavior, configuration, or output contract changes.
3. Regenerate auto, agent, and web references after metadata changes.
### Validation

```bash
waveform-docs generate plugins-agent --plugin peak_classification
waveform-docs check coverage --strict --fail-on-warning
```
