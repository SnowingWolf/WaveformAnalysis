**导航**: [文档中心](../../README.md) > [功能特性](../README.md) > [插件功能](README.md) > 信号处理插件

---

# 信号处理插件文档

> **更新**: 2026-01-12 - 插件架构重构，按加速器划分

## 概述

WaveformAnalysis 提供了两个信号处理插件，用于波形滤波和高级峰值检测：

1. **FilteredWaveformsPlugin** - 波形滤波插件
2. **SignalPeaksPlugin** - 基于滤波波形的峰值检测插件

这些插件提供了比标准插件更灵活的信号处理功能，特别适合需要精细控制滤波参数和峰值检测的场景。

## 架构变化 (2026-01)

### 新的插件位置

信号处理插件已从扁平结构迁移到按加速器划分的架构：

**之前**:
```python
from waveform_analysis.core.plugins.builtin.signal_processing import (
    FilteredWaveformsPlugin,
    SignalPeaksPlugin,
)
```

**现在（推荐）**:
```python
# CPU 实现（推荐，明确指定加速器）
from waveform_analysis.core.plugins.builtin.cpu import (
    FilteredWaveformsPlugin,
    SignalPeaksPlugin,
)

# 或者从 builtin/ 导入（向后兼容）
from waveform_analysis.core.plugins.builtin import (
    FilteredWaveformsPlugin,
    SignalPeaksPlugin,
)
```

### 文件位置

- **CPU 实现**:
  - `waveform_analysis/core/plugins/builtin/cpu/filtering.py` - FilteredWaveformsPlugin
  - `waveform_analysis/core/plugins/builtin/cpu/peak_finding.py` - SignalPeaksPlugin
- **JAX 实现（待开发）**:
  - `waveform_analysis/core/plugins/builtin/jax/filtering.py` - JAX 滤波插件
  - `waveform_analysis/core/plugins/builtin/jax/peak_finding.py` - JAX 寻峰插件

### 向后兼容

旧的导入方式仍然可用，但会发出弃用警告：
```python
# 会发出 DeprecationWarning
from waveform_analysis.core.plugins.builtin.legacy import FilteredWaveformsPlugin
```

---

## FilteredWaveformsPlugin

### 功能描述

对结构化波形数据应用滤波处理，支持两种滤波方法：

- **Butterworth 带通滤波器 (BW)**: 适合去除特定频率范围的噪声
- **Savitzky-Golay 滤波器 (SG)**: 适合保持波形形状的平滑处理

### 依赖关系

- **依赖**: `st_waveforms` (由 `StWaveformsPlugin` 提供)
- **提供**: `filtered_waveforms` (滤波后的波形数组)

### 配置选项

| 选项 | 默认值 | 类型 | 说明 |
|------|--------|------|------|
| `filter_type` | `"SG"` | str | 滤波器类型: `"BW"` 或 `"SG"` |
| `lowcut` | `0.1` | float | BW 滤波器低频截止频率 |
| `highcut` | `0.5` | float | BW 滤波器高频截止频率 |
| `fs` | `1.0` | float | BW 滤波器采样率 |
| `filter_order` | `4` | int | BW 滤波器阶数 |
| `sg_window_size` | `11` | int | SG 滤波器窗口大小（必须为奇数） |
| `sg_poly_order` | `2` | int | SG 滤波器多项式阶数 |

### 使用示例

#### 示例 1: 使用 Savitzky-Golay 滤波器

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import (
    RawFilesPlugin,
    WaveformsPlugin,
    StWaveformsPlugin,
    FilteredWaveformsPlugin,
)

# 创建 Context 并注册插件
ctx = Context(storage_dir="./strax_data")
ctx.register_plugin(RawFilesPlugin())
ctx.register_plugin(WaveformsPlugin())
ctx.register_plugin(StWaveformsPlugin())
ctx.register_plugin(FilteredWaveformsPlugin())

# 配置全局参数
ctx.set_config({
    "data_root": "DAQ",
    "n_channels": 2,
    "start_channel_slice": 6,
})

# 配置 SG 滤波器
ctx.set_config({
    "filter_type": "SG",
    "sg_window_size": 11,
    "sg_poly_order": 2,
}, plugin_name="filtered_waveforms")

