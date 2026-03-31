# ThresholdHitPlugin

> Threshold-only hit detector with THRESHOLD_HIT_DTYPE output.

## Overview

| Property | Value |
|----------|-------|
| **Provides** | `hit_threshold` |
| **Version** | `0.10.0` |
| **Category** | 特征提取 |
| **Accelerator** | CPU (NumPy/SciPy) |
| **Streaming** | No |
| **Side Effect** | No |

## Dependencies

This plugin has no dependencies.

## Configuration Options

| Option | Type | Default | Units | Description |
|--------|------|---------|-------|-------------|
| `threshold` | `float` | `10.0` | - | Hit 检测阈值 |
| `use_filtered` | `bool` | `False` | - | 是否使用 filtered_waveforms（需要先注册 FilteredWaveformsPlugin） |
| `wave_source` | `str` | `auto` | - | 波形数据源: auto|records|st_waveforms|filtered_waveforms |
| `polarity` | `str` | `negative` | - | 信号极性：negative 表示 baseline-wave；positive 表示 wave-baseline |
| `left_extension` | `int` | `2` | - | Hit 左侧扩展点数 |
| `right_extension` | `int` | `2` | - | Hit 右侧扩展点数 |
| `dt` | `int` | `None` | - | 采样间隔（ns）。仅在输入数据缺少 dt 字段时作为兼容补充。 |
| `channel_config` | `dict` | `None` | - | 按 (board, channel) 的插件通道覆盖配置，可覆盖 polarity/threshold。 |


## Output Schema

**Output Type**: `structured_array`

| Field | Type | Units | Description |
|-------|------|-------|-------------|
| `position` | `int64` | - | - |
| `height` | `float32` | - | - |
| `integral` | `float32` | - | - |
| `edge_start` | `float32` | - | - |
| `edge_end` | `float32` | - | - |
| `width` | `float32` | - | - |
| `dt` | `int32` | - | - |
| `rise_time` | `float32` | - | - |
| `fall_time` | `float32` | - | - |
| `timestamp` | `int64` | - | - |
| `board` | `int16` | - | - |
| `channel` | `int16` | - | - |
| `record_id` | `int64` | - | - |
| `record_sample_start` | `int32` | - | - |
| `record_sample_end` | `int32` | - | - |
| `wave_pool_start` | `int64` | - | - |
| `wave_pool_end` | `int64` | - | - |

## Usage Example

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import ThresholdHitPlugin

# Create context and register plugin
ctx = Context(config={"data_root": "DAQ"})
ctx.register(ThresholdHitPlugin())

# Configure plugin (optional)
ctx.set_config({
    "threshold": 10.0,
    "use_filtered": False,
    "wave_source": 'auto',
}, plugin_name="hit_threshold")

# Get data
data = ctx.get_data("run_001", "hit_threshold")
```

## Module

- **Module Path**: `waveform_analysis.core.plugins.builtin.cpu.hit_finder`

---

*This documentation was auto-generated from plugin metadata.*
