---
schema_version: 1
document_type: "plugin_reference"
profile: "auto"
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
| `pair_id` | `int64` | - | Unique candidate pair identifier |
| `s1_peak_id` | `int64` | - | S1 peak identifier |
| `s2_peak_id` | `int64` | - | S2 peak identifier (anchor) |
| `s1_index` | `int32` | - | S1 row index in the S1-only sub-array |
| `s2_index` | `int32` | - | S2 row index in the S2-only sub-array |
| `s1_time` | `int64` | - | S1 timestamp in picoseconds |
| `s2_time` | `int64` | - | S2 timestamp in picoseconds |
| `drift_time` | `int64` | - | Drift time (S2 time minus S1 time) in picoseconds |
| `drift_time_ns` | `float32` | - | Drift time in nanoseconds |
| `s1_area` | `float32` | - | S1 signal area |
| `s2_area` | `float32` | - | S2 signal area |
| `log10_s2_s1` | `float32` | - | log10 of S2/S1 area ratio |
| `s1_width` | `float32` | - | S1 width (ns) |
| `s2_width` | `float32` | - | S2 width (ns) |
| `s1_n_channels` | `int16` | - | Number of channels for S1 |
| `s2_n_channels` | `int16` | - | Number of channels for S2 |
| `score_total` | `float32` | - | Total pairing score |
| `score_time` | `float32` | - | Time-matching score |
| `score_s1_quality` | `float32` | - | S1 quality score |
| `score_s2_quality` | `float32` | - | S2 quality score |
| `score_ratio` | `float32` | - | S2/S1 ratio score |
| `score_pattern` | `float32` | - | Pattern-matching score (reserved) |
| `score_ambiguity` | `float32` | - | Ambiguity penalty (reserved) |
| `rank_for_s1` | `int32` | - | Rank of this S2 among all S1 candidates (1-based) |
| `rank_for_s2` | `int32` | - | Rank of this S1 among all S2 candidates (1-based) |
| `n_s1_candidates_for_s2` | `int32` | - | Number of S1 candidates competing for this S2 |
| `n_s2_candidates_for_s1` | `int32` | - | Number of S2 candidates competing for this S1 |
| `delta_score_to_next_best` | `float32` | - | Score difference to next-best candidate |
| `flags` | `uint32` | - | Bit-field status flags |
| `selected` | `bool` | - | Whether this pair was selected as final pairing |
## Usage

### Minimal Example

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import S1S2PairCandidatesPlugin

ctx = Context(config={"data_root": "DAQ"})
ctx.register(S1S2PairCandidatesPlugin())
data = ctx.get_data("run_001", "s1_s2_pair_candidates")
```
### Downstream Consumers

- `s1_s2_pairs`
