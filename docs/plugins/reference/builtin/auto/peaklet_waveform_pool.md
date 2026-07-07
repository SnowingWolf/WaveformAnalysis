# PeakletWaveformPoolPlugin

> Return flattened float32 peaklet waveform signal pool.

## Overview

| Property | Value |
|----------|-------|
| **Provides** | `peaklet_waveform_pool` |
| **Version** | `1.1.0` |
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
| `debug_numba` | `bool` | `False` | - | 调试 peaklet waveform Numba 路径；启用后 Numba 异常直接抛出。 |
| `log_waveform_diagnostics` | `bool` | `False` | - | 记录 peaklet waveform 构建统计和耗时诊断信息。 |
| `n_workers` | `int` | `1` | - | 并行处理的进程数。1=单进程，0=自动（使用 CPU 核心数-1），>1=指定进程数 |
| `parallel_threshold` | `int` | `5000` | - | 启用并行化的最小 peaklet 数量。少于此数量时使用单进程 |


## Output Schema

**Output Type**: `array`

| Field | Type | Units | Description |
|-------|------|-------|-------------|
| `value` | `float32` | - | - |

## Usage Example

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import PeakletWaveformPoolPlugin

# Create context and register plugin
ctx = Context(config={"data_root": "DAQ"})
ctx.register(PeakletWaveformPoolPlugin())

# Configure plugin (optional)
ctx.set_config({
    "use_filtered": False,
    "debug_numba": False,
    "log_waveform_diagnostics": False,
    "n_workers": 1,
    "parallel_threshold": 5000,
}, plugin_name="peaklet_waveform_pool")

# Get data
data = ctx.get_data("run_001", "peaklet_waveform_pool")
```

## Module

- **Module Path**: `waveform_analysis.core.plugins.builtin.peaks.peaklets`

---

*This documentation was auto-generated from plugin metadata.*
