---
schema_version: 2
document_type: "plugin_reference"
profile: "agent"
provides: "hit_threshold"
plugin_class: "ThresholdHitPlugin"
module: "waveform_analysis.core.plugins.builtin.hit_threshold.plugin"
version: "1.2.2"
summary: "Threshold-only hit detector with THRESHOLD_HIT_DTYPE output."
depends_on: []
declared_depends_on: []
resolved_depends_on: ["records", "wave_pool", "records_asymmetry_mask"]
dependency_profile: "documentation-default-v1"
dependency_profile_values: {"asymmetry_cut_enabled": true, "daq_adapter": "vx2730", "use_filtered": false, "wave_source": "records"}
dependency_config_keys: ["asymmetry_cut_enabled", "channel_role_cut_enabled", "use_filtered", "wave_source"]
output_kind: "structured_array"
execution_kind: "static"
narrative_source: "source"
narrative_source_reason: null
source_fingerprint: "79ebfcefb52cdf0771c16bdc5c3149f93ce53e1f68b085d62bc4f40059c2833f"
generated: true
---
# hit_threshold

## Overview

Threshold-only hit detector with THRESHOLD_HIT_DTYPE output.
records 输入路径采用 ragged wave_pool 扫描，避免不等长波形被强制 padding 成二维矩阵。

**重要 - 输出顺序说明:** - 输出的 hits 按 record 输入顺序连接，**不保证**按全局时间戳排序 - 单个 record 内的 hits 按 sample position 有序（时间递增） - 跨 records 时，如果输入 records 的时间戳乱序，hits 也会乱序 - 下游组件（如 PeakChannelAccessor）在拼接跨 records 波形时会按时间排序 - 如果需要时间有序的 hits，应在使用前按 'timestamp' 字段排序

| Item | Value |
| --- | --- |
| Provides | `hit_threshold` |
| Plugin Class | `ThresholdHitPlugin` |
| Module | `waveform_analysis.core.plugins.builtin.hit_threshold.plugin` |
| Version | `1.2.2` |
| Category | 特征提取 |
| Output Container | `structured_array` |
| Execution Mode | `static` |
| Save Policy | `always` |
| Uses Run Config | no |
| Timeout | `none` |
| Side Effect | no |
| Narrative Source | `source` |
| Source Fingerprint | `79ebfcefb52cdf0771c16bdc5c3149f93ce53e1f68b085d62bc4f40059c2833f` |

### Dependencies

默认文档画像：`documentation-default-v1`（{"asymmetry_cut_enabled": true, "daq_adapter": "vx2730", "use_filtered": false, "wave_source": "records"}）。
该插件通过 `resolve_depends_on(context, run_id)` 动态解析依赖；可能影响解析的配置键：`asymmetry_cut_enabled`, `channel_role_cut_enabled`, `use_filtered`, `wave_source`。

| Dependency | Version Constraint | Resolution | Required Fields | Description |
| --- | --- | --- | --- | --- |
| `records` | - | dynamic-default | - | Build records (event index table) from the shared internal records bundle. |
| `wave_pool` | - | dynamic-default | - | Build wave_pool from the shared internal records bundle. |
| `records_asymmetry_mask` | - | dynamic-default | - | Bool mask for waveform asymmetry selection. |
### How It Works

1. Threshold-only hit detector with THRESHOLD_HIT_DTYPE output.
2. records 输入路径采用 ragged wave_pool 扫描，避免不等长波形被强制 padding 成二维矩阵。
3. **重要 - 输出顺序说明:** - 输出的 hits 按 record 输入顺序连接，**不保证**按全局时间戳排序 - 单个 record 内的 hits 按 sample position 有序（时间递增） - 跨 records 时，如果输入 records 的时间戳乱序，hits 也会乱序 - 下游组件（如 PeakChannelAccessor）在拼接跨 records 波形时会按时间排序 - 如果需要时间有序的 hits，应在使用前按 'timestamp' 字段排序

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
from waveform_analysis.core.plugins import profiles

ctx = Context(config={"data_root": "DAQ", "daq_adapter": "vx2730"})
ctx.register(*profiles.cpu_default())
result = ctx.get_data("run_001", "hit_threshold")
```

示例使用 `run_id="run_001"` 和文档默认运行画像；真实数据路径与配置应以当前实验设置为准。

## Operational Notes

### Behavior

- Threshold Hit Plugin - 阈值 Hit 检测插件（provides='hit_threshold'）。
- 本模块包含： 1. THRESHOLD_HIT_DTYPE 契约 dtype 2. ThresholdHitPlugin: 纯阈值 hit 插件（provides='hit_threshold'），输出 THRESHOLD_HIT_DTYPE
### Failure Modes

- `hit_threshold` 的实际输入由 `resolve_depends_on(context, run_id)` 决定；默认画像之外的配置需要重新确认依赖是否可用。
- 动态依赖无法解析、所需配置不合法或上游产物缺失时，插件不会生成有效输出。
### Downstream Impact

直接消费者：`hit_grouped`、`hit_merge_clusters`、`hit_merged`、`hit_merged_components`、`hit_merged_features`、`peaklet_channels`、`peaklet_waveforms`
## Maintenance

### Change Playbook

1. 保持 `provides`、依赖和输出字段语义稳定，或同步所有下游消费者。
2. 行为、配置或输出契约改变时升级插件 `version`。
3. 修改插件源码后重新生成 Auto、Agent 和 HTML 参考。
### Validation

```bash
waveform-docs generate plugins-agent --plugin hit_threshold
waveform-docs check coverage --strict --fail-on-warning
```
