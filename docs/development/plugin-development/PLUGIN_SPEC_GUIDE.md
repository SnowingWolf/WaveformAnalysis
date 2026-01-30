# PluginSpec 与 ConfigField 高级指南

**导航**: [文档中心](../../README.md) > [开发指南](../README.md) > [插件开发](README.md) > PluginSpec 高级指南

---

> **适合人群**: 框架开发者、高级用户
>
> 本文档介绍 `PluginSpec` 和 `ConfigField`，这是面向框架内部和高级场景的功能。[^source]
> 普通插件开发者只需使用 `Option` 定义配置即可。

---

## 概述

### Option vs ConfigField

| 特性 | Option | ConfigField |
|------|--------|-------------|
| **用途** | 运行时配置验证和类型转换 | 静态契约声明 |
| **使用场景** | 插件开发（必需） | 文档生成、lineage hash、IDE 提示（可选） |
| **定义位置** | `Plugin.options` | `PluginSpec.config_spec` |
| **自动提取** | - | 可从 `Option` 自动生成 |

### 为什么需要 PluginSpec？

`PluginSpec` 提供插件的**机器可读契约**，用于：

1. **注册时校验** - 确保插件定义完整且一致
2. **文档生成** - 自动生成 API 文档
3. **Lineage Hash** - 保证缓存一致性
4. **IDE 提示** - 提供类型信息和文档字符串
5. **依赖分析** - 版本兼容性检查

---

## ConfigField

### 定义

```python
from dataclasses import dataclass
from typing import Any, Optional

@dataclass(frozen=True)
class ConfigField:
    """配置字段规范"""
    type: str = "any"              # 类型名称（如 'float', 'int', 'str', 'bool'）
    default: Any = None            # 默认值
    doc: str = ""                  # 说明文档
    units: Optional[str] = None    # 物理单位（如 'ns', 'mV', 'Hz'）
    track: bool = True             # 是否纳入 lineage（默认 True）
    deprecated: Optional[str] = None  # 弃用信息
    alias_of: Optional[str] = None    # 别名指向的规范键名
```

### 属性说明

| 属性 | 类型 | 说明 |
|------|------|------|
| `type` | `str` | 类型名称字符串，如 `'float'`, `'int'`, `'str'`, `'bool'` |
| `default` | `Any` | 配置的默认值 |
| `doc` | `str` | 配置项的说明文档 |
| `units` | `Optional[str]` | 物理单位，如 `'ns'`（纳秒）, `'mV'`（毫伏）, `'Hz'`（赫兹） |
| `track` | `bool` | 是否纳入 lineage hash 计算（默认 `True`） |
| `deprecated` | `Optional[str]` | 弃用信息，如 `"Use 'new_option' instead"` |
| `alias_of` | `Optional[str]` | 如果是别名，指向规范键名 |

### 从 Option 创建

```python
from waveform_analysis.core.plugins.core import Option, ConfigField

opt = Option(default=10.0, type=float, help='Detection threshold')
cf = ConfigField.from_option(opt)

print(cf.type)     # 'float'
print(cf.default)  # 10.0
print(cf.doc)      # 'Detection threshold'
```

---

## PluginSpec

### 定义

```python
@dataclass
class PluginSpec:
    """插件完整契约规范"""
    name: str                                    # 插件类名
    provides: str                                # 提供的数据名称
    version: str                                 # 语义化版本号
    depends_on: Tuple[InputRequirement, ...] = ()  # 输入依赖列表
    output_schema: Optional[OutputSchema] = None   # 输出数据 schema
    config_spec: Dict[str, ConfigField] = {}       # 配置字段规范
    capabilities: Capabilities = Capabilities()    # 能力声明
    description: str = ""                          # 插件描述
    deprecated: Optional[str] = None               # 弃用信息
    superseded_by: Optional[str] = None            # 替代插件名称
```

## 插件属性

插件核心属性决定契约与依赖关系，通常包括：

- `provides`：插件输出的数据名（必须唯一）。
- `depends_on`：上游依赖的数据名列表。
- `version`：语义化版本号，变更行为时必须更新。
- `output_schema` / `config_spec`：输出与配置的静态契约。

这些属性会参与注册校验与 lineage hash，确保缓存一致性。

### 相关类


#### InputRequirement

```python
@dataclass(frozen=True)
class InputRequirement:
    """输入依赖需求"""
    name: str                              # 依赖的数据名称
    version_spec: Optional[str] = None     # 版本约束（PEP 440 格式）
    required_fields: Tuple[str, ...] = ()  # 需要的字段列表
    doc: str = ""                          # 需求说明
```

#### OutputSchema

