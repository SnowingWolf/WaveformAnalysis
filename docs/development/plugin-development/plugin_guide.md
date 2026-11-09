**导航**: [文档中心](../../README.md) > [development](../README.md) > [插件开发](README.md) > 插件开发完整指南

---

# 插件开发指南

本指南介绍如何开发自定义插件。

> 🎯 **初学者？** 如果你是第一次写插件，建议先阅读 [插件编写规范](../../plugins/PLUGIN_SYSTEM_OVERVIEW.md)，然后再回到这里深入学习。

---

## 插件架构概览

### 插件 Bundle 与公开入口

内置实现按产物组织为 Bundle；`cpu/` 中保留部分历史导入入口。新代码从
`waveform_analysis.plugins` 导入插件和 plugin set：

```python
from waveform_analysis import Context
from waveform_analysis.plugins import BasicFeaturesPlugin, plugins_io, plugins_waveform

ctx = Context(config={"data_root": "DAQ", "daq_adapter": "vx2730"})
ctx.register(*plugins_io(), *plugins_waveform(), BasicFeaturesPlugin())
features = ctx.get_data("run_001", "basic_features")
```

每个 Bundle 的实现、manifest、依赖与测试放在 `builtin/<产物>/` 中，例如：

```text
waveform_analysis/core/plugins/builtin/
├── raw_files/         # 原始文件发现
├── st_waveforms/      # 结构化波形
├── records/           # 记录元数据
├── wave_pool/         # 波形池
├── basic_features/    # 单记录基础特征
├── hit/               # 寻峰
├── peaks/             # 峰表
└── cpu/               # 保留的 CPU 实现和兼容导入
```

### 常用插件

| 插件 | 产物与职责 |
| --- | --- |
| `RawFileNamesPlugin` | `raw_files`：扫描并分组原始文件 |
| `WaveformsPlugin` | `st_waveforms`：构建结构化波形 |
| `RecordsPlugin`, `WavePoolPlugin` | `records`, `wave_pool`：记录元数据与波形池 |
| `BasicFeaturesPlugin` | `basic_features`：每条记录的面积、高度等基础特征 |
| `FilteredWaveformsPlugin` | `filtered_waveforms`：配置 Butterworth/SG 滤波 |
| `HitFinderPlugin` | `hit`：峰检测 |
| `PeaksPlugin` | `peaks`：从 peaklet 特征构建峰表 |