# 获取滤波后的波形
filtered_waveforms = ctx.get_data("run_001", "filtered_waveforms")
print(f"通道 0 滤波波形形状: {filtered_waveforms[0].shape}")
```

#### 示例 2: 使用 Butterworth 带通滤波器

```python
# 配置 Butterworth 滤波器
ctx.set_config({
    "filter_type": "BW",
    "lowcut": 0.05,     # 低频截止
    "highcut": 0.8,      # 高频截止
    "fs": 1.0,           # 采样率
    "filter_order": 4,   # 滤波器阶数
}, plugin_name="filtered_waveforms")

# 获取滤波后的波形
filtered_waveforms = ctx.get_data("run_001", "filtered_waveforms")
```

---

## SignalPeaksPlugin

### 功能描述

从滤波后的波形中检测峰值，计算峰值的位置、高度、积分、边缘等详细特征。

支持两种峰值检测模式：
- **导数模式**: 检测一阶导数的峰值（推荐）
- **直接模式**: 直接检测波形峰值

### 依赖关系

- **依赖**: `filtered_waveforms`, `st_waveforms`
- **提供**: `signal_peaks` (峰值特征结构化数组)

### 数据类型 (ADVANCED_PEAK_DTYPE)

```python
ADVANCED_PEAK_DTYPE = np.dtype([
    ("position", "i8"),      # 峰值位置（采样点索引）
    ("height", "f4"),        # 峰值高度
    ("integral", "f4"),      # 峰值积分（面积）
    ("edge_start", "f4"),    # 峰值起始边缘
    ("edge_end", "f4"),      # 峰值结束边缘
    ("timestamp", "i8"),     # 事件时间戳
    ("channel", "i2"),       # 通道号
    ("event_index", "i8"),   # 事件索引
])
```

### 配置选项

| 选项 | 默认值 | 类型 | 说明 |
|------|--------|------|------|
| `use_derivative` | `True` | bool | 是否使用导数进行峰值检测 |
| `height` | `30.0` | float | 峰值的最小高度阈值 |
| `distance` | `2` | int | 峰值之间的最小距离（采样点数） |
| `prominence` | `0.7` | float | 峰值的最小显著性 |
| `width` | `4` | int | 峰值的最小宽度（采样点数） |
| `threshold` | `None` | float | 峰值的阈值条件（可选） |
| `height_method` | `"diff"` | str | 峰高计算方法: `"diff"` 或 `"minmax"` |

### 使用示例

#### 示例 1: 基本峰值检测

```python
from waveform_analysis.core.plugins.builtin.cpu import SignalPeaksPlugin

# 注册峰值检测插件
ctx.register_plugin(SignalPeaksPlugin())

# 配置峰值检测参数
ctx.set_config({
    "use_derivative": True,     # 使用导数检测
    "height": 30.0,              # 最小峰高
    "distance": 2,               # 最小峰间距
    "prominence": 0.7,           # 最小显著性
    "width": 4,                  # 最小宽度
    "height_method": "minmax",   # 峰高计算方法
}, plugin_name="signal_peaks")

# 获取峰值检测结果
signal_peaks = ctx.get_data("run_001", "signal_peaks")

# 查看结果
for ch_idx, peaks_ch in enumerate(signal_peaks):
    print(f"通道 {ch_idx}: {len(peaks_ch)} 个峰值")
    if len(peaks_ch) > 0:
        print(f"  示例峰值: {peaks_ch[0]}")
```

#### 示例 2: 完整的信号处理流程

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import (
    RawFilesPlugin,
    WaveformsPlugin,
    StWaveformsPlugin,
    FilteredWaveformsPlugin,
    SignalPeaksPlugin,
)

# 创建 Context 并注册所有插件
ctx = Context(storage_dir="./strax_data")
ctx.register_plugin(RawFilesPlugin())
ctx.register_plugin(WaveformsPlugin())
ctx.register_plugin(StWaveformsPlugin())
ctx.register_plugin(FilteredWaveformsPlugin())
ctx.register_plugin(SignalPeaksPlugin())

# 全局配置
ctx.set_config({
    "data_root": "DAQ",
    "n_channels": 2,
    "start_channel_slice": 6,
})

# 滤波配置
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
run_id = "50V_OV_circulation_20thr"
signal_peaks = ctx.get_data(run_id, "signal_peaks")

# 分析结果
for ch_idx, peaks_ch in enumerate(signal_peaks):
    print(f"\n通道 {ch_idx}:")
    print(f"  总峰值数: {len(peaks_ch)}")
    if len(peaks_ch) > 0:
        print(f"  平均峰高: {peaks_ch['height'].mean():.2f}")
        print(f"  最大峰高: {peaks_ch['height'].max():.2f}")
        print(f"  平均峰宽: {(peaks_ch['edge_end'] - peaks_ch['edge_start']).mean():.2f}")
```

