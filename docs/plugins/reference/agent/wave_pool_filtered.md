---
schema_version: 1
document_type: "plugin_reference"
profile: "agent"
provides: "wave_pool_filtered"
plugin_class: "WavePoolFilteredPlugin"
module: "waveform_analysis.core.plugins.builtin.cpu.records"
version: "3.0.0"
summary: "Build filtered wave_pool from records-backed raw waveforms."
depends_on: ["records", "wave_pool"]
output_kind: "array"
generated: true
---
# wave_pool_filtered

## Overview

Build filtered wave_pool from records-backed raw waveforms.
| Item | Value |
| --- | --- |
| Provides | `wave_pool_filtered` |
| Plugin Class | `WavePoolFilteredPlugin` |
| Module | `waveform_analysis.core.plugins.builtin.cpu.records` |
| Version | `3.0.0` |
| Category | 波形处理 |
| Accelerator | CPU (NumPy/SciPy) |
| Output Kind | `array` |

| Dependency | Version Constraint | Resolution | Required Fields | Description |
| --- | --- | --- | --- | --- |
| `records` | - | declared | - | Build records (event index table) from the shared internal records bundle. |
| `wave_pool` | - | declared | - | Build wave_pool from the shared internal records bundle. |
### How It Works


## Configuration

| Name | Type | Default | Unit | Tracked | Deprecated | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `filter_type` | `str` | `SG` | - | yes | no | 滤波器类型: 'BW' 或 'SG' |
| `lowcut` | `float` | `0.1` | - | yes | no | BW 低频截止 |
| `highcut` | `float` | `0.5` | - | yes | no | BW 高频截止 |
| `fs` | `float` | `0.5` | - | yes | no | BW 采样率（GHz） |
| `filter_order` | `int` | `4` | - | yes | no | BW 阶数 |
| `sg_window_size` | `int` | `11` | - | yes | no | SG 窗口大小（奇数） |
| `sg_poly_order` | `int` | `2` | - | yes | no | SG 多项式阶数 |
| `max_workers` | `int` | `None` | - | yes | no | 并行工作线程数；None 使用 CPU 核心数，1 或 0 禁用并行 |
| `batch_size` | `int` | `0` | - | yes | no | 每批次记录数（0 表示不分批，整个通道一次处理） |
| `channel_config` | `dict` | `None` | - | yes | no | 按 (board, channel) 的插件通道覆盖配置，可覆盖滤波参数。 |
## Output

array output with fields: value.

| Field | DType | Unit | Meaning |
| --- | --- | --- | --- |
| `value` | `float32` | ADC counts | Flattened float32 filtered sample value |
## Usage

### Minimal Example

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import WavePoolFilteredPlugin

ctx = Context(config={"data_root": "DAQ"})
ctx.register(WavePoolFilteredPlugin())
data = ctx.get_data("run_001", "wave_pool_filtered")
```

## Operational Notes

### Behavior

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
waveform-docs generate plugins-agent --plugin wave_pool_filtered
waveform-docs check coverage --strict --fail-on-warning
```
