---
schema_version: 1
document_type: "plugin_reference"
profile: "agent"
provides: "peaks"
plugin_class: "PeaksPlugin"
module: "waveform_analysis.core.plugins.builtin.peaks.plugin"
version: "4.0.1"
summary: "Build final peaks table from peaklets and waveform-derived features."
depends_on: ["peaklets", "peaklet_features", "peaklet_channels"]
output_kind: "structured_array"
generated: true
---
# peaks

## Overview

Build final peaks table from peaklets and waveform-derived features.
PeaksPlugin 是分析链末端的用户级插件，把 peaklet 层面的元数据与 peaklet_features 导出的波形派生特征合并为最终的用户可见 peaks 表。它不重新计算任何物理量，只负责把 特征按 `peak_id` 稳定地对齐到 `peaklets` 的行序，并以其行索引作为 `peak_id`。

由于 `peaklet_features` 的特征行是按 peak_id 解析的，PeaksPlugin 采用稳定排序 + `searchsorted` 的方式将每个 peaklet 精确匹配到其特征行：任何 peaklet 缺失对应特征都会被认定为数据不一致并抛出异常，从而保证 peaks 表总是完整、且与 peaklets 一一对齐。

peaks 表同时携带峰形时序字段（rise_time、fall_time、width_25_75、area、height 等）与聚合规模字段（n_hits、n_channels），是上游 S1/S2 分类与物理筛选（peak_classification、s1_s2_pair_candidates）的唯一输入入口。

| Item | Value |
| --- | --- |
| Provides | `peaks` |
| Plugin Class | `PeaksPlugin` |
| Module | `waveform_analysis.core.plugins.builtin.peaks.plugin` |
| Version | `4.0.1` |
| Category | 特征提取 |
| Output Kind | `structured_array` |

| Dependency | Version Constraint | Resolution | Required Fields | Description |
| --- | --- | --- | --- | --- |
| `peaklets` | - | declared | - | Build lightweight cross-channel peaklets from hit_merged intervals. |
| `peaklet_features` | - | declared | - | Compute peaklet waveform features from ragged signal pools. |
| `peaklet_channels` | - | declared | - | Aggregate hit_merged_features into per-peaklet channel contribution rows. |
### How It Works

1. 读取输入：从 context 获取 `peaklets` 与 `peaklet_features` 结构化数组；`peaklets` 为空时返回空 peaks 数组。
2. 排序特征行：以 `peaklet_features['peak_id']` 作稳定排序（mergesort），得到按 peak_id 递增的特征序列。
3. 对齐 peaklet：对每个 `peak_id`（即 peaklet 行号）用 `searchsorted` 定位特征行，并校验特征行的 peak_id 与 peaklet 一致；任一 peaklet 找不到特征则抛错。
4. 复制波形特征：将 time_start、time_end、time_peak、center_time、rise_time、fall_time、width_25_75、rise_time_10_50、range_90p_area、area、height、width 从对齐后的特征行复制到输出。
5. 填入峰规模信息：从 `peaklets` 复制 `n_hits` 与 `n_channels`。
6. 返回结果：输出 `PEAKS_DTYPE` 结构化数组，行序与 `peaklets` 完全一致，`peak_id` 即行索引。

## Configuration

| Name | Type | Default | Unit | Tracked | Deprecated | Description |
| --- | --- | --- | --- | --- | --- | --- |
| - | - | - | - | - | - | - |
## Output

structured_array output with fields: peak_id, time_start, time_end, time_peak, center_time, rise_time, fall_time, width_25_75, ....

| Field | DType | Unit | Meaning |
| --- | --- | --- | --- |
| `peak_id` | `int64` | None | Peak identifier, matching the row index in the peaks table |
| `time_start` | `int64` | ps | Earliest absolute start time across component hits (ps) |
| `time_end` | `int64` | ps | Latest absolute end time across component hits (ps) |
| `time_peak` | `int64` | ps | Time of the maximum sample value (ps) |
| `center_time` | `int64` | ps | Center time of the peak (ps) |
| `rise_time` | `float32` | ns | Rise time (ns) |
| `fall_time` | `float32` | ns | Fall time (ns) |
| `width_25_75` | `float32` | ns | Width between 25% and 75% of the peak (ns) |
| `rise_time_10_50` | `float32` | ns | Rise time from 10% to 50% (ns) |
| `range_90p_area` | `float32` | ns | Time range covering 90% of the waveform area (ns) |
| `area` | `float32` | ADC counts | Total waveform area |
| `height` | `float32` | ADC counts | Maximum waveform height |
| `width` | `float32` | ns | Pulse width (ns) |
| `n_hits` | `int32` | None | Total number of component hits in the peak |
| `n_channels` | `int32` | None | Number of distinct (board, channel) pairs in the peak |
## Usage

### Minimal Example

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.peaks import PeaksPlugin

ctx = Context(config={"data_root": "DAQ"})
ctx.register(PeaksPlugin())
data = ctx.get_data("run_001", "peaks")
```

## Operational Notes

### Behavior

- `peaks` and `peaklets` are strictly 1:1: every peaklet row must have a matching `peaklet_features` row or compute raises.
- `peak_id` equals the row index in the output array and matches the corresponding `peaklets` row.
- Extra `peaklet_features` rows whose `peak_id` is not present in `peaklets` are simply not selected; they do not fail the plugin.
- The plugin performs no physics computation; all waveform quantities originate from `peaklet_features`.
### Failure Modes

- `peaklets` 或 `peaklet_features` 不是结构化数组时抛出 `ValueError`。
- 存在某个 peaklet 在 `peaklet_features` 中找不到相同 `peak_id` 的特征行时抛出 `ValueError`，通常意味着上游缓存或成员关系错位。
- 上游 `peaklet_features` 与 `peaklets` 的 `peak_id` 语义不一致（如特征缺失整段 peaklet）会触发上述异常而使 peaks 无法物化。
### Downstream Impact

Consumers: `peak_classification`, `s1_s2_pair_candidates`
- `peak_classification` 直接以 peaks 特征做 S1/S2 分类，任何特征字段语义变化都会改变分类结果。
- `s1_s2_pair_candidates` 以 peaks（尤其经过分类后的 peak）生成物理候选配对，依赖 peaks 的时序与规模字段。

## Maintenance

### Change Playbook

1. 输出字段或对齐规则的变动会影响 `peak_classification` 与 `s1_s2_pair_candidates`，请同步运行对应定向测试并重新生成文档。
### Validation

```bash
waveform-docs generate plugins-agent --plugin peaks
waveform-docs check coverage --strict --fail-on-warning
```
