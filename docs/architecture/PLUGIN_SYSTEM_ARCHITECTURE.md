**导航**: [文档中心](../README.md) > [架构设计](README.md) > 插件系统架构

---

# 插件系统架构

本文档详细描述 WaveformAnalysis 插件系统的完整架构，包括目录结构、核心类、继承关系和数据流。

---

## 1. 目录结构概览

```
waveform_analysis/core/plugins/
├── core/                          # 插件基础设施
│   ├── base.py                   # Plugin, Option 基类
│   ├── spec.py                   # PluginSpec 契约规范
│   ├── streaming.py              # StreamingPlugin, StreamingContext
│   ├── loader.py                 # PluginLoader 动态发现
│   ├── adapters.py               # Strax 插件适配器
│   ├── hot_reload.py             # 插件热重载
│   ├── stats.py                  # 插件执行统计
│   └── __init__.py               # 统一导出
│
├── builtin/                       # 内置插件（按加速器分类）
│   ├── cpu/                      # CPU 实现 (NumPy/SciPy/Numba)
│   │   ├── standard.py           # 统一导入入口
│   │   ├── raw_files.py          # RawFileNamesPlugin
│   │   ├── waveforms.py          # WaveformsPlugin
│   │   ├── filtering.py          # FilteredWaveformsPlugin
│   │   ├── peak_finding.py       # SignalPeaksPlugin
│   │   ├── hit_finder.py         # HitFinderPlugin
│   │   ├── basic_features.py     # BasicFeaturesPlugin
│   │   ├── dataframe.py          # DataFramePlugin
│   │   ├── event_analysis.py     # GroupedEventsPlugin, PairedEventsPlugin
│   │   └── ...
│   │
│   ├── jax/                      # JAX GPU 实现（占位）
│   ├── streaming/                # 流式处理插件
│   │   ├── cpu/                  # CPU 流式插件
│   │   └── jax/                  # JAX 流式插件（占位）
│   └── legacy/                   # 向后兼容层（弃用警告）
│
├── plugin_sets/                  # 可组合的插件集合
│   ├── io.py                     # I/O 插件集
│   ├── waveform.py               # 波形处理插件集
│   ├── basic_features.py         # 特征提取插件集
│   ├── tabular.py                # DataFrame 转换插件集
│   ├── events.py                 # 事件分组/配对插件集
│   └── signal_processing.py      # 信号处理插件集
│
├── profiles.py                   # 执行配置文件
└── __init__.py
```

---

## 2. 核心类与职责

### 2.1 基础插件系统 (`core/base.py`)

| 类 | 职责 |
|---|------|
| `Option` | 配置选项，支持验证、单位转换、范围约束、弃用警告 |
| `Plugin` (ABC) | 插件抽象基类，声明 `provides`、`depends_on`、`options`、`version` |
| `@option` | 装饰器，为插件类添加单个配置选项 |
| `@takes_config` | 装饰器，为插件类添加多个配置选项 |

**Plugin 核心属性**：

| 属性 | 类型 | 说明 |
|------|------|------|
| `provides` | `str` | 插件产出的数据名称 |
| `depends_on` | `List[Union[str, Tuple[str, str]]]` | 依赖列表（支持版本约束） |
| `options` | `Dict[str, Option]` | 配置选项字典 |
| `output_dtype` | `Optional[np.dtype]` | 输出数据类型 |
| `version` | `str` | 语义版本号，参与血缘追踪 |
| `is_side_effect` | `bool` | 是否为副作用插件（输出隔离） |
| `output_kind` | `Literal["static", "stream"]` | 输出类型 |

**Plugin 核心方法**：

| 方法 | 说明 |
|------|------|
| `compute(context, run_id, **kwargs)` | 主处理逻辑（抽象方法） |
| `validate()` | 注册时验证插件结构 |
| `validate_config(context)` | 验证并返回解析后的配置 |
| `resolve_depends_on(context, run_id)` | 动态依赖解析 |
| `on_error(context, exception)` | 错误处理钩子 |
| `cleanup(context)` | 资源清理钩子 |

### 2.2 插件规范 (`core/spec.py`)

| 类 | 用途 |
|---|------|
| `ConfigField` | 声明式配置规范（与运行时 `Option` 互补） |
| `FieldSpec` | 结构化数组输出的单字段描述 |
| `OutputSchema` | 完整输出数据 schema，支持从 dtype 自动创建 |
| `InputRequirement` | 输入依赖需求，支持版本约束和必需字段 |
| `Capabilities` | 插件能力声明（streaming, parallel, GPU, idempotent） |
| `PluginSpec` | 机器可读的插件完整契约 |