---

## 完整示例程序

详细的使用示例代码请参考: `examples/signal_processing_example.py`

该示例包含：
1. 基本信号处理流程
2. Butterworth 滤波器使用
3. 可视化滤波和峰值检测结果
4. 比较不同滤波方法的效果

运行示例:

```bash
python examples/signal_processing_example.py
```

---

## 数据流示意图

```
RawFilesPlugin → WaveformsPlugin → StWaveformsPlugin → FilteredWaveformsPlugin → SignalPeaksPlugin
                                                                ↓
                                                         filtered_waveforms
                                                                ↓
                                                           signal_peaks
```

---

## 与原始 Waver 类的对应关系

如果你之前使用的是 `Waver` 类，新插件的对应关系如下：

| Waver 方法 | 新插件 | 说明 |
|-----------|--------|------|
| `waveform_filter()` | `FilteredWaveformsPlugin` | 滤波功能 |
| `find_peaks()` | `SignalPeaksPlugin` | 寻峰功能 |
| `_peak_height_from_diff()` | `height_method="diff"` | 差分峰高计算 |
| `_peak_height_from_diff_new()` | `height_method="minmax"` | 最大最小值峰高计算 |

### 主要改进

1. **插件化架构**: 集成到 WaveformAnalysis 框架，自动处理依赖关系和缓存
2. **批量处理**: 自动处理所有通道和所有事件，无需手动循环
3. **配置管理**: 通过 Context 统一管理配置，支持持久化
4. **类型安全**: 使用 NumPy 结构化数组，提供类型检查
5. **可扩展性**: 可以轻松添加新的滤波方法或峰值检测算法

---

## 注意事项

1. **滤波器选择**:
   - 对于保持波形形状的平滑处理，推荐使用 SG 滤波器
   - 对于去除特定频率噪声，推荐使用 BW 滤波器

2. **峰值检测参数**:
   - `use_derivative=True` 通常能获得更好的峰值检测效果
   - 需要根据实际波形调整 `height`、`prominence`、`width` 参数

3. **性能优化**:
   - 滤波和峰值检测结果会自动缓存
   - 修改配置参数后需要清除缓存才能生效

4. **依赖要求**:
   - `scipy >= 1.5.0` (用于信号处理函数)
   - `numpy >= 1.18.0`

---

## 高级用法

### 自定义滤波方法

你可以继承 `FilteredWaveformsPlugin` 并重写 `_apply_filter` 方法来添加自定义滤波器：

```python
from waveform_analysis.core.plugins.builtin.signal_processing import FilteredWaveformsPlugin

class CustomFilterPlugin(FilteredWaveformsPlugin):
    provides = "custom_filtered_waveforms"

    def _apply_filter(self, waveform, filter_type, context):
        if filter_type == "CUSTOM":
            # 实现自定义滤波逻辑
            filtered = your_custom_filter(waveform)
            return filtered
        else:
            return super()._apply_filter(waveform, filter_type, context)
```

### 自定义峰值检测

类似地，你可以继承 `SignalPeaksPlugin` 并自定义峰值检测逻辑：

```python
from waveform_analysis.core.plugins.builtin.signal_processing import SignalPeaksPlugin

class CustomPeaksPlugin(SignalPeaksPlugin):
    provides = "custom_peaks"

    def _find_peaks_in_waveform(self, waveform, timestamp, channel, event_index, **kwargs):
        # 实现自定义峰值检测逻辑
        peaks = your_custom_peak_detection(waveform)
        return peaks
```

---

## 参考文档

- [WaveformAnalysis 架构文档](../docs/ARCHITECTURE.md)
- [插件开发指南](../docs/PLUGIN_DEVELOPMENT.md)
- [配置管理指南](../CLAUDE.md#configuration-management)

---

## 问题反馈

如有问题或建议，请在 GitHub Issues 中提交。
