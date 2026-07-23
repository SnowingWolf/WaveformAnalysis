---
schema_version: 1
document_type: "plugin_reference"
profile: "auto"
provides: "hit_merged_features"
plugin_class: "HitMergedFeaturesPlugin"
module: "waveform_analysis.core.plugins.builtin.hit.hit_merged_features"
version: "0.5.1"
summary: "Compute per-hit_merged local waveform features from records-backed samples."
depends_on: []
output_kind: "structured_array"
generated: true
---
# hit_merged_features

## Overview

Compute per-hit_merged local waveform features from records-backed samples.
| Item | Value |
| --- | --- |
| Provides | `hit_merged_features` |
| Plugin Class | `HitMergedFeaturesPlugin` |
| Module | `waveform_analysis.core.plugins.builtin.hit.hit_merged_features` |
| Version | `0.5.1` |
| Category | 特征提取 |
| Accelerator | CPU (NumPy/SciPy) |
| Output Kind | `structured_array` |

| Dependency | Version Constraint | Resolution | Required Fields | Description |
| --- | --- | --- | --- | --- |
| - | - | - | - | No declared inputs. |
### How It Works


## Configuration

| Name | Type | Default | Unit | Tracked | Deprecated | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `wave_source` | `str` | `records` | - | yes | no | 波形来源。hit_merged_features 当前正式支持 records。 |
| `use_filtered` | `bool` | `False` | - | yes | no | 是否使用 wave_pool_filtered 计算局部特征。 |
| `dt` | `int` | `None` | - | yes | no | 保留兼容配置；特征优先使用 records/hits 的 dt |
| `gain_adc_per_pe` | `dict` | `None` | - | yes | no | 按硬件通道配置 ADC/PE 增益，键请使用 "board:channel"，例如 {"0:0": 12.5, "0:1": 13.2}。设置后会新增 area_pe/height_pe 列。 |
| `normalize_to_pe` | `bool` | `False` | - | yes | no | 是否将 area/height 直接归一化为 PE 单位。False (默认): area/height 保持 ADC 单位，area_pe/height_pe 输出 PE 单位。True: area/height 归一化为 PE 单位，area_pe/height_pe 为 NaN。 |
| `feature_num_threads` | `int` | `None` | - | no | no | Numba kernel 线程数；None 使用 Numba 默认。 |
## Output

structured_array output with fields: merged_index, board, channel, record_id, time_start, time_end, center_time, max_time, ....

| Field | DType | Unit | Meaning |
| --- | --- | --- | --- |
| `merged_index` | `int64` | - | Index of the merged hit record |
| `board` | `int16` | - | Hardware board index |
| `channel` | `int16` | - | Physical channel number |
| `record_id` | `int64` | - | Source record identifier |
| `time_start` | `int64` | - | Absolute start time of the merged hit |
| `time_end` | `int64` | - | Absolute end time of the merged hit |
| `center_time` | `int64` | - | Center time of the merged hit |
| `max_time` | `int64` | - | Time of the maximum sample value within the hit window |
| `area` | `float32` | - | Waveform area (integral) within the merged hit window |
| `height` | `float32` | - | Maximum sample height above baseline within the merged hit window |
| `width` | `float32` | - | Width of the merged hit (ns) |
| `rise_time` | `float32` | - | Rise time of the merged hit (ns) |
| `fall_time` | `float32` | - | Fall time of the merged hit (ns) |
| `n_hits` | `int32` | - | Number of component hits in the merged hit |
| `valid` | `int8` | - | Validity flag |
| `area_pe` | `float32` | - | Area in photoelectron units, computed when gain is configured |
| `height_pe` | `float32` | - | Height in photoelectron units, computed when gain is configured |
## Usage

### Minimal Example

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import HitMergedFeaturesPlugin

ctx = Context(config={"data_root": "DAQ"})
ctx.register(HitMergedFeaturesPlugin())
data = ctx.get_data("run_001", "hit_merged_features")
```
### Downstream Consumers

- `peaklet_channels`
