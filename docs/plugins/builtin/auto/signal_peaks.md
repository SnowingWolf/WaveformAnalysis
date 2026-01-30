# SignalPeaksPlugin

> Detect peaks in filtered waveforms and extract peak features.

## Overview

| Property | Value |
|----------|-------|
| **Provides** | `signal_peaks` |
| **Version** | `1.0.2` |
| **Category** | 特征提取 |
| **Accelerator** | CPU (NumPy/SciPy) |
| **Streaming** | No |
| **Side Effect** | No |

## Dependencies

This plugin depends on the following data:

- [`filtered_waveforms`](filtered_waveforms.md)
- [`st_waveforms`](st_waveforms.md)

## Configuration Options

| Option | Type | Default | Units | Description |
|--------|------|---------|-------|-------------|
| `use_derivative` | `bool` | `True` | - | 是否使用一阶导数进行峰值检测（True: 检测导数峰值, False: 检测波形峰值） |
| `height` | `float` | `30.0` | - | 峰值的最小高度阈值 |
| `distance` | `int` | `2` | - | 峰值之间的最小距离（采样点数） |
| `prominence` | `float` | `0.7` | - | 峰值的最小显著性（prominence） |
| `width` | `int` | `4` | - | 峰值的最小宽度（采样点数） |
| `threshold` | `any` | `None` | - | 峰值的阈值条件（可选） |
| `height_method` | `str` | `diff` | - | 峰高计算方法: 'diff' (积分差分) 或 'minmax' (最大最小值差) |
| `sampling_interval_ns` | `float` | `2.0` | - | 采样间隔（纳秒），用于计算全局时间戳。默认 2.0 ns |


## Output Schema

**Output Type**: `structured_array`

| Field | Type | Units | Description |
|-------|------|-------|-------------|
| `position` | `int64` | - | - |
| `height` | `float32` | - | - |
| `integral` | `float32` | - | - |
| `edge_start` | `float32` | - | - |
| `edge_end` | `float32` | - | - |
| `timestamp` | `int64` | - | - |
| `channel` | `int16` | - | - |
| `event_index` | `int64` | - | - |

## Usage Example

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import SignalPeaksPlugin

# Create context and register plugin
ctx = Context(config={"data_root": "DAQ"})
ctx.register(SignalPeaksPlugin())

# Configure plugin (optional)
ctx.set_config({
    "use_derivative": True,
    "height": 30.0,
    "distance": 2,
}, plugin_name="signal_peaks")

# Get data
data = ctx.get_data("run_001", "signal_peaks")
```

## Module

- **Module Path**: `waveform_analysis.core.plugins.builtin.cpu.peak_finding`

---

*This documentation was auto-generated from plugin metadata.*