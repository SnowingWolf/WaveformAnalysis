**导航**: [文档中心](../README.md) > [架构设计](README.md) > 工作流程

---

# Context 和 Processor 数据处理流程演示

本文档详细介绍如何使用 `Context` 和 `Processor` 进行波形数据的完整处理流程。

---

## 目录

- [概述](#概述)
- [核心组件](#核心组件)
- [基础使用流程](#基础使用流程)
- [高级用法](#高级用法)
- [实际应用示例](#实际应用示例)
- [最佳实践](#最佳实践)

---

## 概述

`Context` 和 `Processor` 是 waveform_analysis 框架的两个核心组件：

- **Context**: 插件系统的核心调度器，负责管理插件注册、依赖解析、配置分发和数据缓存
- **Processor**: 信号处理模块，负责波形结构化、特征提取和事件分析

两者结合使用可以实现从原始数据到分析结果的完整数据处理流水线。

---

## 核心组件

### Context 类

`Context` 是插件系统的"大脑"，负责：

- 插件注册和依赖管理
- 配置参数的统一管理
- 数据缓存（内存和磁盘）
- 执行计划优化
- 血缘追踪

### Processor 组件

`WaveformStruct` 与 event_grouping.py 中的函数负责：

- 将原始波形数组转换为结构化数据
- 提取物理特征（峰值、电荷、时间等）
- 支持多通道事件聚类和配对
- 可选的 Numba JIT 编译加速（如多通道事件聚类）

---

## 基础使用流程

### 1. 创建 Context 并注册插件

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import (
    RawFilesPlugin,
    WaveformsPlugin,
    StWaveformsPlugin,
    PeaksPlugin,
    ChargesPlugin,
)

# 创建 Context 实例
ctx = Context(
    storage_dir="./strax_data",  # 数据存储目录
    config={
        "data_root": "DAQ",
        "daq_adapter": "vx2730",
    }
)

# 注册所需的插件
ctx.register(RawFilesPlugin())
ctx.register(WaveformsPlugin())
ctx.register(StWaveformsPlugin())
ctx.register(BasicFeaturesPlugin())
```

### 2. 配置参数

```python
# 方式1: 初始化时配置
ctx = Context(config={
    "height_range": (40, 90),
    "area_range": (0, None),
    "daq_adapter": "vx2730",
})

# 方式2: 运行时更新配置
ctx.set_config({
    "height_range": (45, 95),
    "show_progress": True,
})

# 方式3: 为特定插件设置配置（推荐，避免冲突）
ctx.set_config({"height_range": (40, 90)}, plugin_name="basic_features")
ctx.set_config({"area_range": (0, None)}, plugin_name="basic_features")
ctx.set_config({"daq_adapter": "vx2730"}, plugin_name="raw_files")

# 查看当前配置
ctx.show_config()  # 显示全局配置
ctx.show_config("basic_features")  # 显示特定插件的配置
```

### 3. 获取数据（自动触发插件执行）

```python
# 获取原始文件列表
raw_files = ctx.get_data("run_001", "raw_files")
print(f"找到 {len(raw_files)} 个通道的文件")

# 获取波形数据（会自动执行 RawFilesPlugin -> WaveformsPlugin）
waveforms = ctx.get_data("run_001", "waveforms")
print(f"加载了 {len(waveforms)} 个通道的波形")

# 获取结构化波形（会自动执行依赖插件）
st_waveforms = ctx.get_data("run_001", "st_waveforms")
print(f"结构化波形数量: {len(st_waveforms)}")

# 获取特征数据（会自动执行完整的插件链）
basic_features = ctx.get_data("run_001", "basic_features")
heights = [ch["height"] for ch in basic_features]
areas = [ch["area"] for ch in basic_features]
print(f"高度通道数: {len(heights)}，面积通道数: {len(areas)}")
```

### 4. 使用 Processor 进行信号处理

```python
from waveform_analysis.core.processing.waveform_struct import WaveformStruct

# 方式1: 使用 WaveformStruct 直接处理
waveform_struct = WaveformStruct(waveforms)
structured = waveform_struct.structure_waveforms(show_progress=True)

# 方式2: 通过插件链获取特征
basic_features = ctx.get_data("run_001", "basic_features")
heights = [ch["height"] for ch in basic_features]
areas = [ch["area"] for ch in basic_features]

print(f"找到 {len(heights)} 个高度值")
print(f"计算了 {len(areas)} 个面积值")
```

---

## 高级用法

### 1. 查看插件依赖关系

```python
# 查看数据血缘关系
lineage = ctx.get_lineage("basic_features")
print(lineage)

# 可视化依赖图
ctx.plot_lineage("basic_features", kind="plotly")
# 或
ctx.plot_lineage("basic_features", kind="mermaid")  # 输出 Mermaid 图
```

### 2. 批量处理多个运行

```python
from waveform_analysis.core.data.export import BatchProcessor

# 创建批量处理器
batch_processor = BatchProcessor(ctx)

# 批量处理多个运行
results = batch_processor.process_runs(
    run_ids=["run_001", "run_002", "run_003"],
    data_name="basic_features",
    max_workers=4,  # 并行处理
    show_progress=True,
)

# 结果结构：{"results": ..., "errors": ..., "meta": ...}
for run_id, data in results["results"].items():
    print(f"{run_id}: {len(data['height'])} 个通道的高度")
if results["errors"]:
    print(f"Errors: {results['errors']}")
```

### 3. 时间范围查询

```python
# 查询特定时间范围内的数据
time_range_data = ctx.get_data_time_range(
    run_id="run_001",
    data_name="st_waveforms",
    start_time=1000,  # ns
    end_time=2000,    # ns
)
```

### 4. 自定义插件

```python
from waveform_analysis.core.plugins.core.base import Plugin, Option, option

@option('threshold', default=50.0, type=float, help='检测阈值')
class CustomFeaturePlugin(Plugin):
    """自定义特征提取插件"""

    provides = "custom_features"
    depends_on = ["st_waveforms"]

    def compute(self, context, run_id, **kwargs):
        # 获取依赖数据
        st_waveforms = context.get_data(run_id, "st_waveforms")
        
        # 获取配置
        threshold = context.get_config(self, "threshold")
        
        # 执行处理
        features = self._extract_features(st_waveforms, threshold)
        
        return features
    
    def _extract_features(self, waveforms, threshold):
        # 自定义特征提取逻辑
        return {"custom_value": len(waveforms)}

# 注册自定义插件
ctx.register(CustomFeaturePlugin())

# 使用
custom_features = ctx.get_data("run_001", "custom_features")
```

### 5. 性能优化

```python
# 启用插件性能统计
ctx = Context(
    storage_dir="./strax_data",
    enable_stats=True,
    stats_mode='detailed',  # 'basic' 或 'detailed'
    stats_log_file='./logs/plugin_stats.log'
)

# 获取性能报告
report = ctx.get_performance_report()
print(report)

# 使用 Numba 加速（自动检测）
# group_multi_channel_hits 会在 numba 可用时自动使用 JIT
# df_events = group_multi_channel_hits(df, time_window_ns=100, use_numba=True)
```

### 6. 数据导出

```python
from waveform_analysis.core.data.export import DataExporter

# 创建导出器
exporter = DataExporter()

# 导出为不同格式
basic_features = ctx.get_data("run_001", "basic_features")
exporter.export([ch["height"] for ch in basic_features], "./outputs/heights.parquet", format="parquet")

st_waveforms = ctx.get_data("run_001", "st_waveforms")
exporter.export(st_waveforms, "./outputs/waveforms.h5", format="hdf5", key="waveforms")

exporter.export([ch["area"] for ch in basic_features], "./outputs/areas.csv", format="csv")
```

---

## 实际应用示例

### 示例1: 完整的波形分析流程

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import (
    RawFilesPlugin,
    WaveformsPlugin,
    StWaveformsPlugin,
    BasicFeaturesPlugin,
    DataFramePlugin,
    GroupedEventsPlugin,
    PairedEventsPlugin,
)

# 1. 初始化 Context
ctx = Context(
    storage_dir="./strax_data",
    config={
        "data_root": "DAQ",
        "daq_adapter": "vx2730",
        "height_range": (40, 90),
        "area_range": (0, None),
        "time_window_ns": 1000,
        "show_progress": True,
    }
)

# 2. 注册所有需要的插件
plugins = [
    RawFilesPlugin(),
    WaveformsPlugin(),
    StWaveformsPlugin(),
    BasicFeaturesPlugin(),
    DataFramePlugin(),
    GroupedEventsPlugin(),
    PairedEventsPlugin(),
]
for plugin in plugins:
    ctx.register(plugin)

# 3. 获取最终结果（自动执行所有依赖插件）
run_id = "Co60_R50"
df_paired = ctx.get_data(run_id, "df_paired", show_progress=True)

# 4. 数据分析和可视化
import pandas as pd
import matplotlib.pyplot as plt

# df_paired 已经是 DataFrame，不需要转换
df = df_paired if isinstance(df_paired, pd.DataFrame) else pd.DataFrame(df_paired)

# 绘制高度分布
fig, axes = plt.subplots(1, 2, figsize=(12, 5))
axes[0].hist(df['height_ch6'], bins=50, alpha=0.7, label='CH6')
axes[0].hist(df['height_ch7'], bins=50, alpha=0.7, label='CH7')
axes[0].set_xlabel('Height [ADC]')
axes[0].set_ylabel('Counts')
axes[0].legend()
axes[0].set_title('Height Distribution')

# 绘制时间差分布
axes[1].hist(df['delta_t'], bins=50)
axes[1].set_xlabel('Time Difference [ns]')
axes[1].set_ylabel('Counts')
axes[1].set_title('Coincidence Time Distribution')

plt.tight_layout()
plt.savefig('./outputs/analysis_results.png')
plt.show()

print(f"总共找到 {len(df)} 个配对事件")
print(f"平均高度 (CH6): {df['height_ch6'].mean():.2f}")
print(f"平均高度 (CH7): {df['height_ch7'].mean():.2f}")
```

### 示例2: 使用处理函数进行自定义处理

```python
import numpy as np
import pandas as pd

# 假设已有结构化波形数据
# st_waveforms 是 List[np.ndarray]，每个数组对应一个通道

# 提取特征（示例：手动计算 height/area）
height_range = (40, 90)
area_range = (0, None)
start_p, end_p = height_range
start_c, end_c = area_range

heights = []
areas = []
for st_ch in st_waveforms:
    if len(st_ch) == 0:
        heights.append(np.zeros(0))
        areas.append(np.zeros(0))
        continue

    waves = st_ch["wave"]
    baselines = st_ch["baseline"]
    waves_p = waves[:, start_p:end_p]
    height_vals = np.max(waves_p, axis=1) - np.min(waves_p, axis=1)
    waves_c = waves[:, start_c:end_c]
    area_vals = np.sum(baselines[:, np.newaxis] - waves_c, axis=1)

    heights.append(height_vals)
    areas.append(area_vals)

# 构建 DataFrame（逻辑与 DataFramePlugin 一致）
all_timestamps = np.concatenate([st["timestamp"] for st in st_waveforms])
all_areas = np.concatenate(areas)
all_heights = np.concatenate(heights)
all_channels = np.concatenate([st["channel"] for st in st_waveforms])

df = pd.DataFrame({
    "timestamp": all_timestamps,
    "area": all_areas,
    "height": all_heights,
    "channel": all_channels,
}).sort_values("timestamp")

print(df.head())
print(f"数据形状: {df.shape}")
print(f"列名: {df.columns.tolist()}")
```

### 示例3: 流式处理（大数据场景）

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.core.streaming import get_streaming_context
from waveform_analysis.core.plugins.builtin.cpu import RawFilesPlugin, WaveformsPlugin

# 对于大数据，使用流式处理
ctx = Context(storage_dir="./strax_data")

# 注册常规插件
ctx.register(RawFilesPlugin(), WaveformsPlugin())

# 获取流式数据（返回生成器）
stream_ctx = get_streaming_context(ctx, run_id="run_001", chunk_size=50000)
waveform_stream = stream_ctx.get_stream("waveforms")

# 逐个处理 chunk
for chunk in waveform_stream:
    # 处理每个 chunk
    print(f"处理 chunk: {chunk.shape}")
    # ... 你的处理逻辑 ...
```

### 示例4: 缓存管理

```python
# Context 自动管理缓存
ctx = Context(storage_dir="./strax_data")

# 第一次运行会计算并缓存
data1 = ctx.get_data("run_001", "st_waveforms")  # 计算中...

# 第二次运行会直接从缓存加载
data2 = ctx.get_data("run_001", "st_waveforms")  # 快速加载！

# 清除特定数据的缓存
ctx.clear_cache_for("run_001", "st_waveforms")

# 清除该 run 的所有缓存
ctx.clear_cache_for("run_001")

# 查看缓存统计
stats = ctx.cache_stats()
print(f"缓存命中率: {stats.get('hit_rate', 0):.2%}")
```

---

## 最佳实践

### 1. 配置管理

**推荐方式：按插件设置配置**

```python
# ✅ 推荐：使用插件命名空间
ctx.set_config({"height_range": (40, 90)}, plugin_name="basic_features")
ctx.set_config({"daq_adapter": "vx2730"}, plugin_name="raw_files")

# ❌ 不推荐：全局配置可能冲突
ctx.set_config({"height_range": (40, 90)})  # 如果有多个插件使用 height_range，会冲突
```

**查看配置归属**

```python
# 查看所有已注册的插件
for plugin_name, plugin in ctx._plugins.items():
    print(f"插件: {plugin_name}")
    print(f"  类: {plugin.__class__.__name__}")
    print(f"  配置选项: {list(plugin.options.keys())}")
    print()

# 查看特定插件的配置
ctx.show_config("basic_features")  # 显示 basic_features 插件的当前配置值

# 手动查找配置项属于哪个插件
config_key = "height_range"
matching_plugins = [
    name for name, plugin in ctx._plugins.items() 
    if config_key in plugin.options
]
print(f"配置项 '{config_key}' 属于: {matching_plugins}")
```

### 2. 错误处理

```python
try:
    data = ctx.get_data("run_001", "st_waveforms")
except RuntimeError as e:
    print(f"插件执行失败: {e}")
    # 查看错误上下文
    # Context 会自动记录错误信息
```

### 3. 性能优化建议

```python
# 1. 启用性能统计，找出瓶颈
ctx = Context(enable_stats=True, stats_mode='detailed')

# 2. 使用并行处理
ctx.set_config({
    "channel_workers": 4,  # 通道级并行
    "n_jobs": 4,           # 文件级并行
}, plugin_name="waveforms")

# 3. 合理使用缓存
# 对于频繁访问的数据，缓存很有用
# 对于一次性数据，可以禁用缓存节省空间

# 4. 使用流式处理处理大数据
# 避免一次性加载所有数据到内存
```

### 4. 数据组织

```python
# 使用有意义的 run_id
ctx.get_data("Co60_R50_20240101", "st_waveforms")  # ✅ 清晰
ctx.get_data("run1", "st_waveforms")  # ❌ 不清晰

# 保存中间结果以便调试
intermediate_data = ctx.get_data("run_001", "waveforms")
# ... 可以保存到文件进行调试 ...
```

### 5. 插件开发

```python
# 1. 每个插件只做一件事
class MyPlugin(Plugin):
    provides = "one_thing"  # ✅ 明确
    
# 2. 使用类型提示和文档字符串
def compute(self, context, run_id: str, **kwargs) -> np.ndarray:
    """清晰的文档说明"""
    pass

# 3. 验证输入和配置
def validate(self):
    if not self.provides:
        raise ValueError("Plugin must specify 'provides'")
    
# 4. 使用 Option 定义配置
@option('threshold', default=50.0, type=float, help='Detection threshold')
class MyPlugin(Plugin):
    pass
```

---

## 常见问题

### Q1: 如何知道需要注册哪些插件？

A: 查看数据血缘关系。如果要获取 `basic_features`，运行：
```python
lineage = ctx.get_lineage("basic_features")
print(lineage)  # 会显示所有依赖的插件
```

### Q2: 配置冲突怎么办？

A: 使用插件命名空间：
```python
ctx.set_config({"height_range": (40, 90)}, plugin_name="basic_features")  # 只影响 basic_features 插件
```

### Q3: 如何加速数据处理？

A: 
1. 启用并行处理（`channel_workers`, `n_jobs`）
2. 使用 Numba JIT（自动检测）
3. 合理使用缓存
4. 对于大数据使用流式处理

### Q4: 缓存占用太多空间怎么办？

A: 
```python
# 清除不需要的缓存
ctx.clear_cache_for("run_001", "waveforms")  # 清除特定数据

# 或更改存储目录
ctx = Context(storage_dir="./small_cache")
```

### Q5: 如何调试插件执行问题？

A:
```python
# 1. 启用详细日志
import logging
logging.basicConfig(level=logging.DEBUG)

# 2. 查看执行计划
plan = ctx.analyze_dependencies("basic_features")
print(plan)

# 3. 逐步执行
waveforms = ctx.get_data("run_001", "waveforms")  # 先测试这一步
st_waveforms = ctx.get_data("run_001", "st_waveforms")  # 再测试下一步
```

---

## 相关文档

- [项目结构说明](PROJECT_STRUCTURE.md)
- [插件系统指南](../updates/NEW_FEATURES.md)
- [快速开始指南](../user-guide/QUICKSTART_GUIDE.md)
- [缓存机制说明](../features/context/DATA_ACCESS.md#缓存机制)
- [流式处理指南](../features/plugin/STREAMING_PLUGINS_GUIDE.md)

---

## 总结

`Context` 和 `Processor` 提供了强大的数据处理能力：

1. **Context**: 管理整个数据处理流程，自动处理依赖关系和缓存
2. **Processor**: 提供高性能的信号处理和特征提取
3. **结合使用**: 实现从原始数据到分析结果的完整流水线

通过合理使用这两个组件，可以构建高效、可维护的数据分析工作流。
