---
schema_version: 2
document_type: "plugin_reference"
profile: "auto"
provides: "hit_merged_features"
plugin_class: "HitMergedFeaturesPlugin"
module: "waveform_analysis.core.plugins.builtin.hit_merged_features.plugin"
version: "1.1.3"
summary: "Compute per-hit_merged local waveform features from records-backed samples."
depends_on: []
declared_depends_on: []
resolved_depends_on: ["hit_merged", "hit_merged_components", "hit_threshold", "records", "wave_pool"]
dependency_profile: "documentation-default-v1"
dependency_profile_values: {"daq_adapter": "vx2730", "use_filtered": false, "wave_source": "records"}
dependency_config_keys: ["clip_negative_signal", "use_filtered", "wave_source"]
output_kind: "structured_array"
execution_kind: "static"
narrative_source: "source"
narrative_source_reason: null
source_fingerprint: "6e1f87b9584a394c14e56aa54949186af8dfc484f9f20c3a1341a7120ccb4ea3"
generated: true
---
# hit_merged_features

## Overview

Compute per-hit_merged local waveform features from records-backed samples.
为每条 `hit_merged` 计算单硬件通道的局部波形特征。直接窗口由 Numba 并行计算；cross-record fallback 先按安全性分流，非重叠片段按绝对时间在 Numba 中物化，再用与 Python canonical 相同的 NumPy 归约生成特征。

| Item | Value |
| --- | --- |
| Provides | `hit_merged_features` |
| Plugin Class | `HitMergedFeaturesPlugin` |
| Module | `waveform_analysis.core.plugins.builtin.hit_merged_features.plugin` |
| Version | `1.1.3` |
| Category | 特征提取 |
| Output Container | `structured_array` |
| Execution Mode | `static` |
| Save Policy | `always` |
| Uses Run Config | yes |
| Timeout | `none` |
| Side Effect | no |
| Narrative Source | `source` |
| Source Fingerprint | `6e1f87b9584a394c14e56aa54949186af8dfc484f9f20c3a1341a7120ccb4ea3` |

### Dependencies

默认文档画像：`documentation-default-v1`（{"daq_adapter": "vx2730", "use_filtered": false, "wave_source": "records"}）。
该插件通过 `resolve_depends_on(context, run_id)` 动态解析依赖；可能影响解析的配置键：`clip_negative_signal`, `use_filtered`, `wave_source`。

| Dependency | Version Constraint | Resolution | Required Fields | Description |
| --- | --- | --- | --- | --- |
| `hit_merged` | - | dynamic-default | - | Merge nearby threshold hits per channel with time-gap and max-width constraints. |
| `hit_merged_components` | - | dynamic-default | - | Return per-cluster component hit indices for hit_merged rows. |
| `hit_threshold` | - | dynamic-default | - | Threshold-only hit detector with THRESHOLD_HIT_DTYPE output. |
| `records` | - | dynamic-default | - | Build records (event index table) from the shared internal records bundle. |
| `wave_pool` | - | dynamic-default | - | Build wave_pool from the shared internal records bundle. |
### How It Works

1. 读取 hit_merged、component 映射、threshold hits、records 与所选波形池。
2. 直接窗口走 Numba 单遍 area/height 计算；无效窗口展开为 component 片段。
3. 同通道、同 dt 且绝对时间不重叠的 fallback 片段走 Numba compact 路径；可能重叠或不安全的行保留 Python canonical 合并。
4. 将 canonical 顺序的 float32 样本以 NumPy float64 求面积，并写入固定输出 dtype。

## Configuration

| Name | Type | Default | Unit | Tracked | Deprecated | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `wave_source` | `str` | `records` | - | yes | no | 波形来源。hit_merged_features 当前正式支持 records。 |
| `use_filtered` | `bool` | `False` | - | yes | no | 是否使用 wave_pool_filtered 计算局部特征。 |
| `clip_negative_signal` | `bool` | `False` | - | yes | no | 是否在积分前把负的基线扣除采样裁剪为 0。默认 False，area 直接积分有符号波形；True 仅用于兼容旧行为。 |
| `dt` | `int` | `None` | - | yes | no | 保留兼容配置；特征优先使用 records/hits 的 dt |
| `gain_adc_per_pe` | `dict` | `None` | - | yes | no | 按硬件通道配置 ADC/PE 增益，键请使用 "board:channel"，例如 {"0:0": 12.5, "0:1": 13.2}。设置后会新增 area_pe/height_pe 列。 |
| `normalize_to_pe` | `bool` | `False` | - | yes | no | 是否将 area/height 直接归一化为 PE 单位。False (默认): area/height 保持 ADC 单位，area_pe/height_pe 输出 PE 单位。True: area/height 归一化为 PE 单位，area_pe/height_pe 为 NaN。 |
| `feature_num_threads` | `int` | `None` | - | no | no | 设置 Numba 路径线程数；None 使用 Numba 默认，且不改变 cache lineage。 |
| `log_feature_diagnostics` | `bool` | `False` | - | no | no | 记录 direct/Numba canonical/Python canonical 的行数、样本数和耗时。 |
## Output

structured_array output with fields: merged_index, board, channel, record_id, time_start, time_end, center_time, max_time, ....

| Field | DType | Unit | Meaning |
| --- | --- | --- | --- |
| `merged_index` | `int64` | None | Index of the merged hit record |
| `board` | `int16` | None | Hardware board index |
| `channel` | `int16` | None | Physical channel number |
| `record_id` | `int64` | None | Source record identifier |
| `time_start` | `int64` | ps | Absolute start time of the merged hit |
| `time_end` | `int64` | ps | Absolute end time of the merged hit |
| `center_time` | `int64` | ps | Center time of the merged hit |
| `max_time` | `int64` | ps | Time of the maximum sample value within the hit window |
| `area` | `float32` | ADC counts | Waveform area (integral) within the merged hit window |
| `height` | `float32` | ADC counts | Maximum sample height above baseline within the merged hit window |
| `width` | `float32` | ns | Width of the merged hit (ns) |
| `rise_time` | `float32` | ns | Rise time of the merged hit (ns) |
| `fall_time` | `float32` | ns | Fall time of the merged hit (ns) |
| `n_hits` | `int32` | None | Number of component hits in the merged hit |
| `valid` | `int8` | None | Validity flag |
| `area_pe` | `float32` | PE | Area in photoelectron units, computed when gain is configured |
| `height_pe` | `float32` | PE | Height in photoelectron units, computed when gain is configured |
## Usage

### Minimal Example

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins import profiles

ctx = Context(config={"data_root": "DAQ", "daq_adapter": "vx2730"})
ctx.register(*profiles.cpu_default())
result = ctx.get_data("run_001", "hit_merged_features")
```

示例使用 `run_id="run_001"` 和文档默认运行画像；真实数据路径与配置应以当前实验设置为准。

### Downstream Consumers

- `peaklet_channels`
