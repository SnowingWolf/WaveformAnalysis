# WavePoolFilteredPlugin

> Build filtered wave_pool from records-backed raw waveforms.

## Overview

| Property | Value |
|----------|-------|
| **Provides** | `wave_pool_filtered` |
| **Version** | `0.2.0` |
| **Category** | 波形处理 |
| **Accelerator** | CPU (NumPy/SciPy) |
| **Streaming** | No |
| **Side Effect** | No |

## Dependencies

This plugin depends on the following data:

- [`records`](records.md)
- [`wave_pool`](wave_pool.md)

## Configuration Options

| Option | Type | Default | Units | Description |
|--------|------|---------|-------|-------------|
| `filter_type` | `str` | `SG` | - | 滤波器类型: 'BW' 或 'SG' |
| `lowcut` | `float` | `0.1` | - | BW 低频截止 |
| `highcut` | `float` | `0.5` | - | BW 高频截止 |
| `fs` | `float` | `0.5` | - | BW 采样率（GHz） |
| `filter_order` | `int` | `4` | - | BW 阶数 |
| `sg_window_size` | `int` | `11` | - | SG 窗口大小（奇数） |
| `sg_poly_order` | `int` | `2` | - | SG 多项式阶数 |
| `max_workers` | `int` | `None` | - | 并行工作线程数；None 使用 CPU 核心数，1 或 0 禁用并行 |
| `batch_size` | `int` | `0` | - | 每批次记录数（0 表示不分批，整个通道一次处理） |
| `channel_config` | `dict` | `None` | - | 按 (board, channel) 的插件通道覆盖配置，可覆盖滤波参数 |


## Output Schema

**Output Type**: `array`

| Field | Type | Units | Description |
|-------|------|-------|-------------|
| `value` | `float32` | - | - |

超短波形会在 SG/BW 路径下安全回退到原始波形，以避免无效窗口或 `padlen` 异常。

## Usage Example

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import WavePoolFilteredPlugin

# Create context and register plugin
ctx = Context(config={"data_root": "DAQ"})
ctx.register(WavePoolFilteredPlugin())

# Configure plugin (optional)
ctx.set_config({
    "filter_type": 'SG',
    "lowcut": 0.1,
    "highcut": 0.5,
}, plugin_name="wave_pool_filtered")

# Get data
data = ctx.get_data("run_001", "wave_pool_filtered")
```

## Module

- **Module Path**: `waveform_analysis.core.plugins.builtin.cpu.records`

---

*This documentation was auto-generated from plugin metadata.*
