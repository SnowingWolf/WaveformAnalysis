# WaveformAnalysis 内置插件文档

> 本文档由 PluginSpec 元数据自动生成，提供所有内置插件的完整参考。

## 概述

WaveformAnalysis 采用**插件化架构**处理 DAQ（数据采集系统）波形数据。每个插件负责数据处理流水线中的一个特定步骤，通过声明式的依赖关系自动构建处理 DAG（有向无环图）。

### 核心特性

| 特性 | 说明 |
|------|------|
| **自动依赖解析** | 插件声明 `depends_on`，Context 自动按正确顺序执行 |
| **智能缓存** | 基于 lineage（代码版本+配置+dtype）的缓存，自动失效 |
| **零拷贝存储** | 使用 `numpy.memmap` 实现大数据的高效持久化 |
| **流式处理** | 支持内存受限场景下的分块流式处理 |
| **多加速器** | CPU (NumPy/SciPy/Numba)、JAX (GPU) 等多种后端 |

### 插件统计

- **总插件数**: 16
- **类别数**: 7
- **加速器**: CPU (NumPy/SciPy)

---

## 快速开始

### 基本用法

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import standard_plugins

# 创建 Context 并注册所有标准插件
ctx = Context(config={"data_root": "DAQ", "n_channels": 2})
ctx.register(*standard_plugins)

# 获取数据（自动解析依赖并执行）
st_waveforms = ctx.get_data("run_001", "st_waveforms")
peaks = ctx.get_data("run_001", "signal_peaks")
```

### 配置插件

```python
# 全局配置
ctx.set_config({
    "n_channels": 2,
    "daq_adapter": "vx2730",
})

# 插件特定配置
ctx.set_config({
    "height": 30.0,
    "prominence": 0.7,
    "use_derivative": True,
}, plugin_name="signal_peaks")

# 查看插件配置选项
ctx.list_plugin_configs(plugin_name="signal_peaks")
```

### 预览执行计划

```python
# 在执行前预览依赖和缓存状态
ctx.preview_execution("run_001", "signal_peaks")
```

---

## 数据处理流水线

### 标准流水线

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           数据加载层                                      │
│                                                                          │
│   CSV Files ──► raw_files ──► records                                   │
│                     │                                                    │
└─────────────────────┼────────────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          波形处理层                                       │
│                                                                          │
│   raw_files ──► st_waveforms ──► filtered_waveforms                     │
│                      │                                                   │
│                      ├──► waveform_width                                │
│                      └──► waveform_width_integral                       │
└──────────────────────┼───────────────────────────────────────────────────┘
                       │
       ┌───────────────┼───────────────┐
       ▼               ▼               ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│  特征提取    │ │  峰值检测    │ │  Hit检测     │
│              │ │              │ │              │
│basic_features│ │ signal_peaks │ │    hits      │
└──────┬───────┘ └──────────────┘ └──────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          数据整合层                                       │
│                                                                          │
│   basic_features + st_waveforms ──► df (DataFrame)                      │
│                                       │                                  │
│                                       ▼                                  │
│                                   df_events (时间窗口分组)               │
│                                       │                                  │
│                                       ▼                                  │
│                                   df_paired (跨通道配对)                 │
└─────────────────────────────────────────────────────────────────────────┘
```

### 新版事件流水线

```
raw_files ──► records ──► events ──► events_df ──► events_grouped
```

---

## 插件快速参考

