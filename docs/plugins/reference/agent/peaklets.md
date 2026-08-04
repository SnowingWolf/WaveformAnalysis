---
schema_version: 1
document_type: "plugin_reference"
profile: "agent"
provides: "peaklets"
plugin_class: "PeakletPlugin"
module: "waveform_analysis.core.plugins.builtin.peaklets.plugin"
version: "1.2.0"
summary: "Build lightweight cross-channel peaklets from hit_merged intervals."
depends_on: ["hit_merged", "peaklet_components"]
output_kind: "structured_array"
generated: true
---
# peaklets

## Overview

Build lightweight cross-channel peaklets from hit_merged intervals.
PeakletPlugin 负责在 hit_merged 与 peaklet_components 之上构建轻量级的跨通道 peaklet 候选对象。它本身不检测峰形，而是按 peaklet_components 提供的成员关系，把同一逻辑事件（可能横跨多个 (board, channel) 的 hit_merged 行）聚合为一条 peaklet 记录，并汇总出绝对时间范围、参与 hit 数与去重后的通道数。

该插件是 hit 层与 peak 层之间的桥梁：下游的 peaklet_features 特征计算、peaklet_waveforms / peaklet_waveform_pool 波形还原以及最终的 peaks 表都以 peaklets 的行索引作为 peak_id，因此本插件的行序与 peak_id 约定是后续所有 peaklet 消费插件对齐的基础。

实现上先按 peak_id 建立分组成员表并校验组件引用的合法性，再调用 Numba 聚合内核 `_summarize_peaklets_numba` 单次遍历完成时间范围、n_hits 与 n_channels 的汇总，输出为按行对齐的 PEAKLET_DTYPE 结构化数组。

| Item | Value |
| --- | --- |
| Provides | `peaklets` |
| Plugin Class | `PeakletPlugin` |
| Module | `waveform_analysis.core.plugins.builtin.peaklets.plugin` |
| Version | `1.2.0` |
| Category | 峰构建 |
| Output Kind | `structured_array` |

| Dependency | Version Constraint | Resolution | Required Fields | Description |
| --- | --- | --- | --- | --- |
| `hit_merged` | - | declared | - | Merge nearby threshold hits per channel with time-gap and max-width constraints. |
| `peaklet_components` | - | declared | - | Return per-peaklet component hit_merged indices. |
### How It Works

1. 读取输入：从 context 获取 `hit_merged` 与 `peaklet_components` 结构化数组；任一为空时直接返回空 peaklets 数组。
2. 推导 peaklet 数量：以 `peaklet_components['peak_id']` 的最大值加 1 作为 n_peaklets，不依赖外部计数状态。
3. 校验组件引用：调用 `_prepare_component_groups` 按 peak_id 建立分组成员表，并确保每个 `merged_index` 都落在 `hit_merged` 的行范围内，越界即抛错。
4. 计算绝对时间窗口：由 `hit_merged` 的时间戳与采样窗口推导每条记录的绝对起止时间（`_abs_window`），供跨通道聚合使用。
5. 聚合摘要：通过 Numba 内核 `_summarize_peaklets_numba` 对每组组件汇总最小/最大绝对时间、`n_hits` 与去重后的 `n_channels`，并连续记录成员在 `peaklet_components` 中的 `component_offset` 与 `component_count`。
6. 写回输出：返回按 `peak_id`（行序）排序的 `PEAKLET_DTYPE` 结构化数组。

## Configuration

| Name | Type | Default | Unit | Tracked | Deprecated | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `time_window_ns` | `float` | `100.0` | - | yes | no | 跨通道 peaklet 合并时间窗口（ns）。由上游 peaklet_components 消费并判定成员关系；本插件只消费其分组结果。 |
| `max_total_width_ns` | `float` | `10000.0` | - | yes | no | peaklet 最大总宽度（ns），限制链式合并总时长；同样由 peaklet_components 消费。 |
| `dt` | `int` | `None` | - | yes | no | 兼容性采样间隔（ns）回退配置，仅在输入缺少 dt 时使用；优先采用 `hit_merged` 的 dt。 |
## Output

structured_array output with fields: time_start, time_end, center_time, n_hits, n_channels, component_offset, component_count.

| Field | DType | Unit | Meaning |
| --- | --- | --- | --- |
| `time_start` | `int64` | ps | Earliest absolute start time across component hits (ps) |
| `time_end` | `int64` | ps | Latest absolute end time across component hits (ps) |
| `center_time` | `int64` | ps | Midpoint of time_start and time_end (ps) |
| `n_hits` | `int32` | None | Total number of component hits in the peaklet |
| `n_channels` | `int32` | None | Number of distinct (board, channel) pairs in the peaklet |
| `component_offset` | `int64` | None | Start row in peaklet_components for this peaklet |
| `component_count` | `int32` | None | Number of component rows in peaklet_components for this peaklet |
## Usage

### Minimal Example

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.peaklets import PeakletPlugin

ctx = Context(config={"data_root": "DAQ"})
ctx.register(PeakletPlugin())
data = ctx.get_data("run_001", "peaklets")
```

## Operational Notes

### Behavior

- Only `peaklet_components` row membership matters; per-channel hit details are not preserved here and are re-derived downstream via `peaklet_channels`.
- `time_start`/`time_end` are the min/max of member absolute windows and `center_time` is their midpoint `(time_start + time_end) // 2`.
- `n_hits` sums `hit_merged['component_count']` when present, otherwise counts members one by one; `n_channels` counts distinct `(board, channel)` pairs among members.
- `component_offset` accumulates contiguously across peaklets, so it points exactly into `peaklet_components`.
- Empty `peaklet_components` or non-positive peak-id range produce an empty `PEAKLET_DTYPE` array rather than an error.
- `dt` config is a compatibility fallback resolved via `resolve_dt_config`; the effective sample interval is taken from `hit_merged` when available.
### Failure Modes

- `hit_merged` 不是结构化数组时抛出 `ValueError`。
- `peaklet_components` 不是结构化数组时抛出 `ValueError`。
- 存在 `peaklet_components` 行的 `merged_index` 越界（超出 `hit_merged` 行范围）时抛出 `ValueError`。
- `peaklet_id` 分组不连续或成员索引错乱时，`component_offset`/`component_count` 指向的成员切片会失真，下游 `peaklet_channels` 的一致性校验将失败。
### Downstream Impact

Consumers: `peaklet_channels`, `peaklet_features`, `peaklet_waveforms`, `peaks`
- `peaks` 直接以 peaklets 的行序作为 `peak_id`，任何行序或 `component_offset`/`component_count` 变更都会传播到最终 peaks 表。
- `peaklet_channels` 会校验成员数与 `peaklet_components` 的一致性，因此本插件的成员关系语义必须与 peaklet_components 保持同步。

## Maintenance

### Change Playbook

1. 聚合字段语义或 `component_offset`/`component_count` 的变化会级联影响 `peaklet_channels`、`peaklet_features`、`peaklet_waveforms` 与 `peaks` 的消费逻辑。
2. 修改后请运行 peaklets 相关定向测试（test_peaklets_plugin 等）并重新生成 agent 文档。
### Validation

```bash
waveform-docs generate plugins-agent --plugin peaklets
waveform-docs check coverage --strict --fail-on-warning
```
