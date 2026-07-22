---
schema_version: 1
document_type: "plugin_reference"
profile: "agent"
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

1. Resolve input dependencies at runtime from the Context configuration and run_id.
2. Compute per-hit_merged local waveform features from records-backed samples.
3. Return structured_array output with fields: merged_index, board, channel, record_id, time_start, time_end, center_time, max_time, ....
### Execution Chain

`<runtime-resolved inputs>` -> `hit_merged_features`
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
| `merged_index` | `int64` | - | - |
| `board` | `int16` | - | - |
| `channel` | `int16` | - | - |
| `record_id` | `int64` | - | - |
| `time_start` | `int64` | - | - |
| `time_end` | `int64` | - | - |
| `center_time` | `int64` | - | - |
| `max_time` | `int64` | - | - |
| `area` | `float32` | - | - |
| `height` | `float32` | - | - |
| `width` | `float32` | - | - |
| `rise_time` | `float32` | - | - |
| `fall_time` | `float32` | - | - |
| `n_hits` | `int32` | - | - |
| `valid` | `int8` | - | - |
| `area_pe` | `float32` | - | - |
| `height_pe` | `float32` | - | - |
## Usage

### Minimal Example

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import HitMergedFeaturesPlugin

ctx = Context(config={"data_root": "DAQ"})
ctx.register(HitMergedFeaturesPlugin())
data = ctx.get_data("run_001", "hit_merged_features")
```

### Inspect The Execution

```python
ctx.preview_execution("run_001", "hit_merged_features")
ctx.help("hit_merged_features", run_id="run_001")
```

## Operational Notes

### Behavior

Execution chain: `<runtime-resolved inputs>` -> `hit_merged_features`
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
waveform-docs generate plugins-agent --plugin hit_merged_features
waveform-docs check coverage --strict --fail-on-warning
```