| 插件 | 提供数据 | 版本 | 类别 | 依赖 |
|------|----------|------|------|------|
| [`BasicFeaturesPlugin`](basic_features.md) | `basic_features` | 0.0.0 | 特征提取 | - |
| [`CacheAnalysisPlugin`](cache_analysis.md) | `cache_analysis` | 0.1.0 | 缓存分析 | - |
| [`DataFramePlugin`](df.md) | `df` | 0.0.0 | 数据导出 | st_waveforms, basic_features |
| [`GroupedEventsPlugin`](df_events.md) | `df_events` | 0.0.0 | 事件分析 | df |
| [`PairedEventsPlugin`](df_paired.md) | `df_paired` | 0.0.0 | 事件分析 | df_events |
| [`EventsPlugin`](events.md) | `events` | 0.1.0 | 事件分析 | - |
| [`EventFramePlugin`](events_df.md) | `events_df` | 0.1.0 | 事件分析 | events |
| [`EventsGroupedPlugin`](events_grouped.md) | `events_grouped` | 0.1.0 | 事件分析 | events_df |
| [`FilteredWaveformsPlugin`](filtered_waveforms.md) | `filtered_waveforms` | 1.0.2 | 波形处理 | st_waveforms |
| [`HitFinderPlugin`](hits.md) | `hits` | 0.0.0 | 特征提取 | st_waveforms |
| [`RawFileNamesPlugin`](raw_files.md) | `raw_files` | 0.0.2 | 数据加载 | - |
| [`RecordsPlugin`](records.md) | `records` | 0.4.0 | 记录处理 | raw_files |
| [`SignalPeaksPlugin`](signal_peaks.md) | `signal_peaks` | 1.0.2 | 特征提取 | filtered_waveforms, st_waveforms |
| [`WaveformsPlugin`](st_waveforms.md) | `st_waveforms` | 0.1.0 | 波形处理 | raw_files |
| [`WaveformWidthPlugin`](waveform_width.md) | `waveform_width` | 1.0.1 | 波形处理 | - |
| [`WaveformWidthIntegralPlugin`](waveform_width_integral.md) | `waveform_width_integral` | 1.1.0 | 波形处理 | - |

---

## 按类别浏览

### 数据加载

数据加载插件负责扫描和读取原始数据文件。


| 插件 | 说明 | 依赖 |
|------|------|------|
| [`raw_files`](raw_files.md) | Scan the data directory and group raw CSV files by channel n... | - |

### 波形处理

波形处理插件对原始波形进行结构化、滤波等预处理。


| 插件 | 说明 | 依赖 |
|------|------|------|
| [`filtered_waveforms`](filtered_waveforms.md) | Apply filtering to waveforms using Butterworth or Savitzky-G... | st_waveforms |
| [`st_waveforms`](st_waveforms.md) | Extract waveforms from raw CSV files and structure them into... | raw_files |
| [`waveform_width`](waveform_width.md) | Calculate rise/fall time based on peak detection results. | - |
| [`waveform_width_integral`](waveform_width_integral.md) | Event-wise integral quantile width using st_waveforms baseli... | - |

### 特征提取

特征提取插件从波形中计算各种物理特征（高度、面积、峰值等）。


| 插件 | 说明 | 依赖 |
|------|------|------|
| [`basic_features`](basic_features.md) | Plugin to compute basic height/area features from structured... | - |
| [`hits`](hits.md) | Example implementation of the HitFinder as a plugin. | st_waveforms |
| [`signal_peaks`](signal_peaks.md) | Detect peaks in filtered waveforms and extract peak features... | filtered_waveforms, st_waveforms |

### 事件分析

事件分析插件进行时间窗口分组、跨通道配对等高级分析。


| 插件 | 说明 | 依赖 |
|------|------|------|
| [`df_events`](df_events.md) | Plugin to group events by time window. | df |
| [`df_paired`](df_paired.md) | Plugin to pair events across channels. | df_events |
| [`events`](events.md) | Provide event index data backed by the records bundle. | - |
| [`events_df`](events_df.md) | Build an events DataFrame from the events bundle. | events |
| [`events_grouped`](events_grouped.md) | Group events_df into multi-channel events by time window. | events_df |

### 数据导出

数据导出插件将处理结果整合为 DataFrame 等便于分析的格式。


| 插件 | 说明 | 依赖 |
|------|------|------|
| [`df`](df.md) | Plugin to build the initial single-channel events DataFrame. | st_waveforms, basic_features |

### 缓存分析

缓存分析插件用于诊断和管理缓存状态。


| 插件 | 说明 | 依赖 |
|------|------|------|
| [`cache_analysis`](cache_analysis.md) | Analyze cache usage and return summary, entries, and diagnos... | - |

### 记录处理

记录处理插件构建事件索引表，支持高效的数据查询。


| 插件 | 说明 | 依赖 |
|------|------|------|
| [`records`](records.md) | Build records (event index table) from raw_files. | raw_files |


---

## 常见用例

