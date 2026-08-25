---
schema_version: 2
document_type: "plugin_reference"
profile: "agent"
provides: "wave_pool_filtered"
plugin_class: "WavePoolFilteredPlugin"
module: "waveform_analysis.core.plugins.builtin.wave_pool_filtered.plugin"
version: "3.0.0"
summary: "Build filtered wave_pool from records-backed raw waveforms."
depends_on: ["records", "wave_pool"]
declared_depends_on: ["records", "wave_pool"]
resolved_depends_on: ["records", "wave_pool"]
dependency_profile: "declared"
dependency_profile_values: {}
dependency_config_keys: []
output_kind: "array"
execution_kind: "static"
narrative_source: "source"
narrative_source_reason: null
source_fingerprint: "b9b393d7a99479be125b3a38c9024f8aa353b15ad155e04aff92930648194d38"
generated: true
---
# wave_pool_filtered

## Overview

Build filtered wave_pool from records-backed raw waveforms.
Build a filtered wave_pool aligned to the existing records layout.

| Item | Value |
| --- | --- |
| Provides | `wave_pool_filtered` |
| Plugin Class | `WavePoolFilteredPlugin` |
| Module | `waveform_analysis.core.plugins.builtin.wave_pool_filtered.plugin` |
| Version | `3.0.0` |
| Category | 波形处理 |
| Output Container | `array` |
| Execution Mode | `static` |
| Save Policy | `always` |
| Uses Run Config | no |
| Timeout | `none` |
| Side Effect | no |
| Narrative Source | `source` |
| Source Fingerprint | `b9b393d7a99479be125b3a38c9024f8aa353b15ad155e04aff92930648194d38` |

### Dependencies

默认文档画像：`declared`。

| Dependency | Version Constraint | Resolution | Required Fields | Description |
| --- | --- | --- | --- | --- |
| `records` | - | declared | - | Build records (event index table) from the shared internal records bundle. |
| `wave_pool` | - | declared | - | Build wave_pool from the shared internal records bundle. |
### How It Works

1. Build a filtered wave_pool aligned to the existing records layout.

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
from waveform_analysis.core.plugins import profiles

ctx = Context(config={"data_root": "DAQ", "daq_adapter": "vx2730"})
ctx.register(*profiles.cpu_default())
result = ctx.get_data("run_001", "wave_pool_filtered")
```

示例使用 `run_id="run_001"` 和文档默认运行画像；真实数据路径与配置应以当前实验设置为准。

## Operational Notes

### Behavior

- WavePoolFilteredPlugin 类实现 - 构建与 records 对齐的滤波波形池。
### Failure Modes

- 任一声明依赖（`records`, `wave_pool`）缺失或字段不符合输入契约时，执行会失败。
- 配置校验或输出 schema 校验失败时，结果不会被视为有效插件产物。
### Downstream Impact

没有声明直接的内置消费者。

## Maintenance

### Change Playbook

1. 保持 `provides`、依赖和输出字段语义稳定，或同步所有下游消费者。
2. 行为、配置或输出契约改变时升级插件 `version`。
3. 修改插件源码后重新生成 Auto、Agent 和 HTML 参考。
### Validation

```bash
waveform-docs generate plugins-agent --plugin wave_pool_filtered
waveform-docs check coverage --strict --fail-on-warning
```
