**导航**: [文档中心](../../README.md) > [功能特性](../README.md) > [插件功能](README.md) > 信号处理插件

---

# 信号处理插件文档

WaveformAnalysis 提供了两个信号处理插件，用于波形滤波和高级峰值检测：

1. **FilteredWaveformsPlugin** - 波形滤波插件
2. **SignalPeaksPlugin** - 基于滤波波形的峰值检测插件

这些插件提供了比标准插件更灵活的信号处理功能，特别适合需要精细控制滤波参数和峰值检测的场景。

## 插件导入

```python
from waveform_analysis.core.plugins.builtin.cpu import (
    FilteredWaveformsPlugin,
    SignalPeaksPlugin,
)
```

文件位置：
- `waveform_analysis/core/plugins/builtin/cpu/filtering.py`
- `waveform_analysis/core/plugins/builtin/cpu/peak_finding.py`

---

## FilteredWaveformsPlugin

对结构化波形数据应用滤波处理，支持两种滤波方法：

- **Butterworth 带通滤波器 (BW)**: 适合去除特定频率范围的噪声
- **Savitzky-Golay 滤波器 (SG)**: 适合保持波形形状的平滑处理

### 依赖关系

- **依赖**: `st_waveforms` (由 `StWaveformsPlugin` 提供)
- **提供**: `filtered_waveforms` (滤波后的波形数组)

### 配置选项

| 选项 | 默认值 | 说明 |
|------|--------|------|
| `filter_type` | `"SG"` | 滤波器类型: `"BW"` 或 `"SG"` |
| `lowcut` | `0.1` | BW 滤波器低频截止频率 |
| `highcut` | `0.5` | BW 滤波器高频截止频率 |
| `fs` | `1.0` | BW 滤波器采样率 |
| `filter_order` | `4` | BW 滤波器阶数 |
| `sg_window_size` | `11` | SG 滤波器窗口大小（必须为奇数） |
| `sg_poly_order` | `2` | SG 滤波器多项式阶数 |

## SignalPeaksPlugin

从滤波后的波形中检测峰值，计算峰值的位置、高度、积分、边缘等详细特征。

支持两种峰值检测模式：
- **导数模式**: 检测一阶导数的峰值（推荐）
- **直接模式**: 直接检测波形峰值

### 依赖关系

- **依赖**: `filtered_waveforms`, `st_waveforms`
- **提供**: `signal_peaks` (峰值特征结构化数组)

### 数据类型

```python
ADVANCED_PEAK_DTYPE = np.dtype([
    ("position", "i8"),      # 峰值位置（采样点索引）
    ("height", "f4"),        # 峰值高度
    ("integral", "f4"),      # 峰值积分（面积）
    ("edge_start", "f4"),    # 峰值起始边缘
    ("edge_end", "f4"),      # 峰值结束边缘
    ("timestamp", "i8"),     # 事件时间戳（ps）
    ("channel", "i2"),       # 通道号
    ("event_index", "i8"),   # 事件索引
])
```

### 配置选项

| 选项 | 默认值 | 说明 |
|------|--------|------|
| `use_derivative` | `True` | 是否使用导数进行峰值检测 |
| `height` | `30.0` | 峰值的最小高度阈值 |
| `distance` | `2` | 峰值之间的最小距离（采样点数） |
| `prominence` | `0.7` | 峰值的最小显著性 |
| `width` | `4` | 峰值的最小宽度（采样点数） |
| `threshold` | `None` | 峰值的阈值条件（可选） |
| `height_method` | `"diff"` | 峰高计算方法: `"diff"` 或 `"minmax"` |

## 使用示例

### 示例 1: 完整的信号处理流程

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import (
    RawFilesPlugin, WaveformsPlugin, StWaveformsPlugin,
    FilteredWaveformsPlugin, SignalPeaksPlugin,
)

# 创建 Context 并注册所有插件
ctx = Context(storage_dir="./strax_data")
ctx.register(RawFilesPlugin(), WaveformsPlugin(), StWaveformsPlugin())
ctx.register(FilteredWaveformsPlugin(), SignalPeaksPlugin())

# 全局配置
ctx.set_config({"data_root": "DAQ", "daq_adapter": "vx2730"})

# 滤波配置（SG 滤波器）
ctx.set_config({
    "filter_type": "SG",
    "sg_window_size": 11,
    "sg_poly_order": 2,
}, plugin_name="filtered_waveforms")

# 峰值检测配置
ctx.set_config({
    "use_derivative": True,
    "height": 30.0,
    "prominence": 0.7,
    "width": 4,
    "height_method": "minmax",
}, plugin_name="signal_peaks")

# 执行分析
signal_peaks = ctx.get_data("run_001", "signal_peaks")

# 分析结果
for ch_idx, peaks_ch in enumerate(signal_peaks):
    print(f"通道 {ch_idx}: {len(peaks_ch)} 个峰值")
    if len(peaks_ch) > 0:
        print(f"  平均峰高: {peaks_ch['height'].mean():.2f}")
```

### 示例 2: 使用 Butterworth 滤波器

```python
# 配置 Butterworth 滤波器
ctx.set_config({
    "filter_type": "BW",
    "lowcut": 0.05,
    "highcut": 0.8,
    "fs": 1.0,
    "filter_order": 4,
}, plugin_name="filtered_waveforms")

filtered_waveforms = ctx.get_data("run_001", "filtered_waveforms")
```

## 数据流示意图

```
RawFilesPlugin → WaveformsPlugin → StWaveformsPlugin → FilteredWaveformsPlugin → SignalPeaksPlugin
                                                              ↓
                                                       filtered_waveforms
                                                              ↓
                                                         signal_peaks
```

## 高级用法

### 自定义滤波方法

继承 `FilteredWaveformsPlugin` 并重写 `_apply_filter` 方法：

```python
class CustomFilterPlugin(FilteredWaveformsPlugin):
    provides = "custom_filtered_waveforms"

    def _apply_filter(self, waveform, filter_type, context):
        if filter_type == "CUSTOM":
            return your_custom_filter(waveform)
        return super()._apply_filter(waveform, filter_type, context)
```

### 自定义峰值检测

继承 `SignalPeaksPlugin` 并自定义峰值检测逻辑：

```python
class CustomPeaksPlugin(SignalPeaksPlugin):
    provides = "custom_peaks"

    def _find_peaks_in_waveform(self, waveform, timestamp, channel, event_index, **kwargs):
        return your_custom_peak_detection(waveform)
```

## 注意事项

1. **滤波器选择**:
   - 保持波形形状的平滑处理，推荐使用 SG 滤波器
   - 去除特定频率噪声，推荐使用 BW 滤波器

2. **峰值检测参数**: `use_derivative=True` 通常能获得更好的效果，需要根据实际波形调整参数

3. **性能优化**: 滤波和峰值检测结果会自动缓存，修改配置参数后需要清除缓存

4. **依赖要求**: `scipy >= 1.5.0`, `numpy >= 1.18.0`

## 相关文档

- [架构文档](../../architecture/ARCHITECTURE.md)
- [插件开发指南](../../development/plugin-development/README.md)
- [流式处理插件](STREAMING_PLUGINS_GUIDE.md)