### 用例 1: 基础波形分析

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import (
    RawFileNamesPlugin,
    WaveformsPlugin,
    BasicFeaturesPlugin,
    DataFramePlugin,
)

ctx = Context(config={"data_root": "DAQ", "n_channels": 2})
ctx.register(RawFileNamesPlugin())
ctx.register(WaveformsPlugin())
ctx.register(BasicFeaturesPlugin())
ctx.register(DataFramePlugin())

# 获取包含基础特征的 DataFrame
df = ctx.get_data("run_001", "df")
print(df.head())
```

### 用例 2: 峰值检测与分析

```python
from waveform_analysis.core.plugins.builtin.cpu import (
    FilteredWaveformsPlugin,
    SignalPeaksPlugin,
)

# 添加滤波和峰值检测插件
ctx.register(FilteredWaveformsPlugin())
ctx.register(SignalPeaksPlugin())

# 配置峰值检测参数
ctx.set_config({
    "height": 30.0,
    "prominence": 0.7,
    "distance": 2,
}, plugin_name="signal_peaks")

# 获取峰值数据
peaks = ctx.get_data("run_001", "signal_peaks")
for ch, ch_peaks in enumerate(peaks):
    print(f"Channel {ch}: {len(ch_peaks)} peaks detected")
```

### 用例 3: 事件配对分析

```python
from waveform_analysis.core.plugins.builtin.cpu import (
    GroupedEventsPlugin,
    PairedEventsPlugin,
)

ctx.register(GroupedEventsPlugin())
ctx.register(PairedEventsPlugin())

# 配置时间窗口
ctx.set_config({"time_window_ns": 100}, plugin_name="df_events")

# 获取配对事件
paired = ctx.get_data("run_001", "df_paired")
print(f"Found {len(paired)} paired events")
```

---

## 开发自定义插件

### 插件模板

```python
from waveform_analysis.core.plugins.core.base import Plugin, Option
import numpy as np

class MyCustomPlugin(Plugin):
    """自定义插件示例"""

    provides = "my_custom_data"
    depends_on = ["st_waveforms"]
    version = "1.0.0"
    description = "计算自定义特征"

    # 输出数据类型
    output_dtype = np.dtype([
        ("feature_a", "f4"),
        ("feature_b", "f4"),
    ])

    # 配置选项
    options = {
        "threshold": Option(
            default=10.0,
            type=float,
            help="检测阈值",
        ),
        "window_size": Option(
            default=100,
            type=int,
            help="窗口大小（采样点）",
        ),
    }

    def compute(self, context, run_id, **kwargs):
        # 获取依赖数据
        st_waveforms = context.get_data(run_id, "st_waveforms")

        # 获取配置
        threshold = context.get_config(self, "threshold")
        window_size = context.get_config(self, "window_size")

        # 计算特征
        results = []
        for ch_data in st_waveforms:
            ch_result = np.zeros(len(ch_data), dtype=self.output_dtype)
            # ... 计算逻辑 ...
            results.append(ch_result)

        return results
```

### 注册和使用

```python
ctx.register(MyCustomPlugin())
my_data = ctx.get_data("run_001", "my_custom_data")
```

---

## 相关文档

- [快速开始指南](../../user-guide/QUICKSTART_GUIDE.md)
- [架构概览](../../architecture/ARCHITECTURE.md)
- [配置管理](../../features/context/CONFIGURATION.md)
- [流式处理指南](../../features/plugin/STREAMING_PLUGINS_GUIDE.md)
- [信号处理插件](../../features/plugin/SIGNAL_PROCESSING_PLUGINS.md)
- [PluginSpec 开发指南](../../development/plugin-development/PLUGIN_SPEC_GUIDE.md)

---

## 文档维护

本文档由 `waveform-docs` 工具自动生成：

```bash
# 重新生成插件文档
waveform-docs generate plugins-auto -o docs/plugins/builtin/auto/

# 检查文档覆盖率
waveform-docs check coverage

# 严格模式（检查 spec 质量）
waveform-docs check coverage --strict
```

> **注意**: 请勿手动编辑 `auto/` 目录下的文件，它们会在下次生成时被覆盖。
> 如需补充内容，请在 `manual/` 目录下创建文档。

---

*本文档由 PluginSpec 元数据自动生成*