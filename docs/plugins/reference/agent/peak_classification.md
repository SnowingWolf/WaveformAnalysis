---
schema_version: 2
document_type: "plugin_reference"
profile: "agent"
provides: "peak_classification"
plugin_class: "PeakClassificationPlugin"
module: "waveform_analysis.core.plugins.builtin.peak_classification.plugin"
version: "1.2.1"
summary: "Classify peaks into S1/S2 using multi-dimensional features."
depends_on: ["peaks"]
declared_depends_on: ["peaks"]
resolved_depends_on: ["peaks"]
dependency_profile: "declared"
dependency_profile_values: {}
dependency_config_keys: []
output_kind: "structured_array"
execution_kind: "static"
narrative_source: "source"
narrative_source_reason: null
source_fingerprint: "162076343ab8ea37f03d6cfb6f149c52a5bb6b99ac6ea6649735d9be066543b4"
generated: true
---
# peak_classification

## Overview

Classify peaks into S1/S2 using multi-dimensional features.
基于 peaks 特征进行 S1/S2 分类。

该插件使用 peaks 的多维特征（宽度、面积、高度、上升时间、下降时间、n_hits、n_channels 等） 进行信号类型甄别。通过字典配置各类型的特征范围。

可用的特征字段： - width: 宽度 (ns) - area: 面积 - height: 高度 - rise_time: 上升时间 (ns)，从 10% 到峰值 - fall_time: 下降时间 (ns)，50%-90% 面积分位数 - rise_time_10_50: 上升时间 (ns)，从 10% 到 50% - width_25_75: 宽度 (ns)，25%-75% - range_90p_area: 90% 面积范围 (ns) - n_hits: hits 数量 - n_channels: 通道数量

| Item | Value |
| --- | --- |
| Provides | `peak_classification` |
| Plugin Class | `PeakClassificationPlugin` |
| Module | `waveform_analysis.core.plugins.builtin.peak_classification.plugin` |
| Version | `1.2.1` |
| Category | 特征提取 |
| Output Container | `structured_array` |
| Execution Mode | `static` |
| Save Policy | `always` |
| Uses Run Config | no |
| Timeout | `none` |
| Side Effect | no |
| Narrative Source | `source` |
| Source Fingerprint | `162076343ab8ea37f03d6cfb6f149c52a5bb6b99ac6ea6649735d9be066543b4` |

### Dependencies

默认文档画像：`declared`。

| Dependency | Version Constraint | Resolution | Required Fields | Description |
| --- | --- | --- | --- | --- |
| `peaks` | - | declared | - | Build final peaks table from peaklets and waveform-derived features. |
### How It Works

1. 基于 peaks 特征进行 S1/S2 分类。
2. 该插件使用 peaks 的多维特征（宽度、面积、高度、上升时间、下降时间、n_hits、n_channels 等） 进行信号类型甄别。通过字典配置各类型的特征范围。
3. 可用的特征字段： - width: 宽度 (ns) - area: 面积 - height: 高度 - rise_time: 上升时间 (ns)，从 10% 到峰值 - fall_time: 下降时间 (ns)，50%-90% 面积分位数 - rise_time_10_50: 上升时间 (ns)，从 10% 到 50% - width_25_75: 宽度 (ns)，25%-75% - range_90p_area: 90% 面积范围 (ns) - n_hits: hits 数量 - n_channels: 通道数量

## Configuration

| Name | Type | Default | Unit | Tracked | Deprecated | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `priority_order` | `list` | `['s1_s2', 's1', 's2']` | - | yes | no | 分类优先级顺序（列表，从高到低）。按顺序检查每个标签，返回第一个满足条件的类型。可用值: 's1', 's2', 's1_s2'。示例: ['s1_s2', 's1', 's2'] 先判定 s1_s2，再 s1，最后 s2；['s1', 's2', 's1_s2'] 则 S1 优先。 |
| `default_label` | `str` | `unknown` | - | yes | no | 当不满足任何配置条件时的默认标签。可选值: 'unknown', 's1', 's2'。默认 'unknown'（推荐，避免误判）。；可选值：`unknown`, `s1`, `s2` |
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
from waveform_analysis.core.plugins.builtin.cpu import PeakClassificationPlugin

run_id = "run_001"
ctx = Context(config={"data_root": "DAQ"})
ctx.register(PeakClassificationPlugin())

# 条件组内部使用 AND；accept_any/reject_any 的多个条件组使用 OR。
ctx.set_config(
    {
        "s1_selection": {
            "accept_any": [
                {"width": (0.0, 100.0), "n_hits": (1, 7)},
            ],
        },
        "s2_selection": {
            "accept_any": [
                {"width": (300.0, None), "n_hits": (8, None)},
                {"rise_time_10_50": (100.0, None)},
            ],
        },
        "s1_s2_selection": {
            "accept_any": [
                {"width": (100.0, 200.0), "area": (400.0, 600.0)},
            ],
        },
        "priority_order": ["s1_s2", "s1", "s2"],
        "default_label": "unknown",
    },
    plugin_name="peak_classification",
)
labels = ctx.get_data(run_id, "peak_classification")
```

示例使用 `run_id="run_001"` 和文档默认运行画像；真实数据路径与配置应以当前实验设置为准。

## Operational Notes

### Behavior

- 基于 peaks 表特征（width、area、height、rise_time、n_hits、n_channels 等）把每条 peak 标记为 Unknown(0)、S1(1)、S2(2) 或 S1_S2(3)。
- 判定按 priority_order 顺序执行：为每个标签计算 selection 掩码，返回第一个满足条件的标签；都不满足时返回 default_label。
- accept_any 组间为 OR，组内字段条件为 AND；reject_any 命中即排除。
- s1_s2_selection 命中时优先标记为 S1_S2，再考虑普通 S1/S2 规则。
### Failure Modes

- 任一声明依赖（`peaks`）缺失或字段不符合输入契约时，执行会失败。
- 配置校验或输出 schema 校验失败时，结果不会被视为有效插件产物。
### Downstream Impact

直接消费者：`s1_s2_pair_candidates`
## Maintenance

### Change Playbook

1. 保持 `provides`、依赖和输出字段语义稳定，或同步所有下游消费者。
2. 行为、配置或输出契约改变时升级插件 `version`。
3. 修改插件源码后重新生成 Auto、Agent 和 HTML 参考。
### Validation

```bash
waveform-docs generate plugins-agent --plugin peak_classification
waveform-docs check coverage --strict --fail-on-warning
```
