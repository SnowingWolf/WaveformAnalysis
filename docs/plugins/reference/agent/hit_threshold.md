---
schema_version: 1
document_type: "plugin_reference"
profile: "agent"
provides: "hit_threshold"
plugin_class: "ThresholdHitPlugin"
module: "waveform_analysis.core.plugins.builtin.hit_threshold.plugin"
version: "1.2.2"
summary: "Threshold-only hit detector with THRESHOLD_HIT_DTYPE output."
depends_on: []
output_kind: "structured_array"
generated: true
---
# hit_threshold

## Overview

Threshold-only hit detector with THRESHOLD_HIT_DTYPE output.
Threshold-only hit detector with THRESHOLD_HIT_DTYPE output.

| Item | Value |
| --- | --- |
| Provides | `hit_threshold` |
| Plugin Class | `ThresholdHitPlugin` |
| Module | `waveform_analysis.core.plugins.builtin.hit_threshold.plugin` |
| Version | `1.2.2` |
| Category | 特征提取 |
| Output Kind | `structured_array` |

| Dependency | Version Constraint | Resolution | Required Fields | Description |
| --- | --- | --- | --- | --- |
| - | - | - | - | No declared inputs. |
### How It Works


## Configuration

| Name | Type | Default | Unit | Tracked | Deprecated | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `threshold` | `float` | `10.0` | - | yes | no | Hit 检测阈值 |
| `use_filtered` | `bool` | `False` | - | yes | no | 是否使用 filtered_waveforms（需要先注册 FilteredWaveformsPlugin） |
| `wave_source` | `str` | `auto` | - | yes | no | 波形数据源: auto\|records\|st_waveforms\|filtered_waveforms |
| `left_extension` | `int` | `2` | - | yes | no | Hit 左侧扩展点数 |
| `right_extension` | `int` | `2` | - | yes | no | Hit 右侧扩展点数 |
| `dt` | `int` | `None` | - | yes | no | 采样间隔（ns）。仅在输入数据缺少 dt 字段时作为兼容补充。 |
| `channel_config` | `dict` | `None` | - | yes | no | 按 (board, channel) 的插件通道覆盖配置，可覆盖 threshold。 |
| `backend` | `str` | `auto` | - | yes | no | Hit finding backend: auto\|numba\|ragged。auto 对 records 在达到 parallel_min_records 后尝试 numba，否则使用 ragged。 |
| `chunk_parallel` | `bool` | `True` | - | yes | no | 是否对 records ragged numba 后端启用 chunk 级线程并行。 |
| `n_workers` | `int` | `0` | - | yes | no | records ragged chunk 并行 worker 数；<=0 表示自动。 |
| `parallel_chunk_size` | `int` | `50000` | - | yes | no | records ragged chunk 并行大小（每个任务处理的 record 数）。 |
| `parallel_min_records` | `int` | `50000` | - | yes | no | 触发 records ragged chunk 并行的最小 record 数。 |
| `streaming_chunk_size` | `int` | `10000` | - | yes | no | 流式处理时的 chunk 大小（仅对 RecordsBundleRef 生效） |
| `asymmetry_cut_enabled` | `bool` | `True` | - | yes | no | 是否在 records 路径的 hit 查找前应用 records_asymmetry_mask。 |
| `channel_role_cut_enabled` | `bool` | `False` | - | yes | no | 是否在 records 路径的 hit 查找前应用 records_detector_mask。 |
## Output

structured_array output with fields: position, edge_start, edge_end, width, dt, timestamp, board, channel, ....

| Field | DType | Unit | Meaning |
| --- | --- | --- | --- |
| `position` | `int64` | samples | Representative sample position within the hit interval |
| `edge_start` | `int32` | samples | Hit window start boundary (safe half-open sample index within record) |
| `edge_end` | `int32` | samples | Hit window end boundary (safe half-open sample index within record) |
| `width` | `float32` | samples | Hit window width in samples |
| `dt` | `int32` | ns | Sample interval in nanoseconds |
| `timestamp` | `int64` | ps | Global timestamp in picoseconds at the hit position |
| `board` | `int16` | None | Hardware board index |
| `channel` | `int16` | None | Physical channel number |
| `record_id` | `int64` | None | Identifier of the source waveform record |
## Usage

### Minimal Example

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.hit_threshold import ThresholdHitPlugin

ctx = Context(config={"data_root": "DAQ"})
ctx.register(ThresholdHitPlugin())
data = ctx.get_data("run_001", "hit_threshold")
```

## Operational Notes

### Behavior

### Failure Modes

- Dependency data, configuration, or output contract validation may fail explicitly.
### Downstream Impact

Consumers: `hit_grouped`, `hit_merge_clusters`, `hit_merged`, `hit_merged_components`, `peaklet_channels`

## Maintenance

### Change Playbook

1. Keep `provides` and dependency semantics stable or update all consumers.
2. Bump `version` for behavior, configuration, or output contract changes.
3. Regenerate auto, agent, and web references after metadata changes.
### Validation

```bash
waveform-docs generate plugins-agent --plugin hit_threshold
waveform-docs check coverage --strict --fail-on-warning
```