```python
@dataclass(frozen=True)
class OutputSchema:
    """输出数据 schema"""
    fields: Tuple[FieldSpec, ...] = ()     # 字段规范列表
    dtype: Optional[str] = None            # NumPy dtype 字符串
    kind: str = "structured_array"         # 输出类型
    doc: str = ""                          # schema 说明
```

#### Capabilities

```python
@dataclass(frozen=True)
class Capabilities:
    """插件能力声明"""
    supports_streaming: bool = False   # 是否支持流式处理
    supports_parallel: bool = True     # 是否支持并行执行
    supports_gpu: bool = False         # 是否支持 GPU 加速
    idempotent: bool = True            # 是否幂等
    deterministic: bool = True         # 是否确定性
    time_field: Optional[str] = None   # 时间字段名称
```

---

## 使用方式

### 方式 1: 自动提取（推荐）

使用 `PluginSpec.from_plugin()` 从插件实例自动提取规范：

```python
from waveform_analysis.core.plugins.core import Plugin, Option, PluginSpec

class MyPlugin(Plugin):
    provides = 'my_data'
    version = '1.0.0'
    depends_on = ['st_waveforms']
    options = {
        'threshold': Option(default=10.0, type=float, help='Detection threshold'),
        'window_ns': Option(default=100, type=int, help='Window size in ns'),
    }

    def compute(self, context, run_id, **kwargs):
        return []

# 自动提取 spec
spec = PluginSpec.from_plugin(MyPlugin())

print(spec.config_spec['threshold'].type)     # 'float'
print(spec.config_spec['threshold'].default)  # 10.0
print(spec.config_keys)                       # ('threshold', 'window_ns')
```

### 方式 2: 手动定义 SPEC 属性

在插件类上定义 `SPEC` 属性，提供更丰富的元信息：

```python
from waveform_analysis.core.plugins.core import (
    Plugin, Option, PluginSpec, ConfigField,
    OutputSchema, FieldSpec, InputRequirement, Capabilities
)
import numpy as np

class AdvancedPlugin(Plugin):
    provides = 'advanced_data'
    version = '1.2.0'
    depends_on = [('st_waveforms', '>=1.0.0')]

    options = {
        'threshold_mv': Option(default=10.0, type=float, help='Threshold in mV'),
        'window_ns': Option(default=100, type=int, help='Window size'),
    }

    output_dtype = np.dtype([
        ('time', '<f8'),
        ('amplitude', '<f4'),
    ])

    # 手动定义 SPEC，提供更丰富的元信息
    SPEC = PluginSpec(
        name='AdvancedPlugin',
        provides='advanced_data',
        version='1.2.0',
        depends_on=(
            InputRequirement(
                name='st_waveforms',
                version_spec='>=1.0.0',
                required_fields=('time', 'wave'),
                doc='Structured waveform data'
            ),
        ),
        output_schema=OutputSchema(
            fields=(
                FieldSpec(name='time', dtype='<f8', units='ns', doc='Event time'),
                FieldSpec(name='amplitude', dtype='<f4', units='mV', doc='Peak amplitude'),
            ),
            kind='structured_array',
        ),
        config_spec={
            'threshold_mv': ConfigField(
                type='float',
                default=10.0,
                doc='Detection threshold',
                units='mV',
                track=True,
            ),
            'window_ns': ConfigField(
                type='int',
                default=100,
                doc='Analysis window size',
                units='ns',
                track=True,
            ),
        },
        capabilities=Capabilities(
            supports_streaming=False,
            supports_parallel=True,
            idempotent=True,
        ),
        description='Advanced signal processing plugin',
    )

    def compute(self, context, run_id, **kwargs):
        # ...
        return []
```

### 方式 3: 定义 spec() 方法

动态生成 spec：

```python
class DynamicSpecPlugin(Plugin):
    provides = 'dynamic_data'
    version = '1.0.0'
    options = {
        'threshold': Option(default=10.0, type=float, help='Threshold'),
    }

    def spec(self) -> PluginSpec:
        """动态生成 spec"""
        return PluginSpec.from_plugin(self)

    def compute(self, context, run_id, **kwargs):
        return []
```

---

## 注册时校验

### 启用严格校验

使用 `require_spec=True` 启用严格校验：

```python
from waveform_analysis.core import Context

ctx = Context(storage_dir='/tmp/test')

# 严格模式：要求插件必须有有效的 spec
ctx.register(MyPlugin(), require_spec=True)
```

### 校验内容

启用 `require_spec=True` 时，会校验：

1. **spec 存在性** - 插件必须有 `SPEC` 属性或 `spec()` 方法
2. **spec 类型** - 必须是 `PluginSpec` 实例
3. **spec 完整性** - `name`, `provides`, `version` 必须存在
4. **一致性检查** - `spec.provides` 必须与 `plugin.provides` 一致
5. **config_spec 匹配** - `spec.config_spec.keys()` 必须与 `plugin.options.keys()` 一致

