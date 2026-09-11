---
schema_version: 2
document_type: "plugin_reference"
profile: "agent"
provides: "waveform_width"
plugin_class: "WaveformWidthPlugin"
module: "waveform_analysis.core.plugins.builtin.waveform_width.plugin"
version: "3.0.0"
summary: "Calculate rise/fall time based on peak detection results."
depends_on: []
declared_depends_on: []
resolved_depends_on: ["hit", "st_waveforms"]
dependency_profile: "documentation-default-v1"
dependency_profile_values: {"daq_adapter": "vx2730", "use_filtered": false, "wave_source": "records"}
dependency_config_keys: ["use_filtered"]
output_kind: "structured_array"
execution_kind: "static"
narrative_source: "source"
narrative_source_reason: null
source_fingerprint: "3301315de87b0f4d67c1a63d18188182df40c60f39c94e15cc588a3eb304bc81"
generated: true
---
# waveform_width

## Overview

Calculate rise/fall time based on peak detection results.
波形宽度计算插件 - 基于峰值检测结果计算上升/下降时间。

依赖 HitFinderPlugin 提供的峰值位置和边缘信息，计算： - 上升时间: 从 10% 峰高到 90% 峰高的时间 - 下降时间: 从 90% 峰高到 10% 峰高的时间 - 总宽度: 从上升起点到下降终点的总时间

支持使用原始波形或滤波后的波形进行精确计算。

| Item | Value |
| --- | --- |
| Provides | `waveform_width` |
| Plugin Class | `WaveformWidthPlugin` |
| Module | `waveform_analysis.core.plugins.builtin.waveform_width.plugin` |
| Version | `3.0.0` |
| Category | 波形处理 |
| Output Container | `structured_array` |
| Execution Mode | `static` |
| Save Policy | `always` |
| Uses Run Config | no |
| Timeout | `none` |
| Side Effect | no |
| Narrative Source | `source` |
| Source Fingerprint | `3301315de87b0f4d67c1a63d18188182df40c60f39c94e15cc588a3eb304bc81` |

### Dependencies

默认文档画像：`documentation-default-v1`（{"daq_adapter": "vx2730", "use_filtered": false, "wave_source": "records"}）。
该插件通过 `resolve_depends_on(context, run_id)` 动态解析依赖；可能影响解析的配置键：`use_filtered`。

| Dependency | Version Constraint | Resolution | Required Fields | Description |
| --- | --- | --- | --- | --- |
| `hit` | - | dynamic-default | - | Detect peaks in waveforms and extract peak features. |
| `st_waveforms` | - | dynamic-default | - | Extract waveforms from raw CSV files and structure them into NumPy structured arrays. |
### How It Works

1. 计算波形宽度特征
2. 基于 HitFinderPlugin 的峰值检测结果，计算每个峰值的上升/下降时间。

## Configuration

| Name | Type | Default | Unit | Tracked | Deprecated | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `use_filtered` | `bool` | `False` | - | yes | no | 是否使用滤波后的波形（需要先注册 FilteredWaveformsPlugin） |
| `sampling_rate` | `float` | `None` | - | yes | no | 采样率（GHz）；未设置时默认使用 0.5 GHz |
| `rise_low` | `float` | `0.1` | - | yes | no | 上升时间的低阈值比例（默认 10%） |
| `rise_high` | `float` | `0.9` | - | yes | no | 上升时间的高阈值比例（默认 90%） |
| `fall_high` | `float` | `0.9` | - | yes | no | 下降时间的高阈值比例（默认 90%） |
| `fall_low` | `float` | `0.1` | - | yes | no | 下降时间的低阈值比例（默认 10%） |
| `interpolation` | `bool` | `True` | - | yes | no | 是否使用线性插值提高时间计算精度 |
## Output

structured_array output with fields: rise_time, fall_time, total_width, rise_time_samples, fall_time_samples, total_width_samples, peak_position, peak_height, ....

| Field | DType | Unit | Meaning |
| --- | --- | --- | --- |
| `rise_time` | `float32` | ns | Rise time from 10% to 90% of peak height (ns) |
| `fall_time` | `float32` | ns | Fall time from 90% to 10% of peak height (ns) |
| `total_width` | `float32` | ns | Total width from 10% rise to 10% fall (ns) |
| `rise_time_samples` | `float32` | samples | Rise time in sample counts |
| `fall_time_samples` | `float32` | samples | Fall time in sample counts |
| `total_width_samples` | `float32` | samples | Total width in sample counts |
| `peak_position` | `int64` | samples | Peak position as sample index |
| `peak_height` | `float32` | ADC counts | Peak height above baseline |
| `timestamp` | `int64` | ps | Event timestamp in picoseconds |
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

ctx.set_config(
    {
        "sampling_rate": 0.5,
        "rise_low": 0.1,
        "rise_high": 0.9,
        "fall_high": 0.9,
        "fall_low": 0.1,
        "interpolation": True,
    },
    plugin_name="waveform_width",
)
widths = ctx.get_data("run_001", "waveform_width")
rise_times_ns = widths["rise_time"]
fall_times_ns = widths["fall_time"]
```

示例使用 `run_id="run_001"` 和文档默认运行画像；真实数据路径与配置应以当前实验设置为准。

## Operational Notes

### Behavior

- CPU Waveform Width Plugin - 计算波形宽度特征
- **加速器**: CPU (NumPy) **功能**: 基于峰值检测结果计算波形的上升/下降时间
### Failure Modes

- `waveform_width` 的实际输入由 `resolve_depends_on(context, run_id)` 决定；默认画像之外的配置需要重新确认依赖是否可用。
- 动态依赖无法解析、所需配置不合法或上游产物缺失时，插件不会生成有效输出。
### Downstream Impact

没有声明直接的内置消费者。

## Maintenance

### Change Playbook

1. 保持 `provides`、依赖和输出字段语义稳定，或同步所有下游消费者。
2. 行为、配置或输出契约改变时升级插件 `version`。
3. 修改插件源码后重新生成 Auto、Agent 和 HTML 参考。
### Validation

```bash
waveform-docs generate plugins-agent --plugin waveform_width
waveform-docs check coverage --strict --fail-on-warning
```
