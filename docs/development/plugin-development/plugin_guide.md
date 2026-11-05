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

```python
from waveform_analysis.core.plugins.core.base import Plugin, Option
import numpy as np

class MyCustomPlugin(Plugin):
    """自定义插件示例"""

    # 必需属性
    provides = 'my_data'
    depends_on = ['waveforms']
    version = '1.0.0'

    # 可选属性
    options = {
        'threshold': Option(
            default=10.0,
            type=float,
            help='阈值参数'
        ),
    }

    # 输出数据类型
    output_dtype = np.dtype([
        ('time', '<f8'),
        ('value', '<f4'),
    ])

    def compute(self, waveforms, run_id):
        """
        核心计算逻辑

        Args:
            waveforms: 依赖的数据（自动传入）
            run_id: 运行 ID

        Returns:
            结构化数组或生成器
        """
        # 获取配置
        threshold = self.config.get('threshold', 10.0)

        # 处理逻辑
        result = []
        for wf in waveforms:
            # ... 计算 ...
            pass

        return np.array(result, dtype=self.output_dtype)

# 注册插件
from waveform_analysis.core.context import Context
ctx = Context()
ctx.register(MyCustomPlugin())

# 使用插件
data = ctx.get_data('run_001', 'my_data')
```

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
