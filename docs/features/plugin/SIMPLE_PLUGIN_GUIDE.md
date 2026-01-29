# 插件开发教程

**导航**: [文档中心](../../README.md) > [功能特性](../README.md) > [插件功能](README.md) > 插件开发教程

本教程将带你从零开始创建一个最简单的插件。

## 最简单的插件

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
        return np.array([(1,), (2,), (3,)], dtype=self.output_dtype)
```

### 步骤 3: 使用插件

```python
from waveform_analysis.core.context import Context

ctx = Context(storage_dir="./cache")
ctx.register(MyFirstPlugin())

data = ctx.get_data("my_run", "my_first_data")
print(data)  # [(1,) (2,) (3,)]
```

## 添加依赖

创建一个依赖其他插件的插件：

```python
class MyDependentPlugin(Plugin):
    """依赖其他插件的示例"""

    provides = "my_processed_data"
    depends_on = ["st_waveforms"]  # 依赖 st_waveforms 插件

    def compute(self, context, run_id, **kwargs):
        # 通过 context.get_data 获取依赖的数据
        st_waveforms = context.get_data(run_id, "st_waveforms")

        result = []
        for ch_data in st_waveforms:
            if len(ch_data) > 0:
                lengths = [len(w) for w in ch_data["wave"]]
                result.append(lengths)
            else:
                result.append([])

        return result
```

### 动态依赖

当依赖需要根据配置切换时，实现 `resolve_depends_on` 方法：

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

## 添加配置选项

```python
from waveform_analysis.core.plugins.core.base import Plugin, Option

class MyConfigurablePlugin(Plugin):
    """带配置选项的插件"""

    provides = "my_configurable_data"
    depends_on = ["st_waveforms"]

    options = {
        "threshold": Option(
            default=10.0,
            type=float,
            help="阈值参数"
        ),
        "multiplier": Option(
            default=2.0,
            type=float,
            help="乘数因子"
        ),
    }

    def compute(self, context, run_id, **kwargs):
        threshold = context.get_config(self, "threshold")
        multiplier = context.get_config(self, "multiplier")

        st_waveforms = context.get_data(run_id, "st_waveforms")

        result = []
        for ch_data in st_waveforms:
            if len(ch_data) > 0:
                processed = []
                for wave in ch_data["wave"]:
                    if np.max(wave) > threshold:
                        processed.append(wave * multiplier)
                result.append(processed)
            else:
                result.append([])

        return result
```

使用配置：

```python
ctx.register(MyConfigurablePlugin())
ctx.set_config({
    "threshold": 15.0,
    "multiplier": 3.0
}, plugin_name="my_configurable_data")

data = ctx.get_data("my_run", "my_configurable_data")
```

## 完整示例

```python
from waveform_analysis.core.plugins.core.base import Plugin, Option
from waveform_analysis.core.context import Context
import numpy as np

class SimpleCounterPlugin(Plugin):
    """统计每个通道的事件数量"""

    provides = "event_count"
    depends_on = ["st_waveforms"]
    description = "统计每个通道的事件数量"
    version = "1.0.0"

    options = {
        "min_events": Option(
            default=0,
            type=int,
            help="最小事件数阈值"
        ),
    }

    def compute(self, context, run_id, **kwargs):
        min_events = context.get_config(self, "min_events")
        st_waveforms = context.get_data(run_id, "st_waveforms")

        counts = []
        for ch_data in st_waveforms:
            count = len(ch_data)
            counts.append(count if count >= min_events else 0)

        return counts

# 使用示例
if __name__ == "__main__":
    ctx = Context(storage_dir="./cache")

    from waveform_analysis.core.plugins import (
        RawFilesPlugin,
        WaveformsPlugin,
        StWaveformsPlugin,
    )
    ctx.register(
        RawFilesPlugin(),
        WaveformsPlugin(),
        StWaveformsPlugin(),
        SimpleCounterPlugin(),
    )

    ctx.set_config({"min_events": 5}, plugin_name="event_count")

    counts = ctx.get_data("my_run", "event_count")
    print(f"各通道事件数: {counts}")
```

## 注册和使用

```python
# 单独注册
ctx.register(MyPlugin())

# 批量注册
ctx.register(MyPlugin1(), MyPlugin2(), MyPlugin3())

# 使用列表
plugins = [MyPlugin1(), MyPlugin2(), MyPlugin3()]
ctx.register(*plugins)

# 获取数据
data = ctx.get_data(run_id, "plugin_provides_name")

# 查看已注册插件
print(ctx.list_provided_data())
```

## 插件属性参考

### 必需属性

| 属性 | 类型 | 说明 |
|------|------|------|
| `provides` | `str` | 插件提供的数据名称（唯一标识） |
| `depends_on` | `List[str]` | 依赖的插件列表 |
| `compute()` | `method` | 核心计算逻辑方法 |

### 可选属性

| 属性 | 类型 | 说明 |
|------|------|------|
| `options` | `Dict[str, Option]` | 配置选项字典 |
| `output_dtype` | `np.dtype` | 输出数据类型 |
| `output_kind` | `"static"/"stream"` | 输出类型 |
| `description` | `str` | 插件描述 |
| `version` | `str` | 插件版本号 |
| `save_when` | `str` | 缓存策略：`"never"`, `"target"`, `"always"` |
| `is_side_effect` | `bool` | 标记副作用插件 |
| `timeout` | `float` | 执行超时时间（秒） |

### Option 字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `default` | `Any` | 默认值 |
| `type` | `Type` | 类型检查与自动转换 |
| `help` | `str` | 配置说明 |
| `validate` | `callable` | 自定义校验函数 |
| `track` | `bool` | 是否进入 lineage（默认 True） |

### 装饰器配置

```python
from waveform_analysis.core.plugins.core.base import option, takes_config

@option("threshold", default=10.0, type=float, help="阈值参数")
class MyDecoratedPlugin(Plugin):
    provides = "my_data"
    depends_on = ["st_waveforms"]

    def compute(self, context, run_id, **kwargs):
        threshold = context.get_config(self, "threshold")
        return []

@takes_config({
    "threshold": Option(default=10.0, type=float),
    "window": Option(default=5, type=int),
})
class MyMultiConfigPlugin(Plugin):
    provides = "my_data"
    depends_on = ["st_waveforms"]
```

## compute 方法

```python
def compute(self, context, run_id, **kwargs):
    """
    Args:
        context: Context 实例
        run_id: 运行标识符
        **kwargs: 其他参数

    Returns:
        任意类型的数据（numpy 数组、列表或生成器）
    """
    # 获取依赖数据
    data = context.get_data(run_id, "dependency_name")

    # 获取配置
    threshold = context.get_config(self, "threshold")

    return processed_data
```

## 常见问题

**Q: 插件必须返回什么类型的数据？**

插件可以返回 NumPy 数组、Python 列表或生成器（流式处理）。

**Q: 如何让插件支持缓存？**

设置 `save_when` 属性：
```python
class MyPlugin(Plugin):
    save_when = "target"  # 或 "always", "never"
```

**Q: 插件执行顺序是如何确定的？**

Context 根据 `depends_on` 自动构建依赖图，确保依赖的插件先执行。

## 下一步

- [插件开发完整指南](../../api/plugin_guide.md) - 了解所有功能
- [信号处理插件](SIGNAL_PROCESSING_PLUGINS.md) - 学习复杂插件实现
- 查看源码：`waveform_analysis/core/plugins/builtin/cpu/`
