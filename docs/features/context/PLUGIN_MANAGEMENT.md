**导航**: [文档中心](../../README.md) > [功能特性](../README.md) > [Context 功能](README.md) > 插件管理

---

# 插件管理


本文档介绍如何在 Context 中注册、查询和管理插件。

---

## 📋 目录

1. [注册插件](#注册插件)
2. [查询已注册插件](#查询已注册插件)
3. [插件信息查看](#插件信息查看)
4. [批量注册](#批量注册)
5. [覆盖已注册插件](#覆盖已注册插件)
6. [常见问题](#常见问题)

---

## 注册插件

### 基本用法

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import (
    RawFilesPlugin,
    WaveformsPlugin,
)

# 创建 Context
ctx = Context(storage_dir="./cache")

# 注册单个插件实例
ctx.register(RawFilesPlugin())

# 注册插件类（会自动实例化）
ctx.register(WaveformsPlugin)
```

### 多种注册方式

```python
# 方式 1: 注册插件实例
ctx.register(RawFilesPlugin())

# 方式 2: 注册插件类（自动实例化）
ctx.register(WaveformsPlugin)

# 方式 3: 一次注册多个插件
ctx.register(
    RawFilesPlugin(),
    WaveformsPlugin()
)

# 方式 4: 注册模块中的所有插件
import waveform_analysis.core.plugins.builtin.cpu as cpu
ctx.register(cpu)  # 自动发现并注册模块中所有 Plugin 子类

# 方式 5: 使用列表批量注册
plugins = [RawFilesPlugin(), WaveformsPlugin()]
ctx.register(*plugins)
```

### 注册后使用

```python
# 注册后，通过数据名称访问
ctx.register(RawFilesPlugin())  # provides = "raw_files"
ctx.register(WaveformsPlugin())  # provides = "st_waveforms"

# 获取数据时自动执行插件
raw_files = ctx.get_data("run_001", "raw_files")
st_waveforms = ctx.get_data("run_001", "st_waveforms")
```

---

## 查询已注册插件

### 列出所有数据名称

```python
# 获取所有已注册插件提供的数据名称
data_names = ctx.list_provided_data()
print(data_names)
# ['raw_files', 'st_waveforms', 'basic_features', 'df', ...]
```

### 检查插件是否已注册

```python
# 检查特定数据是否可用
if "st_waveforms" in ctx.list_provided_data():
    data = ctx.get_data("run_001", "st_waveforms")
else:
    print("st_waveforms 插件未注册")
```

### 获取插件实例

```python
# 通过数据名称获取插件实例
plugin = ctx._plugins.get("st_waveforms")
if plugin:
    print(f"插件类: {plugin.__class__.__name__}")
    print(f"版本: {plugin.version}")
    print(f"依赖: {plugin.depends_on}")
```

---

## 插件信息查看

### 查看插件依赖关系

```python
# 获取执行计划（按依赖顺序）
plan = ctx.resolve_dependencies("paired_events")
print(plan)
# ['raw_files', 'st_waveforms', 'basic_features', 'df', 'df_events', 'df_paired']

# 可视化依赖关系
ctx.plot_lineage("paired_events")
```

### 查看插件配置选项

```python
# 列出所有插件的配置选项
ctx.list_plugin_configs()

# 只查看特定插件的配置
ctx.list_plugin_configs(plugin_name='waveforms')
```

### 分析依赖关系

```python
# 详细依赖分析
analysis = ctx.analyze_dependencies("paired_events")
print(analysis.summary())

# 查看关键路径
print(f"关键路径: {analysis.critical_path}")

# 查看并行机会
print(f"可并行组: {analysis.parallel_groups}")
```

---

## 批量注册

### 注册标准插件集

```python
from waveform_analysis.core.plugins.builtin.cpu import (
    RawFilesPlugin,
    WaveformsPlugin,
    BasicFeaturesPlugin,
    DataFramePlugin,
    GroupedEventsPlugin,
    PairedEventsPlugin,
)

# 一次注册完整的处理流水线
ctx.register(
    RawFilesPlugin(),
    WaveformsPlugin(),
    BasicFeaturesPlugin(),
    DataFramePlugin(),
    GroupedEventsPlugin(),
    PairedEventsPlugin(),
)
```

### 注册 records 管线插件

```python
from waveform_analysis.core.plugins.builtin.cpu import (
    RecordsPlugin,
)

ctx.register(
    RecordsPlugin(),
)
```

### 注册信号处理插件

```python
from waveform_analysis.core.plugins.builtin.cpu import (
    FilteredWaveformsPlugin,
    SignalPeaksPlugin,
)

ctx.register(
    FilteredWaveformsPlugin(),
    SignalPeaksPlugin(),
)
```

### 从模块自动发现

```python
# 注册整个模块中的所有插件
import waveform_analysis.core.plugins.builtin.cpu as cpu
ctx.register(cpu)

# 查看注册了哪些
print(ctx.list_provided_data())
```

---

## 覆盖已注册插件

### 默认行为（禁止覆盖）

```python
ctx.register(RawFilesPlugin())
ctx.register(RawFilesPlugin())  # RuntimeError: 插件已注册
```

### 允许覆盖

```python
# 使用 allow_override=True 允许覆盖
ctx.register(RawFilesPlugin())
ctx.register(RawFilesPlugin(), allow_override=True)  # 成功覆盖
```

### 覆盖场景

```python
# 场景：使用自定义版本替换内置插件
class MyCustomWaveformsPlugin(Plugin):
    provides = "waveforms"  # 与内置插件相同
    depends_on = ["raw_files"]

    def compute(self, context, run_id, **kwargs):
        # 自定义实现
        ...

# 先注册内置插件
ctx.register(WaveformsPlugin())

# 用自定义版本覆盖
ctx.register(MyCustomWaveformsPlugin(), allow_override=True)
```

---

## 注册验证

### 自动验证

注册时会自动调用 `plugin.validate()` 进行验证：

```python
class InvalidPlugin(Plugin):
    provides = "test"
    depends_on = ["nonexistent_plugin"]  # 依赖不存在的插件

    def compute(self, context, run_id, **kwargs):
        pass

# 注册时会警告（但不会阻止注册）
ctx.register(InvalidPlugin())
# Warning: Plugin 'test' depends on 'nonexistent_plugin' which is not registered
```

### 版本兼容性检查

```python
class VersionedPlugin(Plugin):
    provides = "processed"
    depends_on = [("waveforms", ">=1.0.0")]  # 要求 waveforms >= 1.0.0

    def compute(self, context, run_id, **kwargs):
        ...

# 如果版本不兼容会抛出 TypeError
ctx.register(VersionedPlugin())
```

---

## 执行期钩子与输出策略

Context 在执行插件时会识别以下可选钩子/属性，用于覆盖默认行为或调整输出策略：

- `get_lineage(context)`: 若插件实现，`Context.get_lineage()` 会优先使用它生成血缘信息。
- `clone()`: `Context.clone()` 复制插件时优先调用；否则使用 deepcopy 或无参构造回退。
- `on_error(context, exception)`: `compute()` 抛错时调用，可做日志或资源清理。
- `cleanup(context)`: `compute()` 结束后调用（成功/失败都会执行）。
- `output_kind`: 控制静态/流式输出，影响输出契约校验与保存方式。
- `output_dtype`: 用于 dtype 校验/转换，并参与 lineage hash。
- `save_when`/`is_side_effect`: 控制缓存写入时机与副作用输出目录（`_side_effects/{run_id}/{plugin}`）。
- `uses_run_config`: 标记插件会读取 `run_config` 的运行级配置，便于排查配置来源和运行链行为。

---

## 常见问题

### Q1: 如何知道插件提供什么数据？

**A**: 查看插件的 `provides` 属性：
```python
print(RawFilesPlugin.provides)  # 'raw_files'
print(WaveformsPlugin.provides)  # 'waveforms'
```

### Q2: 插件执行顺序如何确定？

**A**: Context 根据 `depends_on` 自动构建 DAG，按拓扑排序执行：
```python
plan = ctx.resolve_dependencies("target_data")
print(plan)  # 按依赖顺序排列
```

### Q3: 可以动态添加/移除插件吗？

**A**: 可以随时添加（使用 `register`），但移除需要谨慎：
```python
# 添加插件
ctx.register(NewPlugin())

# 移除插件（直接操作内部字典，不推荐）
# del ctx._plugins["plugin_name"]
```

### Q4: 如何查看插件的详细信息？

**A**: 使用 `list_plugin_configs()` 或直接访问插件属性：
```python
ctx.list_plugin_configs(plugin_name='waveforms')

# 或直接访问
plugin = ctx._plugins['waveforms']
print(f"版本: {plugin.version}")
print(f"选项: {plugin.options}")
print(f"描述: {plugin.description}")
```

---

## 相关文档

- [配置管理](CONFIGURATION.md) - 设置插件配置
- [数据获取](DATA_ACCESS.md) - 获取插件产出的数据
- [插件开发](../../development/plugin-development/README.md) - 开发自定义插件
- [Agent 入口](../../../AGENTS.md) - 任务导航与约束
- [Agent 文档索引](../../agents/INDEX.md) - agent 专题说明

---

**快速链接**: [配置管理](CONFIGURATION.md) | [数据获取](DATA_ACCESS.md) | [血缘可视化](LINEAGE_VISUALIZATION_GUIDE.md)