完整依赖、参数与字段以[内置插件参考](../../plugins/reference/agent/INDEX.md)为准。
使用多个阶段时优先选用[Plugin Set 与 Profile](../../plugins/PLUGIN_SYSTEM_OVERVIEW.md#plugin-sets)。

### 旧表格插件迁移

`DataFramePlugin`、`GroupedEventsPlugin`、`PairedEventsPlugin` 及其旧公开导入已移除。
单记录特征可用 `pd.DataFrame(features)` 转表；旧符合分组和配对需要单独保留或重写分析逻辑，
不能直接替换为 S1/S2 配对。配置、排序与标定处理见[退役迁移说明](../../user-guide/DF_RETIREMENT.md)。

---

## 插件基类

### Plugin

Base class for all processing plugins.
Inspired by strax, each plugin defines what it provides and what it depends on.

#### 核心方法

##### `cleanup(self, context: Any)`

Optional hook called after compute() finishes (successfully or not).
Useful for releasing resources like file handles.


---
##### `compute(self, context: Any, run_id: str, **kwargs) -> Any`

The actual processing logic.
The first argument is the running Context (contains config, cached data, etc.).
The second argument is the run_id being processed.
Implementations should access inputs via `context.get_data(run_id, 'input_name')`
or using `context.get_config(self, 'option_name')`.
Should return the data specified in 'provides'.


---
##### `get_dependency_name(self, dep: Union[str, Tuple[str, str]]) -> str`

从依赖规范中提取依赖名称。

插件的依赖可以是简单的字符串（插件名），也可以是包含版本约束的元组。
此方法统一提取依赖的名称部分。


**参数:**
- `dep`: 依赖规范，可以是： - 字符串：简单的插件名，如 "waveforms" - 元组：(插件名, 版本约束)，如 ("waveforms", ">=1.0.0")

**返回:**

提取的插件名称字符串

**示例**:

```python
>>> plugin.get_dependency_name("waveforms")
"waveforms"
>>> plugin.get_dependency_name(("waveforms", ">=1.0.0"))
"waveforms"
```

---
##### `get_dependency_version_spec(self, dep: Union[str, Tuple[str, str]]) -> Optional[str]`

从依赖规范中提取版本约束。

当依赖声明包含版本约束时（元组形式），提取版本规范字符串。
支持 PEP 440 版本说明符，如 ">=1.0.0", "==2.1.0", "~=1.2.0" 等。


**参数:**
- `dep`: 依赖规范，可以是： - 字符串：简单的插件名（无版本约束） - 元组：(插件名, 版本约束)

**返回:**

版本约束字符串，如果没有约束则返回 None

**示例**:

```python
>>> plugin.get_dependency_version_spec("waveforms")
None
>>> plugin.get_dependency_version_spec(("waveforms", ">=1.0.0"))
">=1.0.0"
```

---
##### `get_lineage(self, context: Any, *, dependency_resolver=None) -> dict`

Optional hook to override Context lineage generation.
If a plugin defines this method, `Context.get_lineage()` will use it instead of
the default lineage builder. This is useful when lineage needs to reflect
internal branching (e.g., adapter-specific paths) or custom dtype handling.
When the hook embeds upstream lineage, pass `dependency_resolver` to
`self._build_depends_lineage(context, dependency_resolver=dependency_resolver)`
or call it directly for a named dependency. This keeps adapter metadata at the
top level and makes cache keys independent of lookup order. The historical
`get_lineage(context)` signature remains supported for third-party plugins.

---
##### `on_error(self, context: Any, exception: Exception)`

Optional hook called when compute() raises an exception.


---
##### `validate(self)`

Validate the plugin structure and configuration.
Called during registration.


---

---

## 标准插件示例

内置插件的版本、依赖与配置选项由代码生成参考页，避免在本指南重复维护：

- [raw_files](../../plugins/reference/agent/raw_files.md)：DAQ 文件发现与 adapter 配置。
- [st_waveforms](../../plugins/reference/agent/st_waveforms.md)：`WaveformsPlugin` 的结构化波形输出。
- [basic_features](../../plugins/reference/agent/basic_features.md)：单记录特征与波形来源配置。

## 开发自定义插件

### 基本模板

以下示例只缩放配置中提供的数值，用于验证插件接入，不代表实际波形算法。
输出 `sample_index` 是从零开始的输入索引，`value` 与输入数值同单位，`scale` 无量纲；
空列表返回相同 dtype 的空表。

```python
import numpy as np
from waveform_analysis.plugins import Option, Plugin


class MyCustomPlugin(Plugin):
    """外置插件的最小可运行示例。"""

    provides = "my_data"
    depends_on = []
    version = "1.0.0"
    save_when = "target"
    options = {
        "values": Option(default=[], type=list, help="待缩放的一维数值列表"),
        "scale": Option(default=1.0, type=float, help="无量纲缩放系数"),
    }
    output_dtype = np.dtype([("sample_index", "<i8"), ("value", "<f8")])

    def compute(self, context, run_id: str, **kwargs):
        values = np.asarray(context.get_config(self, "values"), dtype=np.float64)
        if values.ndim != 1:
            raise ValueError("values 必须是一维数值列表")
        scale = context.get_config(self, "scale")
        result = np.empty(len(values), dtype=self.output_dtype)
        result["sample_index"] = np.arange(len(values))
        result["value"] = values * scale
        return result
```

真实插件通过 `depends_on` 声明正式上游产物，在 `compute(context, run_id, **kwargs)` 中
调用 `context.get_data(run_id, "上游产物名")` 读取。框架传入 Context，而不是把上游数组
直接作为第一个参数传入；配置通过 `context.get_config(self, "配置名")` 读取。

## 外置插件接入

外置插件可以独立于 WaveformAnalysis 仓库维护。注册到 Context 后，它参与同一套 DAG、
配置解析、lineage 和缓存机制。外置包不需要放进 `builtin/`，也不要求内置 bundle 的
`manifest.yaml`、主仓库公共导出表或内置 Profile；插件自身的输入输出和版本契约仍须完整。

### 独立包与安装

将上面的 `MyCustomPlugin` 保存到下列包的 `plugin.py`：

```text
my-analysis-plugins/
├── pyproject.toml
├── README.md
├── src/
│   └── my_analysis_plugins/
│       ├── __init__.py
│       └── plugin.py
└── tests/
    └── test_my_data.py
```

`src/my_analysis_plugins/__init__.py` 明确导出插件类：

```python
from .plugin import MyCustomPlugin

__all__ = ["MyCustomPlugin"]
```

`pyproject.toml` 的最小示例：

```toml
[build-system]
requires = ["setuptools>=61"]
build-backend = "setuptools.build_meta"

[project]
name = "my-analysis-plugins"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = ["waveform-analysis", "numpy"]

[tool.setuptools.packages.find]
where = ["src"]
```

在外置包根目录、使用运行分析的同一个 Python 环境执行：

```bash
python -m pip install -e .
```

上述依赖没有声明经过验证的兼容范围；发布时根据实际测试结果约束 `waveform-analysis`
和第三方依赖的版本。包版本用于分发，插件类的 `version` 用于行为与缓存契约，二者分别维护。

### 方式一：显式注册

适合分析脚本，也适合需要构造参数的插件。以下示例可以直接运行，无需 DAQ 文件：

```python
from waveform_analysis import Context
from my_analysis_plugins import MyCustomPlugin

ctx = Context(storage_dir="./example_cache")
ctx.register(MyCustomPlugin())
ctx.set_config({"values": [1.0, 2.0], "scale": 2.0}, plugin_name="my_data")
result = ctx.get_data("example_run", "my_data")
assert result["value"].tolist() == [2.0, 4.0]
```

真实算法还需注册它的所有上游；可以按需组合内置 Plugin Set / Profile 和自己的插件集合。
注册只加入 provider，不会立即计算。正式结果始终通过显式 `run_id` 请求。

### 方式二：entry points 自动发现

向外置包的 `pyproject.toml` 追加：

```toml
[project.entry-points."waveform_analysis.plugins"]
my_data = "my_analysis_plugins:MyCustomPlugin"
```

重新执行安装命令，使环境中的包元数据包含 entry point，然后显式触发发现：

```python
from waveform_analysis import Context

ctx = Context(storage_dir="./example_cache")
registered_count = ctx.discover_and_register_plugins()
ctx.set_config({"values": [1.0, 2.0], "scale": 2.0}, plugin_name="my_data")
result = ctx.get_data("example_run", "my_data")
```

也可以在创建 Context 时设置 `auto_discover_plugins=True`。默认是 `False`，仅安装包不会
自动注册。发现过程会扫描该组的所有已安装 entry points，并无参实例化插件类；需要构造
参数时使用显式实例注册。entry point 名称是发现标识，实际数据目标由类的 `provides` 决定。

### 方式三：目录扫描

适合简单的本地单文件插件。例如目录结构为：

```text
/absolute/path/to/local_plugins/
└── my_data/
    └── plugin.py
```

```python
from waveform_analysis import Context

ctx = Context(
    storage_dir="./example_cache",
    external_plugin_dirs=["/absolute/path/to/local_plugins"],
    auto_discover_plugins=True,
)
result = ctx.get_data("example_run", "my_data")  # 示例默认返回空表
```

扫描器递归检查 `plugin.py`；同目录没有该文件时，检查子目录的 `__init__.py`。
它不会扫描任意命名的 `.py` 文件，也不会读取 bundle manifest。目录扫描模式仍会先发现
已安装的 entry points。当前文件加载方式不建立完整的包导入上下文，因此有相对导入或
多进程导入需求的插件优先使用可安装包；第三方依赖也需事先安装到当前环境。

### 集成验收与维护

| 检查项 | 验收要求 |
| --- | --- |
| 产物契约 | `provides` 唯一，字段、dtype、单位、关联键、空输入与缺失值语义明确 |
| 依赖与配置 | 上游全部注册；静态和动态依赖一致；Option 默认值、类型和 help 完整 |
| 加载 | 目标类成功注册，实际请求目标产物通过；不能只检查发现函数没有抛异常 |
| 缓存 | 检查配置、插件版本和上游变化后的 lineage；持久化由 `save_when` 控制，基类默认 `never` |
| 测试 | 覆盖正常输入、空输入、边界、输出结构与实际下游链路；需要多进程或流式时单独验证 |
| 交付 | 外置包维护安装、配置、调用示例、兼容范围和版本记录；不自动进入主仓库内置插件参考页 |

当前自动发现会记录加载或注册失败并继续处理其他插件；返回值是成功注册的数量，
不能证明某个指定目标已注册。调试时可改为显式 import 和 `ctx.register()`，直接查看异常。
同一 `provides` 默认拒绝覆盖；只有确实要替换实现时才使用 `allow_override=True`。

插件行为、输出或配置语义改变时按[插件版本规则](../../plugins/PLUGIN_SYSTEM_OVERVIEW.md#插件-version-升级策略)
更新类的 `version`，不要只修改外置包版本。需要更严格的注册检查时，可以提供完整
PluginSpec，再使用 `ctx.register(plugin, require_spec=True)`，详见 [PluginSpec 指南](PLUGIN_SPEC_GUIDE.md)。

## 进阶开发

### 动态依赖

当插件依赖需要随配置切换时，可实现 `resolve_depends_on(context, run_id=None)`，
Context 会使用解析后的依赖构建 DAG 和 lineage。

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

### 最佳实践

1. **命名规范**
   - 类名: PascalCase (如 `MyCustomPlugin`)
   - provides: snake_case (如 `my_data`)
   - 版本号: 遵循 Semantic Versioning

2. **性能优化**
   - 使用生成器处理大数据
   - 利用 NumPy 向量化
   - 考虑使用 Numba JIT

3. **配置管理**
   - 使用 `Option` 定义配置项
   - 提供合理的默认值
   - 添加详细的帮助文本

4. **测试**
   - 为插件编写单元测试
   - 测试边界情况
   - 验证缓存一致性