**PluginSpec 用途**：
- 注册时校验
- 文档自动生成
- Lineage hash 计算
- IDE 提示支持

### 2.3 流式处理框架 (`core/streaming.py`)

| 类 | 职责 |
|---|------|
| `StreamingPlugin` | 流式插件基类，处理 chunk 迭代器 |
| `StreamingContext` | 流式处理上下文管理器 |
| `Chunk` | 数据载体，封装数据与时间边界 |

**流式处理特性**：
- Chunk 级别的内存高效处理
- 时间边界验证与对齐
- 可选动态负载均衡
- Halo 扩展（边界填充）支持
- 与 ExecutorManager 集成的并行处理
- 静态数据到 chunk 流的自动转换

### 2.4 插件加载器 (`core/loader.py`)

| 类 | 职责 |
|---|------|
| `PluginLoader` | 动态插件发现与加载 |

**发现机制**：
- Entry points（通过 `importlib.metadata`）
- 目录扫描（`plugin.py`, `__init__.py`）
- 模块内省

---

## 3. 插件继承层次

```
Plugin (ABC)
├── RawFileNamesPlugin
├── WaveformsPlugin
├── FilteredWaveformsPlugin
├── SignalPeaksPlugin
├── HitFinderPlugin
├── BasicFeaturesPlugin
├── DataFramePlugin
├── GroupedEventsPlugin
├── PairedEventsPlugin
├── StreamingPlugin (ABC)
│   └── SignalPeaksStreamPlugin
└── [自定义插件]
```

---

## 4. 内置 CPU 插件

### 4.1 标准数据流

```
CSV Files
    ↓
RawFileNamesPlugin (raw_files)
    ↓
WaveformsPlugin (waveforms)
    ↓
FilteredWaveformsPlugin (filtered_waveforms) [可选]
    ↓
HitFinderPlugin (hits)
    ↓
BasicFeaturesPlugin (basic_features)
    ↓
DataFramePlugin (df)
    ↓
GroupedEventsPlugin (grouped_events)
    ↓
PairedEventsPlugin (paired_events)
```

### 4.2 插件详情

| 插件 | Provides | Depends On | 用途 |
|------|----------|-----------|------|
| RawFileNamesPlugin | `raw_files` | - | 扫描 CSV 文件，按通道分组 |
| WaveformsPlugin | `waveforms` | `raw_files` | 从 CSV 提取波形数据 |
| FilteredWaveformsPlugin | `filtered_waveforms` | `waveforms` | Butterworth/Savitzky-Golay 滤波 |
| SignalPeaksPlugin | `signal_peaks` | `waveforms` | scipy.signal 峰值检测 |
| HitFinderPlugin | `hits` | `waveforms` | Hit 事件检测 |
| BasicFeaturesPlugin | `basic_features` | `waveforms` | 计算幅度、上升时间等 |
| DataFramePlugin | `df` | `basic_features` | 转换为 pandas DataFrame |
| GroupedEventsPlugin | `grouped_events` | `df` | 时间窗口分组（Numba 加速） |
| PairedEventsPlugin | `paired_events` | `grouped_events` | 跨通道事件配对 |

---

## 5. 插件注册与依赖解析

### 5.1 注册流程

```python
ctx = Context(config={"data_root": "DAQ"})

# 方式 1: 注册插件实例
ctx.register(RawFileNamesPlugin())

# 方式 2: 注册插件类（自动实例化）
ctx.register(WaveformsPlugin)

# 方式 3: 批量注册
ctx.register(RawFileNamesPlugin(), WaveformsPlugin(), ...)

# 方式 4: 从模块注册
ctx.register(*profiles.cpu_default())

# 方式 5: 严格模式（要求 PluginSpec）
ctx.register(MyPlugin(), require_spec=True)
```

**注册步骤**：
1. 验证插件结构 (`plugin.validate()`)
2. 检查 `provides` 名称唯一性
3. 验证版本约束（如指定）
4. 存储到 `Context._plugins[data_name] = plugin`
5. 清除执行计划缓存

### 5.2 依赖解析流程

```python
# 用户调用
data = ctx.get_data("run_001", "paired_events")

# Context 内部流程：
# 1. 检查缓存: _results[(run_id, data_name)]
# 2. 分析依赖: 构建 DAG
# 3. 拓扑排序: 确定执行顺序
# 4. 按序执行插件
# 5. 缓存结果（含血缘哈希）
```

