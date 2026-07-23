---
schema_version: 1
document_type: "plugin_reference"
profile: "agent"
provides: "s1_s2_pairs"
plugin_class: "S1S2PairSelectionPlugin"
module: "waveform_analysis.core.plugins.builtin.cpu.s1_s2_pair_selection"
version: "0.2.0"
summary: "Select best S1-S2 pairs from candidates"
depends_on: ["s1_s2_pair_candidates"]
output_kind: "structured_array"
generated: true
---
# s1_s2_pairs

## Overview

Select best S1-S2 pairs from candidates
| Item | Value |
| --- | --- |
| Provides | `s1_s2_pairs` |
| Plugin Class | `S1S2PairSelectionPlugin` |
| Module | `waveform_analysis.core.plugins.builtin.cpu.s1_s2_pair_selection` |
| Version | `0.2.0` |
| Category | 事件分析 |
| Accelerator | CPU (NumPy/SciPy) |
| Output Kind | `structured_array` |

| Dependency | Version Constraint | Resolution | Required Fields | Description |
| --- | --- | --- | --- | --- |
| `s1_s2_pair_candidates` | - | declared | - | Generate all physically allowed S1-S2 pairing candidates |
### How It Works


## Configuration

| Name | Type | Default | Unit | Tracked | Deprecated | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `selection_mode` | `str` | `largest` | - | yes | no | 选择策略: largest (最大S1), nearest (最近), best_score (综合), all (全部) |
| `close_competitor_threshold` | `float` | `0.1` | - | yes | no | 次优候选接近阈值。delta_score < threshold 时标记 FLAG_CLOSE_COMPETITOR |
| `require_s2_larger_than_s1` | `bool` | `True` | - | yes | no | 是否要求 S2_area > S1_area。这是液氙探测器的物理约束。 |
## Output

structured_array output with fields: pair_id, s1_peak_id, s2_peak_id, s1_index, s2_index, s1_time, s2_time, drift_time, ....

| Field | DType | Unit | Meaning |
| --- | --- | --- | --- |
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
## Usage

### Minimal Example

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import S1S2PairSelectionPlugin

ctx = Context(config={"data_root": "DAQ"})
ctx.register(S1S2PairSelectionPlugin())
data = ctx.get_data("run_001", "s1_s2_pairs")
```

## Operational Notes

### Behavior

- 选择最佳配对
- 算法: 1. 获取候选 2. 过滤不满足物理约束的候选 (S1_area < S2_area) 3. 计算 score (根据 selection_mode) 4. 为每个 S2 选择最优 S1 5. 设置 selected flag 6. 计算 delta_score_to_next_best 7. 计算 rank_for_s2 8. 标记 CLOSE_COMPETITOR
### Failure Modes

- Dependency data, configuration, or output contract validation may fail explicitly.
### Downstream Impact

Consumers: `events`, `position_reconstruction`

## Maintenance

### Change Playbook

1. Keep `provides` and dependency semantics stable or update all consumers.
2. Bump `version` for behavior, configuration, or output contract changes.
3. Regenerate auto, agent, and web references after metadata changes.
### Validation

```bash
waveform-docs generate plugins-agent --plugin s1_s2_pairs
waveform-docs check coverage --strict --fail-on-warning
```
