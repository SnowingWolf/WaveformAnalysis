---
schema_version: 1
document_type: "plugin_reference"
profile: "auto"
provides: "basic_features"
plugin_class: "BasicFeaturesPlugin"
module: "waveform_analysis.core.plugins.builtin.cpu.basic_features"
version: "4.1.0"
summary: "Compute basic height, amplitude, area, and max-abs-diff features from waveform data."
depends_on: []
output_kind: "structured_array"
generated: true
---
# basic_features

## Overview

Compute basic height, amplitude, area, and max-abs-diff features from waveform data.

| Item | Value |
| --- | --- |
| Provides | `basic_features` |
| Plugin Class | `BasicFeaturesPlugin` |
| Module | `waveform_analysis.core.plugins.builtin.cpu.basic_features` |
| Version | `4.1.0` |
| Category | 特征提取 |
| Accelerator | CPU (NumPy/SciPy) |
| Output Kind | `structured_array` |

| Dependency | Version Constraint | Resolution | Required Fields | Description |
| --- | --- | --- | --- | --- |
| - | - | - | - | - |
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

| Field | DType | Unit | Meaning |
| --- | --- | --- | --- |
| `height` | `float32` | - | - |
| `amp` | `float32` | - | - |
| `area` | `float32` | - | - |
| `max_abs_diff` | `float32` | - | - |
| `timestamp` | `int64` | - | - |
| `board` | `int16` | - | - |
| `channel` | `int16` | - | - |
| `record_id` | `int64` | - | - |
## Usage

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import BasicFeaturesPlugin

ctx = Context(config={"data_root": "DAQ"})
ctx.register(BasicFeaturesPlugin())
data = ctx.get_data("run_001", "basic_features")
```
