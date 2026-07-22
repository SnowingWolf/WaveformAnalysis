---
schema_version: 1
document_type: "plugin_reference"
profile: "agent"
provides: "peaklets"
plugin_class: "PeakletPlugin"
module: "waveform_analysis.core.plugins.builtin.peaks.peaklets"
version: "1.2.0"
summary: "Build lightweight cross-channel peaklets from hit_merged intervals."
depends_on: ["hit_merged", "peaklet_components"]
output_kind: "structured_array"
generated: true
---
# peaklets

## Overview

Build lightweight cross-channel peaklets from hit_merged intervals.

| Item | Value |
| --- | --- |
| Provides | `peaklets` |
| Plugin Class | `PeakletPlugin` |
| Module | `waveform_analysis.core.plugins.builtin.peaks.peaklets` |
| Version | `1.2.0` |
| Category | 特征提取 |
| Accelerator | CPU (NumPy/SciPy) |
| Output Kind | `structured_array` |

| Dependency | Version Constraint | Resolution | Required Fields | Description |
| --- | --- | --- | --- | --- |
| `hit_merged` | - | declared | - | - |
| `peaklet_components` | - | declared | - | - |
## Configuration

| Name | Type | Default | Unit | Tracked | Deprecated | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `time_window_ns` | `float` | `100.0` | - | yes | no | 跨通道 peaklet 合并时间窗口 |
| `max_total_width_ns` | `float` | `10000.0` | - | yes | no | peaklet 最大总宽度 |
| `dt` | `int` | `None` | - | yes | no | 保留兼容配置；优先使用输入 hit_merged 的 dt |
## Output

| Field | DType | Unit | Meaning |
| --- | --- | --- | --- |
| `time_start` | `int64` | - | - |
| `time_end` | `int64` | - | - |
| `center_time` | `int64` | - | - |
| `n_hits` | `int32` | - | - |
| `n_channels` | `int32` | - | - |
| `component_offset` | `int64` | - | - |
| `component_count` | `int32` | - | - |
## Usage

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import PeakletPlugin

ctx = Context(config={"data_root": "DAQ"})
ctx.register(PeakletPlugin())
data = ctx.get_data("run_001", "peaklets")
```

## Operational Notes

### Behavior

- Peaklet clustering, ragged waveforms, features, and final peaks.
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
waveform-docs generate plugins-agent --plugin peaklets
waveform-docs check coverage --strict --fail-on-warning
```