**关键方法**：
- `analyze_dependencies(target_name)` - 分析依赖图
- `get_lineage(data_name)` - 获取完整血缘（含配置/版本）
- `_get_plugin_dependency_names(plugin)` - 提取依赖名称
- `resolve_dependencies(data_name)` - 构建执行计划

---

## 6. 配置系统

### 6.1 配置层级

```python
# 全局配置
ctx.set_config({'n_channels': 2, 'threshold': 50})

# 插件特定配置（推荐）
ctx.set_config({'threshold': 50}, plugin_name='peaks')

# 嵌套字典格式
ctx.set_config({'peaks': {'threshold': 50}})

# 点分隔格式
ctx.set_config({'peaks.threshold': 50})
```

### 6.2 配置解析优先级

配置合并优先级（从高到低）：
1. **显式配置** - 用户通过 `set_config()` 设置
2. **Adapter 推断** - 从 DAQ adapter 自动推断
3. **插件默认值** - `plugin.options[key].default`

**核心组件**：
- `ConfigResolver` - 统一配置解析，支持多级来源
- `CompatManager` - 处理参数别名和弃用警告
- `AdapterInfo` - DAQ adapter 信息，用于配置推断
- `ResolvedConfig` - 解析后的配置，含来源追踪

---

## 7. 插件集与执行配置

### 7.1 插件集（可组合集合）

```python
# plugin_sets/io.py
def plugins_io():
    return [RawFileNamesPlugin()]

# plugin_sets/waveform.py
def plugins_waveform():
    return [WaveformsPlugin(), FilteredWaveformsPlugin()]

# plugin_sets/basic_features.py
def plugins_basic_features():
    return [HitFinderPlugin(), BasicFeaturesPlugin()]

# plugin_sets/tabular.py
def plugins_tabular():
    return [DataFramePlugin()]

# plugin_sets/events.py
def plugins_events():
    return [GroupedEventsPlugin(), PairedEventsPlugin()]
```

### 7.2 执行配置 (`profiles.py`)

```python
def cpu_default():
    """默认 CPU 配置（核心流水线）"""
    return (
        plugins_io()
        + plugins_waveform()
        + plugins_basic_features()
        + plugins_tabular()
        + plugins_events()
    )

# 使用
ctx.register(*profiles.cpu_default())
```

---

## 8. 数据流图

```
┌─────────────────────────────────────────────────────────────┐
│                      Context (调度器)                        │
│  - 插件注册表 (_plugins)                                     │
│  - 配置管理                                                  │
│  - 依赖解析 (DAG)                                           │
│  - 缓存管理 (_results)                                       │
│  - 血缘追踪                                                  │
└─────────────────────────────────────────────────────────────┘
                            ↓
                    ┌───────────────┐
                    │  get_data()   │
                    └───────────────┘
                            ↓
        ┌───────────────────┴───────────────────┐
        ↓                                       ↓
    ┌─────────┐                         ┌──────────────┐
    │  缓存   │ (命中)                   │ 分析依赖     │
    │  检查   │ ──→ 返回缓存数据         │ 构建 DAG     │
    └─────────┘                         └──────────────┘
                                                ↓
                                    ┌───────────────────┐
                                    │ 拓扑排序          │
                                    │ 执行计划          │
                                    └───────────────────┘
                                                ↓
                        ┌───────────────────────┴───────────────────────┐
                        ↓                                               ↓
                ┌──────────────────┐                          ┌──────────────────┐
                │ 执行插件 1       │                          │ 执行插件 N       │
                │ (compute)        │ ──→ ... ──→             │ (compute)        │
                └──────────────────┘                          └──────────────────┘
                        ↓                                               ↓
                ┌──────────────────┐                          ┌──────────────────┐
                │ 验证配置         │                          │ 验证配置         │
                │ 获取依赖         │                          │ 获取依赖         │
                └──────────────────┘                          └──────────────────┘
                        ↓                                               ↓
                ┌──────────────────┐                          ┌──────────────────┐
                │ 缓存结果         │                          │ 缓存结果         │
                │ 追踪血缘         │                          │ 追踪血缘         │
                └──────────────────┘                          └──────────────────┘
                        ↓                                               ↓
                        └───────────────────────┬───────────────────────┘
                                                ↓
                                        ┌──────────────┐
                                        │ 返回数据     │
                                        └──────────────┘
```

---

## 9. 关键架构模式

### 9.1 插件声明模式

