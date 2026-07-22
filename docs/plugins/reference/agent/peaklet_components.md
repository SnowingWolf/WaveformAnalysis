---
schema_version: 1
document_type: "plugin_reference"
profile: "agent"
provides: "peaklet_components"
plugin_class: "PeakletComponentsPlugin"
module: "waveform_analysis.core.plugins.builtin.peaks.peaklets"
version: "1.4.0"
summary: "Return per-peaklet component hit_merged indices."
depends_on: ["hit_merged"]
output_kind: "structured_array"
generated: true
---
# peaklet_components

## Overview

Return per-peaklet component hit_merged indices.

| Item | Value |
| --- | --- |
| Provides | `peaklet_components` |
| Plugin Class | `PeakletComponentsPlugin` |
| Module | `waveform_analysis.core.plugins.builtin.peaks.peaklets` |
| Version | `1.4.0` |
| Category | 特征提取 |
| Accelerator | CPU (NumPy/SciPy) |
| Output Kind | `structured_array` |

| Dependency | Version Constraint | Resolution | Required Fields | Description |
| --- | --- | --- | --- | --- |
| `hit_merged` | - | declared | - | - |
## Configuration

| Name | Type | Default | Unit | Tracked | Deprecated | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `time_window_ns` | `float` | `100.0` | - | yes | no | 跨通道 peaklet 合并时间窗口 |
| `max_total_width_ns` | `float` | `10000.0` | - | yes | no | peaklet 最大总宽度 |
| `dt` | `int` | `None` | - | yes | no | 保留兼容配置；优先使用输入 hit_merged 的 dt |
## Output

| Field | DType | Unit | Meaning |
| --- | --- | --- | --- |
| `peak_id` | `int64` | - | - |
| `merged_index` | `int64` | - | - |
## Usage

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import PeakletComponentsPlugin

ctx = Context(config={"data_root": "DAQ"})
ctx.register(PeakletComponentsPlugin())
data = ctx.get_data("run_001", "peaklet_components")
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
waveform-docs generate plugins-agent --plugin peaklet_components
waveform-docs check coverage --strict --fail-on-warning
```
