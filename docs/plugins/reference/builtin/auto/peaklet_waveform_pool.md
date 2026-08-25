---
schema_version: 2
document_type: "plugin_reference"
profile: "auto"
provides: "peaklet_waveform_pool"
plugin_class: "PeakletWaveformPoolPlugin"
module: "waveform_analysis.core.plugins.builtin.peaklet_waveform_pool.plugin"
version: "3.0.0"
summary: "Return the flattened float32 signal pool paired with peaklet_waveforms. Configure waveform construction on peaklet_waveforms."
depends_on: ["peaklet_waveforms"]
declared_depends_on: ["peaklet_waveforms"]
resolved_depends_on: ["peaklet_waveforms"]
dependency_profile: "declared"
dependency_profile_values: {}
dependency_config_keys: []
output_kind: "array"
execution_kind: "static"
narrative_source: "source"
narrative_source_reason: null
source_fingerprint: "dbf955e5ddc3320a0f8c56d971b05e9b0fa4226f22c1f449d7c19a18fd3855e5"
generated: true
---
# peaklet_waveform_pool

## Overview

Return the flattened float32 signal pool paired with peaklet_waveforms. Configure waveform construction on peaklet_waveforms.
Return the pool produced alongside the canonical peaklet waveform index.

| Item | Value |
| --- | --- |
| Provides | `peaklet_waveform_pool` |
| Plugin Class | `PeakletWaveformPoolPlugin` |
| Module | `waveform_analysis.core.plugins.builtin.peaklet_waveform_pool.plugin` |
| Version | `3.0.0` |
| Category | 峰构建 |
| Output Container | `array` |
| Execution Mode | `static` |
| Save Policy | `always` |
| Uses Run Config | no |
| Timeout | `none` |
| Side Effect | no |
| Narrative Source | `source` |
| Source Fingerprint | `dbf955e5ddc3320a0f8c56d971b05e9b0fa4226f22c1f449d7c19a18fd3855e5` |

### Dependencies

默认文档画像：`declared`。

| Dependency | Version Constraint | Resolution | Required Fields | Description |
| --- | --- | --- | --- | --- |
| `peaklet_waveforms` | - | declared | - | Build peaklet waveform index rows from records-backed hit_merged samples. Supports cross-record hits via component expansion. |
### How It Works

1. Return the pool produced alongside the canonical peaklet waveform index.

## Configuration

| Name | Type | Default | Unit | Tracked | Deprecated | Description |
| --- | --- | --- | --- | --- | --- | --- |
| - | - | - | - | - | - | 此插件没有插件级配置。 |
## Output

array output with fields: value.

| Field | DType | Unit | Meaning |
| --- | --- | --- | --- |
| `value` | `float32` | ADC counts | Flattened float32 waveform sample for peaklet waveform slices |
## Usage

### Minimal Example

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.plugin_sets import (
    plugins_hit,
    plugins_io,
    plugins_waveform,
)

ctx = Context(config={"data_root": "DAQ"})
ctx.register(*plugins_io(), *plugins_waveform(), *plugins_hit())

# Construction options belong to the canonical waveform producer.
ctx.set_config(
    {"use_filtered": False, "clip_negative_signal": False},
    plugin_name="peaklet_waveforms",
)
pool = ctx.get_data("run_001", "peaklet_waveform_pool")
```

示例使用 `run_id="run_001"` 和文档默认运行画像；真实数据路径与配置应以当前实验设置为准。

### Downstream Consumers

- `peaklet_features`
