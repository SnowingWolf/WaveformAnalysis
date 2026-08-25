---
schema_version: 2
document_type: "plugin_reference"
profile: "auto"
provides: "basic_features"
plugin_class: "BasicFeaturesPlugin"
module: "waveform_analysis.core.plugins.builtin.basic_features.plugin"
version: "4.1.0"
summary: "Compute basic height, amplitude, area, and max-abs-diff features from waveform data."
depends_on: []
declared_depends_on: []
resolved_depends_on: ["records", "wave_pool"]
dependency_profile: "documentation-default-v1"
dependency_profile_values: {"daq_adapter": "vx2730", "use_filtered": false, "wave_source": "records"}
dependency_config_keys: ["use_filtered", "wave_source"]
output_kind: "structured_array"
execution_kind: "static"
narrative_source: "source"
narrative_source_reason: null
source_fingerprint: "c418569295963ec951c2fb2910f8fc3706542531607b1ed7bb9037a313fd29d3"
generated: true
---
# basic_features

## Overview

Compute basic height, amplitude, area, and max-abs-diff features from waveform data.
Plugin to compute basic height/area features from structured waveforms.

| Item | Value |
| --- | --- |
| Provides | `basic_features` |
| Plugin Class | `BasicFeaturesPlugin` |
| Module | `waveform_analysis.core.plugins.builtin.basic_features.plugin` |
| Version | `4.1.0` |
| Category | 特征提取 |
| Output Container | `structured_array` |
| Execution Mode | `static` |
| Save Policy | `always` |
| Uses Run Config | no |
| Timeout | `none` |
| Side Effect | no |
| Narrative Source | `source` |
| Source Fingerprint | `c418569295963ec951c2fb2910f8fc3706542531607b1ed7bb9037a313fd29d3` |

### Dependencies

默认文档画像：`documentation-default-v1`（{"daq_adapter": "vx2730", "use_filtered": false, "wave_source": "records"}）。
该插件通过 `resolve_depends_on(context, run_id)` 动态解析依赖；可能影响解析的配置键：`use_filtered`, `wave_source`。

| Dependency | Version Constraint | Resolution | Required Fields | Description |
| --- | --- | --- | --- | --- |
| `records` | - | dynamic-default | - | Build records (event index table) from the shared internal records bundle. |
| `wave_pool` | - | dynamic-default | - | Build wave_pool from the shared internal records bundle. |
### How It Works

1. 计算基础特征（height/amp/area/max_abs_diff）
2. 使用逐条处理模式，支持任意长度波形，不使用 padding。
3. height = baseline - min(wave)  (信号偏离基线的幅度) amp = max - min  (峰峰值振幅) area = sum(baseline - wave)  (不包含 padding) max_abs_diff = max(abs(diff(wave)))

## Configuration

| Name | Type | Default | Unit | Tracked | Deprecated | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `height_range` | `tuple` | `(40, 90)` | - | yes | no | 高度计算范围 (start, end) |
| `area_range` | `tuple` | `(0, None)` | - | yes | no | 面积计算范围 (start, end)，end=None 表示积分到波形末端 |
| `use_filtered` | `bool` | `False` | - | yes | no | 是否使用 filtered_waveforms（需要先注册 FilteredWaveformsPlugin） |
| `wave_source` | `str` | `auto` | - | yes | no | 波形数据源: auto\|records\|st_waveforms\|filtered_waveforms |
| `fixed_baseline` | `dict` | `None` | - | yes | no | 已废弃；按硬件通道固定 baseline 请改用 channel_config。 |
| `channel_config` | `dict` | `None` | - | yes | no | 按 (board, channel) 的插件通道覆盖配置，可覆盖 fixed_baseline。 |
| `compute_max_abs_diff` | `bool` | `True` | - | yes | no | 是否计算 max_abs_diff（关闭可减少一次全波形扫描，提升性能） |
| `batch_size` | `int` | `10000` | - | yes | no | 批处理大小：当 records 数量超过此值时，分批处理以降低内存峰值 |
## Output

structured_array output with fields: height, amp, area, max_abs_diff, timestamp, board, channel, record_id.

| Field | DType | Unit | Meaning |
| --- | --- | --- | --- |
| `height` | `float32` | ADC counts | Pulse height (baseline minus minimum sample) |
| `amp` | `float32` | ADC counts | Peak-to-peak amplitude (max minus min) |
| `area` | `float32` | ADC counts | Waveform integral area |
| `max_abs_diff` | `float32` | ADC counts | Maximum absolute difference between consecutive samples |
| `timestamp` | `int64` | ps | ADC timestamp in picoseconds |
| `board` | `int16` | None | Hardware board index |
| `channel` | `int16` | None | Physical channel number |
| `record_id` | `int64` | None | Source record identifier |
## Usage

### Minimal Example

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins import profiles

ctx = Context(config={"data_root": "DAQ", "daq_adapter": "vx2730"})
ctx.register(*profiles.cpu_default())
result = ctx.get_data("run_001", "basic_features")
```

示例使用 `run_id="run_001"` 和文档默认运行画像；真实数据路径与配置应以当前实验设置为准。

### Downstream Consumers

- `df`
