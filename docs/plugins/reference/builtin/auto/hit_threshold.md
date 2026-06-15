# ThresholdHitPlugin

> Threshold-only hit detector with THRESHOLD_HIT_DTYPE output.

## Overview

| Property | Value |
|----------|-------|
| **Provides** | `hit_threshold` |
| **Version** | `1.2.0` |
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
| `left_extension` | `int` | `2` | - | Hit 左侧扩展点数 |
| `right_extension` | `int` | `2` | - | Hit 右侧扩展点数 |
| `dt` | `int` | `None` | - | 采样间隔（ns）。仅在输入数据缺少 dt 字段时作为兼容补充。 |
| `channel_config` | `dict` | `None` | - | 按 (board, channel) 的插件通道覆盖配置，可覆盖 threshold。 |
| `backend` | `str` | `auto` | - | Hit finding backend: auto|numba|ragged。auto 对 records 在达到 parallel_min_records 后尝试 numba，否则使用 ragged。 |
| `chunk_parallel` | `bool` | `True` | - | 是否对 records ragged numba 后端启用 chunk 级线程并行。 |
| `n_workers` | `int` | `0` | - | records ragged chunk 并行 worker 数；<=0 表示自动。 |
| `parallel_chunk_size` | `int` | `50000` | - | records ragged chunk 并行大小（每个任务处理的 record 数）。 |
| `parallel_min_records` | `int` | `50000` | - | 触发 records ragged chunk 并行的最小 record 数。 |
| `streaming_chunk_size` | `int` | `10000` | - | 流式处理时的 chunk 大小（仅对 RecordsBundleRef 生效） |
| `asymmetry_cut_enabled` | `bool` | `False` | - | 是否在 records 路径的 hit 查找前应用 records_asymmetry_mask。 |
| `channel_role_cut_enabled` | `bool` | `False` | - | 是否在 records 路径的 hit 查找前应用 records_detector_mask。 |


## Output Schema

**Output Type**: `structured_array`

| Field | Type | Units | Description |
|-------|------|-------|-------------|
| `position` | `int64` | - | - |
| `edge_start` | `int32` | - | - |
| `edge_end` | `int32` | - | - |
| `width` | `float32` | - | - |
| `dt` | `int32` | - | - |
| `timestamp` | `int64` | - | - |
| `board` | `int16` | - | - |
| `channel` | `int16` | - | - |
| `record_id` | `int64` | - | - |

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
