---
schema_version: 2
document_type: "plugin_reference"
profile: "auto"
provides: "waveform_width_integral"
plugin_class: "WaveformWidthIntegralPlugin"
module: "waveform_analysis.core.plugins.builtin.waveform_width_integral.plugin"
version: "2.7.0"
summary: "Event-wise integral quantile width using st_waveforms or filtered_waveforms."
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
source_fingerprint: "f249922ddbb38c01179b7f12ef88db72b3fbf87670aa049c7e57bde060b551b7"
generated: true
---
# waveform_width_integral

## Overview

Event-wise integral quantile width using st_waveforms or filtered_waveforms.
事件级积分分位数宽度 (Event-wise Integral Quantile Width)。

对每条波形进行基线校正后积分，计算累计积分的 t_low/t_high 并得到宽度。 baseline 始终来自 st_waveforms.baseline，与系统其它特征一致。

| Item | Value |
| --- | --- |
| Provides | `waveform_width_integral` |
| Plugin Class | `WaveformWidthIntegralPlugin` |
| Module | `waveform_analysis.core.plugins.builtin.waveform_width_integral.plugin` |
| Version | `2.7.0` |
| Category | 波形处理 |
| Output Container | `structured_array` |
| Execution Mode | `static` |
| Save Policy | `always` |
| Uses Run Config | no |
| Timeout | `none` |
| Side Effect | no |
| Narrative Source | `source` |
| Source Fingerprint | `f249922ddbb38c01179b7f12ef88db72b3fbf87670aa049c7e57bde060b551b7` |

### Dependencies

默认文档画像：`documentation-default-v1`（{"daq_adapter": "vx2730", "use_filtered": false, "wave_source": "records"}）。
该插件通过 `resolve_depends_on(context, run_id)` 动态解析依赖；可能影响解析的配置键：`use_filtered`, `wave_source`。

| Dependency | Version Constraint | Resolution | Required Fields | Description |
| --- | --- | --- | --- | --- |
| `records` | - | dynamic-default | - | Build records (event index table) from the shared internal records bundle. |
| `wave_pool` | - | dynamic-default | - | Build wave_pool from the shared internal records bundle. |
### How It Works

1. 事件级积分分位数宽度 (Event-wise Integral Quantile Width)。
2. 对每条波形进行基线校正后积分，计算累计积分的 t_low/t_high 并得到宽度。 baseline 始终来自 st_waveforms.baseline，与系统其它特征一致。

## Configuration

| Name | Type | Default | Unit | Tracked | Deprecated | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `q_low` | `float` | `0.1` | - | yes | no | 低分位点（默认 0.10） |
| `q_high` | `float` | `0.9` | - | yes | no | 高分位点（默认 0.90） |
| `use_filtered` | `bool` | `False` | - | yes | no | 是否使用 filtered_waveforms（若启用，baseline 仍来自 st_waveforms） |
| `wave_source` | `str` | `auto` | - | yes | no | 波形数据源: auto\|records\|st_waveforms\|filtered_waveforms |
| `sampling_rate` | `float` | `0.5` | - | yes | no | 采样率（GHz），用于换算时间（ns） |
| `dt` | `float` | `None` | - | yes | no | 采样间隔（ns），优先级高于 sampling_rate |
## Output

structured_array output with fields: t_low, t_high, width, t_low_samples, t_high_samples, width_samples, q_total, timestamp, ....

| Field | DType | Unit | Meaning |
| --- | --- | --- | --- |
| `t_low` | `float32` | ns | Low-quantile integral point (ns, corresponding to q_low) |
| `t_high` | `float32` | ns | High-quantile integral point (ns, corresponding to q_high) |
| `width` | `float32` | ns | t_high minus t_low (ns) |
| `t_low_samples` | `float32` | samples | Low-quantile integral point in sample index |
| `t_high_samples` | `float32` | samples | High-quantile integral point in sample index |
| `width_samples` | `float32` | samples | Pulse width in sample counts |
| `q_total` | `float64` | ADC counts | Total baseline-subtracted charge (integral) |
| `timestamp` | `int64` | ps | ADC event timestamp |
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
result = ctx.get_data("run_001", "waveform_width_integral")
```

示例使用 `run_id="run_001"` 和文档默认运行画像；真实数据路径与配置应以当前实验设置为准。

### Downstream Consumers

- 没有声明直接的内置消费者。
