---
schema_version: 1
document_type: "plugin_reference"
profile: "agent"
provides: "hit_grouped"
plugin_class: "HitGroupedPlugin"
module: "waveform_analysis.core.plugins.builtin.hit.hit_grouped"
version: "0.5.0"
summary: "Group merged hits across channels into event-level coincidence windows."
depends_on: ["hit_merged", "hit_merged_components", "hit_threshold"]
output_kind: "dataframe"
generated: true
---
# hit_grouped

## Overview

Group merged hits across channels into event-level coincidence windows.

| Item | Value |
| --- | --- |
| Provides | `hit_grouped` |
| Plugin Class | `HitGroupedPlugin` |
| Module | `waveform_analysis.core.plugins.builtin.hit.hit_grouped` |
| Version | `0.5.0` |
| Category | 特征提取 |
| Accelerator | CPU (NumPy/SciPy) |
| Output Kind | `dataframe` |

| Dependency | Version Constraint | Resolution | Required Fields | Description |
| --- | --- | --- | --- | --- |
| `hit_merged` | - | declared | - | - |
| `hit_merged_components` | - | declared | - | - |
| `hit_threshold` | - | declared | - | - |
## Configuration

| Name | Type | Default | Unit | Tracked | Deprecated | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `time_window_ns` | `float` | `100.0` | - | yes | no | Maximum absolute time separation in nanoseconds for grouping hits. |
| `dt` | `int` | `None` | - | yes | no | 采样间隔（ns）。仅在输入 hit_merged 缺少 dt 字段时作为兼容补充。 |
## Output

| Field | DType | Unit | Meaning |
| --- | --- | --- | --- |
| - | `dataframe` | - | Group merged hits across channels into event-level coincidence windows. |
## Usage

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import HitGroupedPlugin

ctx = Context(config={"data_root": "DAQ"})
ctx.register(HitGroupedPlugin())
data = ctx.get_data("run_001", "hit_grouped")
```

## Operational Notes

### Behavior

- Hit Grouped Plugin - Hit 分组插件

**加速器**: CPU (NumPy/Numba)
**功能**: 按绝对 hit 窗口将多通道的 merged hits 分组为事件级符合窗口

本插件将 hit_merged 数据按时间窗口分组，用于事件级分析。
已标记为 deprecated，推荐使用新的 S1-S2 配对工作流。
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
waveform-docs generate plugins-agent --plugin hit_grouped
waveform-docs check coverage --strict --fail-on-warning
```
