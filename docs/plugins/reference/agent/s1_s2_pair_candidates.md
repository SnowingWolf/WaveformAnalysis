---
schema_version: 1
document_type: "plugin_reference"
profile: "agent"
provides: "s1_s2_pair_candidates"
plugin_class: "S1S2PairCandidatesPlugin"
module: "waveform_analysis.core.plugins.builtin.cpu.s1_s2_pair_candidates"
version: "0.1.3"
summary: "Generate all physically allowed S1-S2 pairing candidates"
depends_on: ["peak_classification", "peaks"]
output_kind: "structured_array"
generated: true
---
# s1_s2_pair_candidates

## Overview

Generate all physically allowed S1-S2 pairing candidates
| Item | Value |
| --- | --- |
| Provides | `s1_s2_pair_candidates` |
| Plugin Class | `S1S2PairCandidatesPlugin` |
| Module | `waveform_analysis.core.plugins.builtin.cpu.s1_s2_pair_candidates` |
| Version | `0.1.3` |
| Category | 事件分析 |
| Accelerator | CPU (NumPy/SciPy) |
| Output Kind | `structured_array` |

| Dependency | Version Constraint | Resolution | Required Fields | Description |
| --- | --- | --- | --- | --- |
| `peak_classification` | - | declared | - | Classify peaks into S1/S2 using multi-dimensional features. |
| `peaks` | - | declared | - | Build final peaks table from peaklets and waveform-derived features. |
### How It Works


## Configuration

| Name | Type | Default | Unit | Tracked | Deprecated | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `max_drift_time` | `float` | `50000.0` | - | yes | no | 最大漂移时间 (ns). 典型液氙 TPC 约 50 μs |
| `min_drift_time` | `float` | `0.0` | - | yes | no | 最小漂移时间 (ns). 用于过滤噪声 |
| `time_field` | `str` | `center_time` | - | yes | no | 使用的时间字段 |
| `min_s1_area` | `(<class 'float'>, <class 'NoneType'>)` | `None` | - | yes | no | S1 最小面积阈值 (可选) |
| `min_s2_area` | `(<class 'float'>, <class 'NoneType'>)` | `None` | - | yes | no | S2 最小面积阈值 (可选) |
| `allow_orphan_s1` | `bool` | `False` | - | yes | no | 是否输出孤立 S1 (无 S2 配对) |
| `allow_orphan_s2` | `bool` | `False` | - | yes | no | 是否输出孤立 S2 (无 S1 配对) |
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
from waveform_analysis.core.plugins.builtin.cpu import S1S2PairCandidatesPlugin

ctx = Context(config={"data_root": "DAQ"})
ctx.register(S1S2PairCandidatesPlugin())
data = ctx.get_data("run_001", "s1_s2_pair_candidates")
```

## Operational Notes

### Behavior

- 生成 S1-S2 配对候选
- 算法: 1. 分离 S1 和 S2 peaks 2. 预处理: 排序, 应用面积阈值 3. 主循环: 对每个 S2, 使用二分搜索找到候选 S1 范围 4. 提取 observables 5. 统计 ambiguity 信息 6. 可选: 处理孤立信号
- 时间复杂度: O(M log N + K), K 是候选总数
### Failure Modes

- Dependency data, configuration, or output contract validation may fail explicitly.
### Downstream Impact

Consumers: `s1_s2_pairs`

## Maintenance

### Change Playbook

1. Keep `provides` and dependency semantics stable or update all consumers.
2. Bump `version` for behavior, configuration, or output contract changes.
3. Regenerate auto, agent, and web references after metadata changes.
### Validation

```bash
waveform-docs generate plugins-agent --plugin s1_s2_pair_candidates
waveform-docs check coverage --strict --fail-on-warning
```
