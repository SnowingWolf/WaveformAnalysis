---
schema_version: 1
document_type: "plugin_reference"
profile: "agent"
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
Plugin to compute basic height/area features from structured waveforms.

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
| - | - | - | - | No declared inputs. |
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
from waveform_analysis.core.plugins.builtin.cpu import BasicFeaturesPlugin

ctx = Context(config={"data_root": "DAQ"})
ctx.register(BasicFeaturesPlugin())
data = ctx.get_data("run_001", "basic_features")
```

## Operational Notes

### Behavior

- 计算基础特征（height/amp/area/max_abs_diff）
- 使用逐条处理模式，支持任意长度波形，不使用 padding。
- height = baseline - min(wave)  (信号偏离基线的幅度) amp = max - min  (峰峰值振幅) area = sum(baseline - wave)  (不包含 padding) max_abs_diff = max(abs(diff(wave)))
### Failure Modes

- Dependency data, configuration, or output contract validation may fail explicitly.
### Downstream Impact

Terminal output; no direct builtin consumer is declared.


## Maintenance

### Change Playbook

1. Keep `provides` and dependency semantics stable or update all consumers.
2. Bump `version` for behavior, configuration, or output contract changes.
3. Regenerate auto, agent, and web references after metadata changes.
### Validation

```bash
waveform-docs generate plugins-agent --plugin basic_features
waveform-docs check coverage --strict --fail-on-warning
```