```python
class MyPlugin(Plugin):
    provides = "my_data"
    depends_on = ["input_data"]
    version = "1.0.0"
    options = {
        "threshold": Option(default=10.0, type=float, help="阈值"),
    }

    def compute(self, context, run_id, **kwargs):
        input_data = context.get_data(run_id, "input_data")
        threshold = context.get_config(self, "threshold")
        # 处理数据
        return result
```

### 9.2 依赖解析模式

```python
# 静态依赖
depends_on = ["raw_files", "waveforms"]

# 带版本约束
depends_on = [("waveforms", ">=1.0.0"), ("peaks", "~=2.1.0")]

# 动态依赖
def resolve_depends_on(self, context, run_id=None):
    if context.get_config(self, "use_filtering"):
        return ["filtered_waveforms"]
    else:
        return ["waveforms"]
```

### 9.3 配置验证模式

```python
Option(
    default=10.0,
    type=float,
    help="阈值 (mV)",
    min_value=0.0,
    max_value=100.0,
    unit="mV",
    internal_unit="V",  # 自动转换
    track=True,  # 参与血缘计算
)
```

### 9.4 流式处理模式

```python
class MyStreamingPlugin(StreamingPlugin):
    provides = "stream_output"
    depends_on = ["input_stream"]
    output_kind = "stream"

    def compute_chunk(self, chunk, context, run_id, **kwargs):
        # 处理单个 chunk
        return processed_chunk
```

---

## 10. 血缘与缓存

### 10.1 血缘追踪

```python
lineage = ctx.get_lineage("paired_events")
# 返回:
{
    "plugin_class": "PairedEventsPlugin",
    "plugin_version": "1.0.0",
    "config": {"time_window_ns": 100},
    "depends_on": {
        "grouped_events": {
            "plugin_class": "GroupedEventsPlugin",
            "config": {...},
            "depends_on": {...}
        }
    },
    "dtype": [...],
    "spec_hash": "abc12345"
}
```

### 10.2 缓存键生成

```
key = SHA1(lineage_json + plugin_code + version + config + dtype)
```

### 10.3 缓存存储结构

```
storage_dir/
├── {run_id}/
│   ├── _cache/
│   │   ├── raw_files.bin
│   │   ├── waveforms.bin
│   │   └── ...
│   └── side_effects/
│       └── {plugin_name}/
│           └── data.bin
```

---

## 11. 高级特性

### 11.1 热重载 (`core/hot_reload.py`)

- 文件变更监控
- 自动模块重载
- 缓存一致性维护
- 自动重载守护线程

### 11.2 插件统计 (`core/stats.py`)

- 执行时间追踪
- 内存使用监控
- 性能分析
- 统计收集与报告

### 11.3 Strax 适配器 (`core/adapters.py`)

- 包装 strax 插件实现无缝集成
- 自动元数据提取
- 参数映射与兼容

### 11.4 插件加载器 (`core/loader.py`)

- Entry point 发现
- 目录扫描
- 模块内省
- 错误处理与日志

---

## 12. 架构特点总结

| 特性 | 说明 |
|------|------|
| **模块化组织** | 插件按加速器类型分类（CPU, JAX, Streaming） |
| **声明式契约** | PluginSpec 提供机器可读的插件规范 |
| **自动 DAG 解析** | Context 构建并执行依赖图 |
| **灵活配置** | 多级配置解析，支持 adapter 推断 |
| **可组合配置** | 插件集组合成执行配置 |
| **流式支持** | Chunk 级别的内存高效处理 |
| **完整缓存** | 基于血缘的缓存验证与原子写入 |
| **可扩展性** | 热重载、自定义适配器、插件发现机制 |
| **性能追踪** | 内置统计收集与分析 |
| **向后兼容** | Legacy 插件支持与弃用警告 |

---

## 相关文档

- [系统架构](ARCHITECTURE.md) - 完整系统架构
- [插件开发教程](../plugins/tutorials/SIMPLE_PLUGIN_GUIDE.md) - 从零开始写插件
- [插件开发完整指南](../development/plugin-development/plugin_guide.md) - 深入学习
- [PluginSpec 指南](../development/plugin-development/PLUGIN_SPEC_GUIDE.md) - 高级契约系统
- [流式插件指南](../plugins/guides/STREAMING_PLUGINS_GUIDE.md) - 流式处理开发
- [Plugin Set & Profile](../plugins/guides/PLUGIN_SET_PROFILE_GUIDE.md) - 插件集合与配置
