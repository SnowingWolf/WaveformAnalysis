---
schema_version: 2
document_type: "plugin_reference"
profile: "agent"
provides: "s1_s2_pair_candidates"
plugin_class: "S1S2PairCandidatesPlugin"
module: "waveform_analysis.core.plugins.builtin.s1_s2_pair_candidates.plugin"
version: "0.1.3"
summary: "Generate all physically allowed S1-S2 pairing candidates"
depends_on: ["peak_classification", "peaks"]
declared_depends_on: ["peak_classification", "peaks"]
resolved_depends_on: ["peak_classification", "peaks"]
dependency_profile: "declared"
dependency_profile_values: {}
dependency_config_keys: []
output_kind: "structured_array"
execution_kind: "static"
narrative_source: "source"
narrative_source_reason: null
source_fingerprint: "ce140efec954613eb2fdb8766b6b6ace72c5c2ab2dba8a9dc1cd2115b0572305"
generated: true
---
# s1_s2_pair_candidates

## Overview

Generate all physically allowed S1-S2 pairing candidates
S1-S2 配对候选生成插件

生成所有物理允许的 S1-S2 配对候选对。采用 S2 为 anchor 的设计, 对每个 S2 向前搜索满足时间窗口约束的 S1 候选。

Hard constraints (物理必须满足): - t_S2 > t_S1 (时间因果性) - min_drift_time < (t_S2 - t_S1) < max_drift_time (漂移时间窗口) - 可选: S1/S2 最小面积阈值

不做的事: - 不判断哪个配对"更好" - 不强制唯一配对 - 不做复杂的能量比筛选 (只存储 log10_s2_s1)

输出: - 候选表,包含所有满足物理约束的 (S1, S2) 配对 - selected=False (由第二层插件设置) - score=0.0 (由第二层插件计算)

| Item | Value |
| --- | --- |
| Provides | `s1_s2_pair_candidates` |
| Plugin Class | `S1S2PairCandidatesPlugin` |
| Module | `waveform_analysis.core.plugins.builtin.s1_s2_pair_candidates.plugin` |
| Version | `0.1.3` |
| Category | 事件分析 |
| Output Container | `structured_array` |
| Execution Mode | `static` |
| Save Policy | `always` |
| Uses Run Config | no |
| Timeout | `none` |
| Side Effect | no |
| Narrative Source | `source` |
| Source Fingerprint | `ce140efec954613eb2fdb8766b6b6ace72c5c2ab2dba8a9dc1cd2115b0572305` |

### Dependencies

默认文档画像：`declared`。

| Dependency | Version Constraint | Resolution | Required Fields | Description |
| --- | --- | --- | --- | --- |
| `peak_classification` | - | declared | - | Classify peaks into S1/S2 using multi-dimensional features. |
| `peaks` | - | declared | - | Build final peaks table from peaklets and waveform-derived features. |
### How It Works

1. 生成 S1-S2 配对候选
2. 算法: 1. 分离 S1 和 S2 peaks 2. 预处理: 排序, 应用面积阈值 3. 主循环: 对每个 S2, 使用二分搜索找到候选 S1 范围 4. 提取 observables 5. 统计 ambiguity 信息 6. 可选: 处理孤立信号
3. 时间复杂度: O(M log N + K), K 是候选总数

## Configuration

| Name | Type | Default | Unit | Tracked | Deprecated | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `max_drift_time` | `float` | `50000.0` | - | yes | no | 最大漂移时间 (ns). 典型液氙 TPC 约 50 μs；范围：0.0 至 +∞ |
| `min_drift_time` | `float` | `0.0` | - | yes | no | 最小漂移时间 (ns). 用于过滤噪声；范围：0.0 至 +∞ |
| `time_field` | `str` | `center_time` | - | yes | no | 使用的时间字段；可选值：`center_time`, `time_start`, `time_peak` |
| `min_s1_area` | `(<class 'float'>, <class 'NoneType'>)` | `None` | - | yes | no | S1 最小面积阈值 (可选) |
| `min_s2_area` | `(<class 'float'>, <class 'NoneType'>)` | `None` | - | yes | no | S2 最小面积阈值 (可选) |
| `allow_orphan_s1` | `bool` | `False` | - | yes | no | 是否输出孤立 S1 (无 S2 配对) |
| `allow_orphan_s2` | `bool` | `False` | - | yes | no | 是否输出孤立 S2 (无 S1 配对) |
## Output

structured_array output with fields: pair_id, s1_peak_id, s2_peak_id, s1_index, s2_index, s1_time, s2_time, drift_time, ....

| Field | DType | Unit | Meaning |
| --- | --- | --- | --- |
| `pair_id` | `int64` | None | Unique candidate pair identifier |
| `s1_peak_id` | `int64` | None | S1 peak identifier |
| `s2_peak_id` | `int64` | None | S2 peak identifier (anchor) |
| `s1_index` | `int32` | None | S1 row index in the S1-only sub-array |
| `s2_index` | `int32` | None | S2 row index in the S2-only sub-array |
| `s1_time` | `int64` | ps | S1 timestamp |
| `s2_time` | `int64` | ps | S2 timestamp |
| `drift_time` | `int64` | ps | Drift time (S2 time minus S1 time) |
| `drift_time_ns` | `float32` | ns | Drift time in nanoseconds |
| `s1_area` | `float32` | ADC counts | S1 signal area |
| `s2_area` | `float32` | ADC counts | S2 signal area |
| `log10_s2_s1` | `float32` | None | log10 of S2/S1 area ratio |
| `s1_width` | `float32` | ns | S1 width |
| `s2_width` | `float32` | ns | S2 width |
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
result = ctx.get_data("run_001", "s1_s2_pair_candidates")
```

示例使用 `run_id="run_001"` 和文档默认运行画像；真实数据路径与配置应以当前实验设置为准。

## Operational Notes

### Behavior

- S1-S2 配对候选生成插件。
- 这个插件只负责“生成候选”，不负责“选择最终配对”。 它先把 `peak_classification` 的结果拆成 S1 和 S2，然后以 S2 为 anchor， 在漂移时间窗口内向前搜索所有物理上允许的 S1 候选。
### Failure Modes

- 任一声明依赖（`peak_classification`, `peaks`）缺失或字段不符合输入契约时，执行会失败。
- 配置校验或输出 schema 校验失败时，结果不会被视为有效插件产物。
### Downstream Impact

直接消费者：`s1_s2_pairs`
## Maintenance

### Change Playbook

1. 保持 `provides`、依赖和输出字段语义稳定，或同步所有下游消费者。
2. 行为、配置或输出契约改变时升级插件 `version`。
3. 修改插件源码后重新生成 Auto、Agent 和 HTML 参考。
### Validation

```bash
waveform-docs generate plugins-agent --plugin s1_s2_pair_candidates
waveform-docs check coverage --strict --fail-on-warning
```