### 校验失败示例

```python
class MismatchPlugin(Plugin):
    provides = 'mismatch'
    version = '1.0.0'
    options = {
        'threshold': Option(default=10.0, type=float),
        'extra_option': Option(default=1, type=int),  # spec 中缺少
    }

    SPEC = PluginSpec(
        name='MismatchPlugin',
        provides='mismatch',
        version='1.0.0',
        config_spec={
            'threshold': ConfigField(type='float', default=10.0),
            # 缺少 extra_option
        },
    )

# 这会抛出 ValueError
ctx.register(MismatchPlugin(), require_spec=True)
# ValueError: Plugin 'mismatch' config_spec mismatch: missing in spec: {'extra_option'}
```

---

## Lineage Hash

`PluginSpec.to_dict()` 返回可序列化的字典，用于计算 lineage hash：

```python
spec = PluginSpec.from_plugin(MyPlugin())
spec_dict = spec.to_dict()

# spec_dict 结构：
{
    'name': 'MyPlugin',
    'provides': 'my_data',
    'version': '1.0.0',
    'depends_on': [...],
    'output_schema': {...},
    'config_spec': {
        'threshold': {
            'type': 'float',
            'default': 10.0,
            'doc': 'Detection threshold',
            'units': None,
            'track': True,
            'deprecated': None,
            'alias_of': None,
        },
        ...
    },
    'capabilities': {...},
    'description': '...',
    'deprecated': None,
    'superseded_by': None,
}
```

只有 `track=True` 的配置项会影响 lineage hash。

---

## 向后兼容

### config_keys 属性

`PluginSpec.config_keys` 属性保留用于向后兼容：

```python
spec = PluginSpec(
    name='Test',
    provides='test',
    version='1.0.0',
    config_spec={
        'threshold': ConfigField(type='float'),
        'window': ConfigField(type='int'),
    },
)

# config_keys 返回配置键的元组
print(spec.config_keys)  # ('threshold', 'window')
```

---

## 最佳实践

### 1. 普通插件开发

对于普通插件，只需使用 `Option` 定义配置：

```python
class SimplePlugin(Plugin):
    provides = 'simple_data'
    version = '1.0.0'
    options = {
        'threshold': Option(default=10.0, type=float, help='Threshold'),
    }
```

框架会自动通过 `PluginSpec.from_plugin()` 提取规范。

### 2. 需要丰富元信息时

当需要提供物理单位、弃用信息等额外元信息时，手动定义 `SPEC`：

```python
class RichMetadataPlugin(Plugin):
    provides = 'rich_data'
    version = '1.0.0'
    options = {
        'threshold_mv': Option(default=10.0, type=float, help='Threshold'),
    }

    SPEC = PluginSpec(
        name='RichMetadataPlugin',
        provides='rich_data',
        version='1.0.0',
        config_spec={
            'threshold_mv': ConfigField(
                type='float',
                default=10.0,
                doc='Detection threshold',
                units='mV',  # 物理单位
            ),
        },
    )
```

### 3. 生产环境

在生产环境中，建议启用严格校验：

```python
ctx = Context(storage_dir='/data/cache')
ctx.register(MyPlugin(), require_spec=True)
```

---

## API 参考

### 导入

```python
from waveform_analysis.core.plugins.core import (
    # 基础类
    Plugin,
    Option,
    # Spec 相关
    PluginSpec,
    ConfigField,
    OutputSchema,
    FieldSpec,
    InputRequirement,
    Capabilities,
)
```

### ConfigField 方法

| 方法 | 说明 |
|------|------|
| `to_dict()` | 转换为可序列化的字典 |
| `from_option(opt)` | 从 Option 实例创建 ConfigField |

### PluginSpec 方法

| 方法 | 说明 |
|------|------|
| `to_dict()` | 转换为可序列化的字典（用于 lineage hash） |
| `validate()` | 校验 spec 完整性，返回错误列表 |
| `from_plugin(plugin)` | 从 Plugin 实例自动创建 PluginSpec |

### PluginSpec 属性

| 属性 | 说明 |
|------|------|
| `config_keys` | 向后兼容属性，返回 `tuple(config_spec.keys())` |

---

## 相关文档

- [简单插件教程](../../plugins/tutorials/SIMPLE_PLUGIN_GUIDE.md) - 插件开发入门
- [插件开发完整指南](plugin_guide.md) - 插件开发详细指南
- [API 参考](../../api/README.md) - 完整 API 文档

---

**快速链接**: [简单教程](../../plugins/tutorials/SIMPLE_PLUGIN_GUIDE.md) | [完整指南](plugin_guide.md) | [返回目录](README.md)

[^source]: 来源：`waveform_analysis/core/plugins/core/spec.py`。
