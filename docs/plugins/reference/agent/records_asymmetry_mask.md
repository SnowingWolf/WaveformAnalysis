---
schema_version: 2
document_type: "plugin_reference"
profile: "agent"
provides: "records_asymmetry_mask"
plugin_class: "RecordsAsymmetryMaskPlugin"
module: "waveform_analysis.core.plugins.builtin.records_asymmetry_mask.plugin"
version: "0.2.0"
summary: "Bool mask for waveform asymmetry selection."
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
source_fingerprint: "89b3544e76e327d0ba8bb9badb1a7edcd689482fd5df2d2d521a320d4686c625"
generated: true
---
# records_asymmetry_mask

## Overview

Bool mask for waveform asymmetry selection.
Return a bool mask aligned with the original records array.

| Item | Value |
| --- | --- |
| Provides | `records_asymmetry_mask` |
| Plugin Class | `RecordsAsymmetryMaskPlugin` |
| Module | `waveform_analysis.core.plugins.builtin.records_asymmetry_mask.plugin` |
| Version | `0.2.0` |
| Category | 记录处理 |
| Output Container | `array` |
| Execution Mode | `static` |
| Save Policy | `always` |
| Uses Run Config | no |
| Timeout | `none` |
| Side Effect | no |
| Narrative Source | `source` |
| Source Fingerprint | `89b3544e76e327d0ba8bb9badb1a7edcd689482fd5df2d2d521a320d4686c625` |

### Dependencies

默认文档画像：`declared`。

| Dependency | Version Constraint | Resolution | Required Fields | Description |
| --- | --- | --- | --- | --- |
| `records` | - | declared | - | Build records (event index table) from the shared internal records bundle. |
| `wave_pool` | - | declared | - | Build wave_pool from the shared internal records bundle. |
### How It Works

1. Return a bool mask aligned with the original records array.

## Configuration

| Name | Type | Default | Unit | Tracked | Deprecated | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `asymmetry_cut_min` | `float` | `0.7` | - | yes | no | Keep records with asymmetry >= this value. |
| `asymmetry_parallel` | `bool` | `True` | - | no | no | Use Numba prange parallel loop. |
| `asymmetry_chunk_size` | `int` | `200000` | - | no | no | Number of records processed per Numba call. |
| `asymmetry_num_threads` | `int` | `0` | - | no | no | Numba thread count. <=0 keeps current Numba default. |
| `asymmetry_polarity_mode` | `str` | `auto` | - | yes | no | Polarity handling mode: 'auto' (extract from records['polarity']), 'negative' (baseline - w_min), 'positive' (w_max - baseline). |
## Output

array output with fields: value.

| Field | DType | Unit | Meaning |
| --- | --- | --- | --- |
| `value` | `bool` | None | Boolean mask: True for records passing waveform asymmetry selection |
## Usage

### Minimal Example

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins import profiles

ctx = Context(config={"data_root": "DAQ", "daq_adapter": "vx2730"})
ctx.register(*profiles.cpu_default())
result = ctx.get_data("run_001", "records_asymmetry_mask")
```

示例使用 `run_id="run_001"` 和文档默认运行画像；真实数据路径与配置应以当前实验设置为准。

## Operational Notes

### Behavior

- RecordsAsymmetryMaskPlugin 类实现 - 基于波形的对称性筛选掩码。
### Failure Modes

- 任一声明依赖（`records`, `wave_pool`）缺失或字段不符合输入契约时，执行会失败。
- 配置校验或输出 schema 校验失败时，结果不会被视为有效插件产物。
### Downstream Impact

直接消费者：`hit_threshold`、`records_detector_mask`、`records_veto_mask`
## Maintenance

### Change Playbook

1. 保持 `provides`、依赖和输出字段语义稳定，或同步所有下游消费者。
2. 行为、配置或输出契约改变时升级插件 `version`。
3. 修改插件源码后重新生成 Auto、Agent 和 HTML 参考。
### Validation

```bash
waveform-docs generate plugins-agent --plugin records_asymmetry_mask
waveform-docs check coverage --strict --fail-on-warning
```
