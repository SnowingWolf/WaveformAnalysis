---
schema_version: 1
document_type: "plugin_reference"
profile: "agent"
provides: "waveform_width"
plugin_class: "WaveformWidthPlugin"
module: "waveform_analysis.core.plugins.builtin.cpu.waveform_width"
version: "3.0.0"
summary: "Calculate rise/fall time based on peak detection results."
depends_on: []
output_kind: "structured_array"
generated: true
---
# waveform_width

## Overview

Calculate rise/fall time based on peak detection results.

| Item | Value |
| --- | --- |
| Provides | `waveform_width` |
| Plugin Class | `WaveformWidthPlugin` |
| Module | `waveform_analysis.core.plugins.builtin.cpu.waveform_width` |
| Version | `3.0.0` |
| Category | 波形处理 |
| Accelerator | CPU (NumPy/SciPy) |
| Output Kind | `structured_array` |

| Dependency | Version Constraint | Resolution | Required Fields | Description |
| --- | --- | --- | --- | --- |
| - | - | - | - | - |
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

| Field | DType | Unit | Meaning |
| --- | --- | --- | --- |
| `rise_time` | `float32` | - | - |
| `fall_time` | `float32` | - | - |
| `total_width` | `float32` | - | - |
| `rise_time_samples` | `float32` | - | - |
| `fall_time_samples` | `float32` | - | - |
| `total_width_samples` | `float32` | - | - |
| `peak_position` | `int64` | - | - |
| `peak_height` | `float32` | - | - |
| `timestamp` | `int64` | - | - |
| `board` | `int16` | - | - |
| `channel` | `int16` | - | - |
| `record_id` | `int64` | - | - |
## Usage

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import WaveformWidthPlugin

ctx = Context(config={"data_root": "DAQ"})
ctx.register(WaveformWidthPlugin())
data = ctx.get_data("run_001", "waveform_width")
```

## Operational Notes

### Behavior

- CPU Waveform Width Plugin - 计算波形宽度特征

**加速器**: CPU (NumPy)
**功能**: 基于峰值检测结果计算波形的上升/下降时间

本插件依赖 HitFinderPlugin 的峰值检测结果，计算每个峰值的：
1. 上升时间 (Rise Time): 从 10% 到 90% 峰值高度的时间
2. 下降时间 (Fall Time): 从 90% 到 10% 峰值高度的时间
3. 总宽度: 从上升起点到下降终点的时间

支持使用原始波形或滤波后的波形进行计算。
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
waveform-docs generate plugins-agent --plugin waveform_width
waveform-docs check coverage --strict --fail-on-warning
```
