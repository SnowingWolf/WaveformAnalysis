**导航**: [文档中心](../../README.md) > [development](../README.md) > [插件开发](README.md) > 插件开发完整指南

---

# 插件开发指南

> 自动生成于 2026-01-11 19:23:26
> **更新**: 2026-01-12 - 添加按加速器划分的插件架构说明

本指南介绍如何开发自定义插件。

> 🎯 **初学者？** 如果你是第一次写插件，建议先阅读 [最简单的插件教程](../../plugins/tutorials/SIMPLE_PLUGIN_GUIDE.md)，然后再回到这里深入学习。

---

## 插件架构概览

### 按加速器划分的插件组织（Since 2026-01）

WaveformAnalysis 采用按计算加速器类型组织插件的架构，便于在不同硬件平台上优化性能：

```
waveform_analysis/core/plugins/builtin/
├── cpu/              # CPU 实现 (NumPy/SciPy/Numba)
│   ├── standard.py   # 标准数据处理插件（10个）
│   ├── filtering.py  # FilteredWaveformsPlugin
│   └── peak_finding.py # SignalPeaksPlugin
├── jax/              # JAX GPU 实现（待开发）
│   ├── filtering.py  # JAX 滤波插件
│   └── peak_finding.py # JAX 寻峰插件
├── streaming/        # 流式处理插件（待开发）
│   ├── cpu/
│   └── jax/
└── legacy/           # 向后兼容层（弃用）
```

### 导入插件（显式 CPU）

```python
from waveform_analysis.core.plugins.builtin.cpu import (
    RawFilesPlugin,
    FilteredWaveformsPlugin,
    SignalPeaksPlugin,
)
```

### 可用的 CPU 插件

#### 标准数据处理插件 (`cpu/standard.py`)
- `RawFilesPlugin`: 扫描和分组原始 CSV 文件
- `WaveformsPlugin`: 提取波形数据
- `StWaveformsPlugin`: 结构化波形数组
- `HitFinderPlugin`: 检测 Hit 事件
- `BasicFeaturesPlugin`: 计算基础特征
- `PeaksPlugin`: 峰值特征提取
- `ChargesPlugin`: 电荷积分
- `DataFramePlugin`: 构建 DataFrame
- `GroupedEventsPlugin`: 时间窗口分组（支持 Numba 加速）
- `PairedEventsPlugin`: 跨通道事件配对

#### 信号处理插件
- `FilteredWaveformsPlugin` (`cpu/filtering.py`): 波形滤波
  - Butterworth 带通滤波器
  - Savitzky-Golay 滤波器
- `SignalPeaksPlugin` (`cpu/peak_finding.py`): 高级峰值检测
  - 基于 scipy.signal.find_peaks
  - 支持导数检测、高度、距离、显著性等参数

> 📖 **详细文档**: 查看 [信号处理插件完整文档](../../plugins/tutorials/SIGNAL_PROCESSING_PLUGINS.md) 了解详细的使用方法、配置选项和示例。

### 迁移指南

如果你的代码使用旧的导入方式，建议迁移到新架构：

```python
# 旧方式（会发出弃用警告）
from waveform_analysis.core.plugins.builtin.cpu import RawFilesPlugin
from waveform_analysis.core.plugins.builtin.cpu import FilteredWaveformsPlugin

# 新方式（推荐）
from waveform_analysis.core.plugins.builtin.cpu import (
    RawFilesPlugin,
    FilteredWaveformsPlugin,
)
```

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
##### `get_lineage(self, context: Any) -> dict`

Optional hook to override Context lineage generation.
If a plugin defines this method, `Context.get_lineage()` will use it instead of
the default lineage builder. This is useful when lineage needs to reflect
internal branching (e.g., adapter-specific paths) or custom dtype handling.

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

以下是一些内置插件的实现示例，可作为开发参考。

### raw_files

**类名**: `RawFilesPlugin`
**版本**: 0.0.2
**提供数据**: `raw_files`
**依赖**: 无
Plugin to find raw CSV files.

**配置选项**:

- `data_root` (<class 'str'>): Root directory for data (默认: DAQ)
- `daq_adapter` (<class 'str'>): DAQ adapter name (默认: vx2730)

---
### waveforms

**类名**: `WaveformsPlugin`
**版本**: 0.0.2
**提供数据**: `waveforms`
**依赖**: raw_files
Plugin to extract waveforms from raw files.

**配置选项**:

- `channel_workers` (None): Number of parallel workers for channel-level processing (None=auto, uses min(len(raw_files), cpu_count)) (默认: None)
- `channel_executor` (<class 'str'>): Executor type for channel-level parallelism: 'thread' or 'process' (默认: thread)
- `n_jobs` (<class 'int'>): Number of parallel workers for file-level processing within each channel (默认: None)
- `use_process_pool` (<class 'bool'>): Whether to use process pool for file-level parallelism (默认: False)
- `chunksize` (<class 'int'>): Chunk size for CSV reading (默认: None)
- `daq_adapter` (<class 'str'>): DAQ adapter name (默认: vx2730)

---
### st_waveforms

**类名**: `StWaveformsPlugin`
**版本**: 0.0.0
**提供数据**: `st_waveforms`
**依赖**: waveforms
Plugin to structure waveforms into NumPy arrays.


---

---

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

---

**生成时间**: 2026-01-11 19:23:26
**工具**: WaveformAnalysis DocGenerator
