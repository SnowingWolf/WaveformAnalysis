---
schema_version: 2
document_type: "plugin_reference"
profile: "agent"
provides: "s1_s2_pairs"
plugin_class: "S1S2PairSelectionPlugin"
module: "waveform_analysis.core.plugins.builtin.s1_s2_pairs.plugin"
version: "0.2.0"
summary: "Select best S1-S2 pairs from candidates"
depends_on: ["s1_s2_pair_candidates"]
declared_depends_on: ["s1_s2_pair_candidates"]
resolved_depends_on: ["s1_s2_pair_candidates"]
dependency_profile: "declared"
dependency_profile_values: {}
dependency_config_keys: []
output_kind: "structured_array"
execution_kind: "static"
narrative_source: "source"
narrative_source_reason: null
source_fingerprint: "c0d8c444d1d3c15e9c74f53cf7f368da414f6a77d62a307e98d813f6ce2aca22"
generated: true
---
# s1_s2_pairs

## Overview

Select best S1-S2 pairs from candidates
S1-S2 配对选择插件

对候选进行打分并选择最佳配对。为每个 S2 选择最优的 S1。

选择模式: - largest: 选择面积最大的 S1 (v0.1 实现) - nearest: 选择时间最近的 S1 (预留) - best_score: 综合打分 (预留) - all: 不做选择,保留所有候选 (预留)

输出: - 修改 candidates 的 selected flag - 填充 score 字段 - 计算 delta_score_to_next_best - 计算 rank_for_s2

| Item | Value |
| --- | --- |
| Provides | `s1_s2_pairs` |
| Plugin Class | `S1S2PairSelectionPlugin` |
| Module | `waveform_analysis.core.plugins.builtin.s1_s2_pairs.plugin` |
| Version | `0.2.0` |
| Category | 事件分析 |
| Output Container | `structured_array` |
| Execution Mode | `static` |
| Save Policy | `always` |
| Uses Run Config | no |
| Timeout | `none` |
| Side Effect | no |
| Narrative Source | `source` |
| Source Fingerprint | `c0d8c444d1d3c15e9c74f53cf7f368da414f6a77d62a307e98d813f6ce2aca22` |

### Dependencies

默认文档画像：`declared`。

| Dependency | Version Constraint | Resolution | Required Fields | Description |
| --- | --- | --- | --- | --- |
| `s1_s2_pair_candidates` | - | declared | - | Generate all physically allowed S1-S2 pairing candidates |
### How It Works

1. 选择最佳配对
2. 算法: 1. 获取候选 2. 过滤不满足物理约束的候选 (S1_area < S2_area) 3. 计算 score (根据 selection_mode) 4. 为每个 S2 选择最优 S1 5. 设置 selected flag 6. 计算 delta_score_to_next_best 7. 计算 rank_for_s2 8. 标记 CLOSE_COMPETITOR

## Configuration

| Name | Type | Default | Unit | Tracked | Deprecated | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `selection_mode` | `str` | `largest` | - | yes | no | 选择策略: largest (最大S1), nearest (最近), best_score (综合), all (全部)；可选值：`largest`, `nearest`, `best_score`, `all` |
| `close_competitor_threshold` | `float` | `0.1` | - | yes | no | 次优候选接近阈值。delta_score < threshold 时标记 FLAG_CLOSE_COMPETITOR；范围：0.0 至 +∞ |
| `require_s2_larger_than_s1` | `bool` | `True` | - | yes | no | 是否要求 S2_area > S1_area。这是液氙探测器的物理约束。 |
## Output

structured_array output with fields: pair_id, s1_peak_id, s2_peak_id, s1_index, s2_index, s1_time, s2_time, drift_time, ....

| Field | DType | Unit | Meaning |
| --- | --- | --- | --- |
| `pair_id` | `int64` | None | Unique candidate pair identifier |
| `s1_peak_id` | `int64` | None | S1 peak identifier |
| `s2_peak_id` | `int64` | None | S2 peak identifier (anchor) |
| `s1_index` | `int32` | None | S1 row index in the S1-only sub-array |
| `s2_index` | `int32` | None | S2 row index in the S2-only sub-array |
| `s1_time` | `int64` | ps | S1 timestamp in picoseconds |
| `s2_time` | `int64` | ps | S2 timestamp in picoseconds |
| `drift_time` | `int64` | ps | Drift time (S2 time minus S1 time) in picoseconds |
| `drift_time_ns` | `float32` | ns | Drift time in nanoseconds |
| `s1_area` | `float32` | ADC counts | S1 signal area |
| `s2_area` | `float32` | ADC counts | S2 signal area |
| `log10_s2_s1` | `float32` | None | log10 of S2/S1 area ratio |
| `s1_width` | `float32` | ns | S1 width (ns) |
| `s2_width` | `float32` | ns | S2 width (ns) |
| `s1_n_channels` | `int16` | None | Number of channels for S1 |
| `s2_n_channels` | `int16` | None | Number of channels for S2 |
| `score_total` | `float32` | None | Total pairing score |
| `score_time` | `float32` | None | Time-matching score |
| `score_s1_quality` | `float32` | None | S1 quality score |
| `score_s2_quality` | `float32` | None | S2 quality score |
| `score_ratio` | `float32` | None | S2/S1 ratio score |
| `score_pattern` | `float32` | None | Pattern-matching score (reserved) |
| `score_ambiguity` | `float32` | None | Ambiguity penalty (reserved) |
| `rank_for_s1` | `int32` | None | Rank of this S2 among all S1 candidates (1-based) |
| `rank_for_s2` | `int32` | None | Rank of this S1 among all S2 candidates (1-based) |
| `n_s1_candidates_for_s2` | `int32` | None | Number of S1 candidates competing for this S2 |
| `n_s2_candidates_for_s1` | `int32` | None | Number of S2 candidates competing for this S1 |
| `delta_score_to_next_best` | `float32` | None | Score difference to next-best candidate |
| `flags` | `uint32` | None | Bit-field status flags |
| `selected` | `bool` | None | Whether this pair was selected as final pairing |
## Usage

### Minimal Example

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins import profiles

ctx = Context(config={"data_root": "DAQ", "daq_adapter": "vx2730"})
ctx.register(*profiles.cpu_default())
result = ctx.get_data("run_001", "s1_s2_pairs")
```

示例使用 `run_id="run_001"` 和文档默认运行画像；真实数据路径与配置应以当前实验设置为准。

## Operational Notes

### Behavior

- S1-S2 配对选择插件
- 此插件对候选进行打分并选择最佳配对。 第一版实现 largest 模式,其他模式预留接口。
### Failure Modes

- 任一声明依赖（`s1_s2_pair_candidates`）缺失或字段不符合输入契约时，执行会失败。
- 配置校验或输出 schema 校验失败时，结果不会被视为有效插件产物。
### Downstream Impact

直接消费者：`energy_reconstruction`、`events`、`position_reconstruction`
## Maintenance

### Change Playbook

1. 保持 `provides`、依赖和输出字段语义稳定，或同步所有下游消费者。
2. 行为、配置或输出契约改变时升级插件 `version`。
3. 修改插件源码后重新生成 Auto、Agent 和 HTML 参考。
### Validation

```bash
waveform-docs generate plugins-agent --plugin s1_s2_pairs
waveform-docs check coverage --strict --fail-on-warning
```
