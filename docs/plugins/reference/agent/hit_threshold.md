---
schema_version: 1
document_type: "plugin_reference"
profile: "agent"
provides: "hit_threshold"
plugin_class: "ThresholdHitPlugin"
module: "waveform_analysis.core.plugins.builtin.hit.hit_finder"
version: "1.2.0"
summary: "Threshold-only hit detector with THRESHOLD_HIT_DTYPE output."
depends_on: []
output_kind: "structured_array"
generated: true
---
# hit_threshold

## Overview

Threshold-only hit detector with THRESHOLD_HIT_DTYPE output.

| Item | Value |
| --- | --- |
| Provides | `hit_threshold` |
| Plugin Class | `ThresholdHitPlugin` |
| Module | `waveform_analysis.core.plugins.builtin.hit.hit_finder` |
| Version | `1.2.0` |
| Category | 特征提取 |
| Accelerator | CPU (NumPy/SciPy) |
| Output Kind | `structured_array` |

| Dependency | Version Constraint | Resolution | Required Fields | Description |
| --- | --- | --- | --- | --- |
| - | - | - | - | - |
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

| Field | DType | Unit | Meaning |
| --- | --- | --- | --- |
| `position` | `int64` | - | - |
| `edge_start` | `int32` | - | - |
| `edge_end` | `int32` | - | - |
| `width` | `float32` | - | - |
| `dt` | `int32` | - | - |
| `timestamp` | `int64` | - | - |
| `board` | `int16` | - | - |
| `channel` | `int16` | - | - |
| `record_id` | `int64` | - | - |
## Usage

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import ThresholdHitPlugin

ctx = Context(config={"data_root": "DAQ"})
ctx.register(ThresholdHitPlugin())
data = ctx.get_data("run_001", "hit_threshold")
```

## Operational Notes

### Behavior

- Hit Finder Plugins - 阈值 Hit 检测插件

本模块包含：
1. HitFinderPlugin: 旧导入路径兼容别名（推荐改为 peak_finding.HitFinderPlugin）
2. ThresholdHitPlugin: 新的纯阈值 hit 插件（provides='hit_threshold'），输出 THRESHOLD_HIT_DTYPE

本版本的主要改动
----------------
1. records 输入路径优先使用 ragged layout：wave_pool + wave_offset + event_length。
2. 对每条 record 先做 min/max record-level prefilter：
   - positive polarity: max(wave) >= baseline + threshold
   - negative polarity: min(wave) <= baseline - threshold
   未通过预筛选的 record 不构造 mask、不找 hit 区间。
3. records 路径不再强制调用 rv.waves(...) 生成 padded 2D matrix，适合不等长波形。
4. waveform matrix 输入路径仍然保留，用于 st_waveforms / filtered_waveforms 等固定窗口数据。
### Failure Modes

- Dependency data, configuration, or output contract validation may fail explicitly.
### Downstream Impact

-
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
