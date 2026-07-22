# PeakletWaveformPlugin

> Build peaklet waveform index rows from records-backed hit_merged samples. Supports cross-record hits via component expansion.

## Overview

| Property | Value |
|----------|-------|
| **Provides** | `peaklet_waveforms` |
| **Version** | `1.3.1` |
| **Category** | 波形处理 |
| **Accelerator** | CPU (NumPy/SciPy) |
| **Streaming** | No |
| **Side Effect** | No |

## Dependencies

This plugin has no dependencies.

## Configuration Options

| Option | Type | Default | Units | Description |
|--------|------|---------|-------|-------------|
| `use_filtered` | `bool` | `False` | - | 是否使用 wave_pool_filtered 构建 peaklet 波形 |
| `clip_negative_signal` | `bool` | `False` | - | 是否将 baseline/polarity 转换后的负信号裁剪为 0。默认保留负值。 |
| `debug_numba` | `bool` | `False` | - | 调试 peaklet waveform Numba 路径；启用后 Numba 异常直接抛出。 |
| `log_waveform_diagnostics` | `bool` | `False` | - | 记录 peaklet waveform 构建统计和耗时诊断信息。 |
| `n_workers` | `int` | `1` | - | 并行处理的进程数。1=单进程，0=自动（使用 CPU 核心数-1），>1=指定进程数 |
| `parallel_threshold` | `int` | `5000` | - | 启用并行化的最小 peaklet 数量。少于此数量时使用单进程 |


## Output Schema

**Output Type**: `structured_array`

| Field | Type | Units | Description |
|-------|------|-------|-------------|
| `peak_id` | `int64` | - | - |
| `time_start` | `int64` | - | - |
| `time_end` | `int64` | - | - |
| `dt` | `int32` | - | - |
| `wave_offset` | `int64` | - | - |
| `wave_length` | `int32` | - | - |

## Usage Example

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import PeakletWaveformPlugin

# Create context and register plugin
ctx = Context(config={"data_root": "DAQ"})
ctx.register(PeakletWaveformPlugin())

# Configure plugin (optional)
ctx.set_config({
    "use_filtered": False,
    "clip_negative_signal": False,
    "debug_numba": False,
}, plugin_name="peaklet_waveforms")

# Get data
data = ctx.get_data("run_001", "peaklet_waveforms")
```

## Module

- **Module Path**: `waveform_analysis.core.plugins.builtin.peaks.peaklets`

---

*This documentation was auto-generated from plugin metadata.*
