**导航**: [文档中心](../../README.md) > [插件详解](../README.md) > [builtin](README.md) > WaveformWidthPlugin 使用指南

# WaveformWidthPlugin 使用指南

## 概述

`WaveformWidthPlugin` 是一个用于计算波形上升/下降时间的插件。它依赖 `SignalPeaksPlugin` 的峰值检测结果，计算每个峰值的时间特征。

## 功能特性

- **上升时间 (Rise Time)**: 从 10% 峰高到 90% 峰高的时间
- **下降时间 (Fall Time)**: 从 90% 峰高到 10% 峰高的时间
- **总宽度 (Total Width)**: 从上升起点到下降终点的总时间
- **支持滤波波形**: 可选择使用原始波形或滤波后的波形进行计算
- **线性插值**: 可选的插值功能提高时间计算精度

## 依赖关系

```
WaveformsPlugin → StWaveformsPlugin → FilteredWaveformsPlugin (可选)
                                    ↓
                              SignalPeaksPlugin → WaveformWidthPlugin
```

## 快速开始

### 基本使用

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import (
    WaveformsPlugin,
    StWaveformsPlugin,
    SignalPeaksPlugin,
    WaveformWidthPlugin,
)

# 创建 Context 并注册插件
ctx = Context(config={"data_root": "DAQ", "daq_adapter": "vx2730"})

ctx.register(WaveformsPlugin())
ctx.register(StWaveformsPlugin())
ctx.register(SignalPeaksPlugin())
ctx.register(WaveformWidthPlugin())

# 配置参数
ctx.set_config({
    "sampling_rate": 0.5,  # 0.5 GHz 采样率
    "rise_low": 0.1,       # 10% 阈值
    "rise_high": 0.9,      # 90% 阈值
    "interpolation": True, # 使用插值
}, plugin_name="waveform_width")

# 获取数据
widths = ctx.get_data("run_001", "waveform_width")

# 分析结果
for ch_idx, ch_widths in enumerate(widths):
    print(f"通道 {ch_idx}:")
    print(f"  平均上升时间: {np.mean(ch_widths['rise_time']):.2f} ns")
    print(f"  平均下降时间: {np.mean(ch_widths['fall_time']):.2f} ns")
```

### 使用滤波波形

```python
from waveform_analysis.core.plugins.builtin.cpu import FilteredWaveformsPlugin

# 注册滤波插件
ctx.register(FilteredWaveformsPlugin())

# 配置滤波参数
ctx.set_config({
    "filter_type": "butterworth",
    "lowcut": 0.01,
    "highcut": 0.3,
    "order": 4,
}, plugin_name="filtered_waveforms")

# 配置波形宽度插件使用滤波波形
ctx.set_config({
    "use_filtered": True,  # 使用滤波后的波形
    "sampling_rate": 0.5,
}, plugin_name="waveform_width")

widths = ctx.get_data("run_001", "waveform_width")
```

## 配置选项

| 选项 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `use_filtered` | bool | False | 是否使用滤波后的波形 |
| `sampling_rate` | float | 0.5 | 采样率（GHz），用于将采样点数转换为时间（ns） |
| `rise_low` | float | 0.1 | 上升时间的低阈值比例（10%） |
| `rise_high` | float | 0.9 | 上升时间的高阈值比例（90%） |
| `fall_high` | float | 0.9 | 下降时间的高阈值比例（90%） |
| `fall_low` | float | 0.1 | 下降时间的低阈值比例（10%） |
| `interpolation` | bool | True | 是否使用线性插值提高精度 |

## 输出数据类型

`WAVEFORM_WIDTH_DTYPE` 包含以下字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `rise_time` | f4 | 上升时间（ns） |
| `fall_time` | f4 | 下降时间（ns） |
| `total_width` | f4 | 总宽度（ns） |
| `rise_time_samples` | f4 | 上升时间（采样点数） |
| `fall_time_samples` | f4 | 下降时间（采样点数） |
| `total_width_samples` | f4 | 总宽度（采样点数） |
| `peak_position` | i8 | 峰值位置（采样点索引） |
| `peak_height` | f4 | 峰值高度 |
| `timestamp` | i8 | 事件时间戳 |
| `channel` | i2 | 通道号 |
| `event_index` | i8 | 事件索引 |

## 高级用法

### 自定义阈值

使用 20%-80% 阈值而不是默认的 10%-90%：

```python
ctx.set_config({
    "rise_low": 0.2,   # 20% 阈值
    "rise_high": 0.8,  # 80% 阈值
    "fall_high": 0.8,
    "fall_low": 0.2,
}, plugin_name="waveform_width")
```

### 数据分析示例

```python
import numpy as np

widths = ctx.get_data("run_001", "waveform_width")

for ch_idx, ch_widths in enumerate(widths):
    if len(ch_widths) == 0:
        continue

    print(f"通道 {ch_idx} 统计:")
    print(f"  峰值数量: {len(ch_widths)}")

    # 上升时间统计
    rise_times = ch_widths["rise_time"]
    print(f"  上升时间:")
    print(f"    平均值: {np.mean(rise_times):.2f} ns")
    print(f"    标准差: {np.std(rise_times):.2f} ns")
    print(f"    范围: [{np.min(rise_times):.2f}, {np.max(rise_times):.2f}] ns")

    # 下降时间统计
    fall_times = ch_widths["fall_time"]
    print(f"  下降时间:")
    print(f"    平均值: {np.mean(fall_times):.2f} ns")
    print(f"    标准差: {np.std(fall_times):.2f} ns")
```

## 注意事项

1. **依赖 SignalPeaksPlugin**: 必须先注册并配置 `SignalPeaksPlugin`
2. **采样率设置**: 确保 `sampling_rate` 与实际 DAQ 采样率一致
3. **滤波波形**: 使用 `use_filtered=True` 时，必须先注册 `FilteredWaveformsPlugin`
4. **阈值选择**: 根据信号特性调整 `rise_low/high` 和 `fall_low/high` 参数
5. **插值精度**: 启用 `interpolation=True` 可提高时间计算精度，但会略微增加计算时间

## 示例代码

完整的使用示例请参见：`examples/waveform_width_example.py`

## 相关插件

- `SignalPeaksPlugin`: 峰值检测插件（必需依赖）
- `FilteredWaveformsPlugin`: 波形滤波插件（可选）
- `StWaveformsPlugin`: 结构化波形插件（必需依赖）
