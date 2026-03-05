**导航**: [文档中心](../../README.md) > [插件系统](../README.md) > 最简单的插件教程

---

# 如何写一个最简单的 Plugin

> **适合人群**: 初学者

本教程将带你从零开始，创建一个最简单的插件。通过这个教程，你将学会插件的基本结构和如何注册使用插件。

> 文档同步说明：本页对应 `waveform_analysis/core/plugins/core/base.py` 顶部 `# DOC` 引用。

---

## 📋 目录

1. [最简单的插件](#最简单的插件)
2. [添加依赖](#添加依赖)
3. [添加配置选项](#添加配置选项)
4. [完整示例](#完整示例)
5. [注册和使用](#注册和使用)
6. [下一步](#下一步)

---

## 最简单的插件

让我们从一个最简单的插件开始，它不依赖任何其他插件，只返回一些数据。

### 步骤 1: 导入必要的类

```python
from waveform_analysis.core.plugins.core.base import Plugin
import numpy as np
```

### 步骤 2: 定义插件类

```python
class MyFirstPlugin(Plugin):
    """我的第一个插件"""

    # 必需：定义插件提供的数据名称
    provides = "my_first_data"

    # 必需：定义依赖（空列表表示无依赖）
    depends_on = []

    # 可选：定义输出数据类型
    output_dtype = np.dtype([('value', np.int32)])

    # 必需：实现 compute 方法
    def compute(self, context, run_id, **kwargs):
        """核心计算逻辑"""
        # 返回一些简单的数据
        return np.array([(1,), (2,), (3,)], dtype=self.output_dtype)
```

### 步骤 3: 使用插件

```python
from waveform_analysis.core.context import Context

# 创建 Context
ctx = Context(storage_dir="./cache")

# 注册插件
ctx.register(MyFirstPlugin())

# 使用插件获取数据
data = ctx.get_data("my_run", "my_first_data")
print(data)
# 输出: [(1,) (2,) (3,)]
```

**就这么简单！** 你已经创建了第一个插件！

---

## 添加依赖

现在让我们创建一个依赖其他插件的插件。这个插件将依赖 `st_waveforms` 数据。

```python
class MyDependentPlugin(Plugin):
    """依赖其他插件的示例"""

    provides = "my_processed_data"
    depends_on = ["st_waveforms"]  # 依赖 st_waveforms 插件

    def compute(self, context, run_id, **kwargs):
        """从 context 获取依赖的数据"""
        # 通过 context.get_data 获取依赖的数据
        st_waveforms = context.get_data(run_id, "st_waveforms")

        # 处理数据
        result = []
        for ch_data in st_waveforms:
            if len(ch_data) > 0:
                # 例如：计算每个事件的波形长度
                lengths = [len(w) for w in ch_data["wave"]]
                result.append(lengths)
            else:
                result.append([])

        return result
```

**关键点**:
- `depends_on` 列表定义了依赖的插件
- 使用 `context.get_data(run_id, "data_name")` 获取依赖数据
- Context 会自动处理依赖关系，确保依赖的插件先执行

### 动态依赖（可选）

当依赖需要根据配置切换（例如是否使用滤波波形）时，可以实现
`resolve_depends_on(context, run_id=None)` 来动态返回依赖列表。Context 会使用
解析后的依赖构建 DAG 和 lineage。

```python
class PeaksPlugin(Plugin):
    provides = "peaks"
    depends_on = ["st_waveforms"]
    options = {"use_filtered": Option(default=False, type=bool)}

    def resolve_depends_on(self, context, run_id=None):
        deps = ["st_waveforms"]
        if context.get_config(self, "use_filtered"):
            deps.append("filtered_waveforms")
        return deps
```

全局开关示例：

```python
ctx.set_config({"use_filtered": True})
```

---

## 添加配置选项

让我们添加配置选项，使插件更灵活：

```python
from waveform_analysis.core.plugins.core.base import Plugin, Option

class MyConfigurablePlugin(Plugin):
    """带配置选项的插件"""

    provides = "my_configurable_data"
    depends_on = ["st_waveforms"]

    # 定义配置选项
    options = {
        "threshold": Option(
            default=10.0,
            type=float,
            help="阈值参数，用于过滤数据"
        ),
        "multiplier": Option(
            default=2.0,
            type=float,
            help="乘数因子"
        ),
    }

    def compute(self, context, run_id, **kwargs):
        """使用配置选项"""
        # 获取配置值
        threshold = context.get_config(self, "threshold")
        multiplier = context.get_config(self, "multiplier")

        # 获取依赖数据
        st_waveforms = context.get_data(run_id, "st_waveforms")

        # 使用配置处理数据
        result = []
        for ch_data in st_waveforms:
            if len(ch_data) > 0:
                # 应用阈值和乘数
                processed = []
                for wave in ch_data["wave"]:
                    if np.max(wave) > threshold:
                        processed.append(wave * multiplier)
                result.append(processed)
            else:
                result.append([])

        return result
```

**使用配置**:

```python
# 注册插件
ctx.register(MyConfigurablePlugin())

# 设置配置
ctx.set_config({
    "threshold": 15.0,
    "multiplier": 3.0
}, plugin_name="my_configurable_data")

# 使用插件
data = ctx.get_data("my_run", "my_configurable_data")
```

---

## 完整示例

下面是一个完整的、可运行的示例：

```python
from waveform_analysis.core.plugins.core.base import Plugin, Option
from waveform_analysis.core.context import Context
import numpy as np

class SimpleCounterPlugin(Plugin):
    """简单的计数器插件 - 统计事件数量"""

    provides = "event_count"
    depends_on = ["st_waveforms"]
    description = "统计每个通道的事件数量"
    version = "1.0.0"

    options = {
        "min_events": Option(
            default=0,
            type=int,
            help="最小事件数阈值（用于过滤）"
        ),
    }

    def compute(self, context, run_id, **kwargs):
        """统计事件数量"""
        # 获取配置
        min_events = context.get_config(self, "min_events")

        # 获取依赖数据
        st_waveforms = context.get_data(run_id, "st_waveforms")

        # 统计每个通道的事件数
        counts = []
        for ch_data in st_waveforms:
            count = len(ch_data)
            if count >= min_events:
                counts.append(count)
            else:
                counts.append(0)

        return counts

# 使用示例
if __name__ == "__main__":
    # 创建 Context
    ctx = Context(storage_dir="./cache")

    # 注册标准插件（提供 st_waveforms）
    from waveform_analysis.core.plugins import (
        RawFilesPlugin,
        WaveformsPlugin,
    )
    ctx.register(
        RawFilesPlugin(),
        WaveformsPlugin(),
    )

    # 注册自定义插件
    ctx.register(SimpleCounterPlugin())

    # 设置配置
    ctx.set_config({
        "min_events": 5
    }, plugin_name="event_count")

    # 运行处理
    run_name = "my_run"
    counts = ctx.get_data(run_name, "event_count")

    print(f"各通道事件数: {counts}")
```

---

## 注册和使用

### 注册插件

有几种方式注册插件：

```python
# 方式 1: 单独注册
ctx.register(MyPlugin())

# 方式 2: 批量注册
ctx.register(
    MyPlugin1(),
    MyPlugin2(),
    MyPlugin3(),
)

# 方式 3: 使用列表
plugins = [MyPlugin1(), MyPlugin2(), MyPlugin3()]
ctx.register(*plugins)
```

### 使用插件数据

```python
# 获取插件提供的数据
data = ctx.get_data(run_id, "plugin_provides_name")

# 检查插件是否已注册
if "plugin_provides_name" in ctx.list_provided_data():
    data = ctx.get_data(run_id, "plugin_provides_name")
```

### 查看插件信息

```python
# 列出所有已注册的插件
print(ctx.list_provided_data())

# 查看插件依赖关系
ctx.analyze_dependencies("plugin_provides_name")
```

---

## 插件必需属性

每个插件必须定义以下属性：

| 属性 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `provides` | `str` | ✅ | 插件提供的数据名称（唯一标识） |
| `depends_on` | `List[str]`/`List[Tuple[str, str]]` | ✅ | 依赖的插件列表（支持版本约束元组） |
| `compute()` | `method` | ✅ | 核心计算逻辑方法 |

### 可选属性

| 属性 | 类型 | 说明 |
|------|------|------|
| `options` | `Dict[str, Option]` | 配置选项字典 |
| `output_dtype` | `np.dtype` | 输出数据类型（影响缓存与 lineage） |
| `input_dtype` | `Dict[str, np.dtype]` | 依赖数据期望 dtype（用于输入校验） |
| `output_kind` | `"static"`/`"stream"` | 输出类型（流式插件要求返回迭代器） |
| `description` | `str` | 插件描述 |
| `resolve_depends_on()` | `method` | 动态依赖解析（根据配置返回依赖列表） |
| `version` | `str` | 插件版本号（参与 lineage hash） |
| `save_when` | `str` | 缓存策略：`"never"`, `"target"`, `"always"` |
| `is_side_effect` | `bool` | 标记副作用插件（输出会隔离到 `_side_effects`） |
| `timeout` | `float` | 单次执行超时时间（秒，None 表示不限制） |

### 字段补充说明

- `depends_on`: 可写为 `["waveforms"]` 或 `[("waveforms", ">=1.0.0")]`。
- `output_kind`: `stream` 表示 `compute()` 必须返回 generator/iterator。
- `output_dtype`: 用于输出 dtype 校验、memmap 存储和 lineage。
- `input_dtype`: 仅在声明的依赖上生效，用于运行前 dtype 兼容检查。
- `is_side_effect`: 常用于绘图、导出、写文件等非数据产出场景。

### Option 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `default` | `Any` | 默认值 |
| `type` | `Type`/`tuple` | 类型检查与自动转换 |
| `help` | `str` | 配置说明 |
| `validate` | `callable` | 自定义校验函数，返回 bool |
| `track` | `bool` | 是否进入 lineage（默认 True） |

### 通过装饰器配置 options

如果希望把配置定义写得更清晰，可以使用装饰器 `@option` 或 `@takes_config`：

```python
from waveform_analysis.core.plugins.core.base import Plugin, Option, option, takes_config

@option("threshold", default=10.0, type=float, help="阈值参数")
class MyDecoratedPlugin(Plugin):
    provides = "my_data"
    depends_on = ["st_waveforms"]

    def compute(self, context, run_id, **kwargs):
        threshold = context.get_config(self, "threshold")
        return []
```

```python
@takes_config({
    "threshold": Option(default=10.0, type=float, help="阈值参数"),
    "window": Option(default=5, type=int, help="窗口长度"),
})
class MyMultiConfigPlugin(Plugin):
    provides = "my_data"
    depends_on = ["st_waveforms"]
```

---

## compute 方法签名

`compute` 方法的签名是：

```python
def compute(self, context: Any, run_id: str, **kwargs) -> Any:
    """
    Args:
        context: Context 实例，用于获取数据和配置
        run_id: 运行标识符（字符串）
        **kwargs: 其他参数（通常包含依赖数据）

    Returns:
        任意类型的数据（通常是 numpy 数组、列表或生成器）
    """
    pass
```

### 获取依赖数据

```python
def compute(self, context, run_id, **kwargs):
    # 方式 1: 通过 context.get_data（推荐）
    data = context.get_data(run_id, "dependency_name")

    # 方式 2: 通过 kwargs（如果依赖数据自动传入）
    data = kwargs.get("dependency_name")

    return processed_data
```

### 获取配置

```python
def compute(self, context, run_id, **kwargs):
    # 获取配置值
    threshold = context.get_config(self, "threshold")

    # 或者使用默认值
    threshold = context.get_config(self, "threshold", default=10.0)

    return processed_data
```

---

## 下一步

现在你已经学会了如何创建最简单的插件！接下来可以：

1. **学习更多高级功能**:
   - 查看 [插件开发完整指南](../../development/plugin-development/plugin_guide.md) 了解所有功能
   - 查看 [信号处理插件文档](SIGNAL_PROCESSING_PLUGINS.md) 学习复杂插件的实现

2. **查看实际插件示例**:
   - `waveform_analysis/core/plugins/builtin/cpu/standard.py` - 标准数据处理插件
   - `waveform_analysis/core/plugins/builtin/cpu/filtering.py` - 滤波插件

3. **学习最佳实践**:
   - 如何设计插件依赖关系
   - 如何优化插件性能
   - 如何测试插件

4. **快速验证新插件**:
   - 查看 [插件脚手架与测试夹具](../../development/plugin-development/PLUGIN_SCAFFOLD.md)

---

## 常见问题

### Q: 插件必须返回什么类型的数据？

A: 插件可以返回任何类型的数据，但通常返回：
- NumPy 数组（结构化数组或普通数组）
- Python 列表
- 生成器（用于流式处理）

### Q: 如何让插件支持缓存？

A: 设置 `save_when` 属性：
```python
class MyPlugin(Plugin):
    save_when = "target"  # 或 "always", "never"
```

### Q: 插件执行顺序是如何确定的？

A: Context 会根据 `depends_on` 或 `resolve_depends_on()` 的解析结果自动构建依赖图，确保依赖的插件先执行。

### Q: 可以在插件中访问其他插件吗？

A: 可以，通过 `context.get_data()` 获取任何已注册插件提供的数据。

---

**快速链接**:
[插件开发完整指南](../../development/plugin-development/plugin_guide.md) |
[信号处理插件文档](SIGNAL_PROCESSING_PLUGINS.md) |
[API 参考](../../api/README.md)
