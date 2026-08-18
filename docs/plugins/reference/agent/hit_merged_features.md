---
schema_version: 1
document_type: "plugin_reference"
profile: "agent"
provides: "hit_merged_features"
plugin_class: "HitMergedFeaturesPlugin"
module: "waveform_analysis.core.plugins.builtin.hit_merged_features.plugin"
version: "1.1.1"
summary: "Compute per-hit_merged local waveform features from records-backed samples."
depends_on: []
output_kind: "structured_array"
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
| Version | `1.1.1` |
| Category | 特征提取 |
| Output Kind | `structured_array` |

| Dependency | Version Constraint | Resolution | Required Fields | Description |
| --- | --- | --- | --- | --- |
| - | - | - | - | No declared inputs. |
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
from waveform_analysis.core.plugins.builtin.hit_merged_features import HitMergedFeaturesPlugin

ctx = Context(config={"data_root": "DAQ"})
ctx.register(HitMergedFeaturesPlugin())
data = ctx.get_data("run_001", "hit_merged_features")
```

## Operational Notes

### Behavior

- 默认积分有符号的 baseline/polarity 转换后波形；clip_negative_signal=True 在积分前裁剪负采样。
- fallback 保留同通道重叠的去重和 WaveformOverlapConflictError 语义，不用直接 component 求和替代。
- feature_num_threads 只控制 Numba 路径；log_feature_diagnostics 仅记录运行时统计，不参与 cache lineage。
### Failure Modes

- 缺失 record、无效 component 映射或空的裁剪后窗口会显式失败。
- 同一硬件通道同一绝对时间的位级不同采样会抛出 WaveformOverlapConflictError。
### Downstream Impact

Terminal output; no direct builtin consumer is declared.

- peaklet_channels、peaklets 与后续峰特征消费本插件的 area、height 和时间字段。
- 版本 1.1.0 更换 fallback 执行路径，缓存会因 lineage 自动重建。

## Maintenance

### Change Playbook

1. 修改 fallback 时必须对照 Python canonical，保持 signed、clipped、重叠去重和冲突错误语义。
2. 性能回归同时报告 Numba compute 和波形 pool 的 cache-save I/O，避免将持久化误判为重算。
### Validation

```bash
waveform-docs generate plugins-agent --plugin hit_merged_features
waveform-docs check coverage --strict --fail-on-warning
```
