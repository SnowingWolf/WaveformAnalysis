---
schema_version: 1
document_type: "plugin_reference"
profile: "agent"
provides: "peaklet_waveforms"
plugin_class: "PeakletWaveformPlugin"
module: "waveform_analysis.core.plugins.builtin.peaks.peaklets"
version: "1.4.0"
summary: "Build peaklet waveform index rows from records-backed hit_merged samples. Supports cross-record hits via component expansion."
depends_on: []
output_kind: "structured_array"
generated: true
---
# peaklet_waveforms

## Overview

Build peaklet waveform index rows from records-backed hit_merged samples. Supports cross-record hits via component expansion.
Build ragged waveform index rows for peaklets and cache the signal pool.

| Item | Value |
| --- | --- |
| Provides | `peaklet_waveforms` |
| Plugin Class | `PeakletWaveformPlugin` |
| Module | `waveform_analysis.core.plugins.builtin.peaks.peaklets` |
| Version | `1.4.0` |
| Category | 峰构建 |
| Accelerator | CPU (NumPy/SciPy) |
| Output Kind | `structured_array` |

| Dependency | Version Constraint | Resolution | Required Fields | Description |
| --- | --- | --- | --- | --- |
| - | - | - | - | No declared inputs. |
### How It Works


## Configuration

| Name | Type | Default | Unit | Tracked | Deprecated | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `use_filtered` | `bool` | `False` | - | yes | no | 是否使用 wave_pool_filtered 构建 peaklet 波形 |
| `clip_negative_signal` | `bool` | `False` | - | yes | no | 是否将 baseline/polarity 转换后的负信号裁剪为 0。默认保留负值。 |
| `debug_numba` | `bool` | `False` | - | yes | no | 调试 peaklet waveform Numba 路径；启用后 Numba 异常直接抛出。 |
| `log_waveform_diagnostics` | `bool` | `False` | - | yes | no | 记录 peaklet waveform 构建统计和耗时诊断信息。 |
| `n_workers` | `int` | `1` | - | yes | no | 并行处理的进程数。1=单进程，0=自动（使用 CPU 核心数-1），>1=指定进程数 |
| `parallel_threshold` | `int` | `5000` | - | yes | no | 启用并行化的最小 peaklet 数量。少于此数量时使用单进程 |
## Output

structured_array output with fields: peak_id, time_start, time_end, dt, wave_offset, wave_length.

| Field | DType | Unit | Meaning |
| --- | --- | --- | --- |
| `peak_id` | `int64` | - | Peaklet identifier, matching the row index in the peaklets table |
| `time_start` | `int64` | - | Absolute start time of the waveform slice (ps) |
| `time_end` | `int64` | - | Absolute end time of the waveform slice (ps) |
| `dt` | `int32` | - | Sample interval in nanoseconds |
| `wave_offset` | `int64` | - | Starting index in peaklet_waveform_pool |
| `wave_length` | `int32` | - | Number of samples in the waveform slice |
## Usage

### Minimal Example

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import PeakletWaveformPlugin

ctx = Context(config={"data_root": "DAQ"})
ctx.register(PeakletWaveformPlugin())
data = ctx.get_data("run_001", "peaklet_waveforms")
```

## Operational Notes

### Behavior

### Failure Modes

- Dependency data, configuration, or output contract validation may fail explicitly.
### Downstream Impact

Consumers: `peaklet_features`, `peaklet_waveform_pool`

## Maintenance

### Change Playbook

1. Keep `provides` and dependency semantics stable or update all consumers.
2. Bump `version` for behavior, configuration, or output contract changes.
3. Regenerate auto, agent, and web references after metadata changes.
### Validation

```bash
waveform-docs generate plugins-agent --plugin peaklet_waveforms
waveform-docs check coverage --strict --fail-on-warning
```
