# API 参考文档

> 自动生成于 2026-01-11 15:31:46

本文档包含 WaveformAnalysis 的完整 API 参考。

---

## 目录

- [Context](#context)
- [WaveformDataset](#waveformdataset)

---

## Context

The Context orchestrates plugins and manages data storage/caching.
Inspired by strax, it is the main entry point for data analysis.

### 方法

#### `__init__(self, storage_dir: str = './strax_data', config: Optional[Dict[str, Any]] = None, storage: Optional[Any] = None, plugin_dirs: Optional[List[str]] = None, auto_discover_plugins: bool = False, enable_stats: bool = False, stats_mode: str = 'basic', stats_log_file: Optional[str] = None, work_dir: Optional[str] = None, use_run_subdirs: bool = True)`

Initialize Context.

Args:
    storage_dir: 默认存储目录（使用 MemmapStorage 时的旧版模式）
    config: 全局配置字典
    storage: 自定义存储后端（必须实现 StorageBackend 接口）
            如果为 None，使用默认的 MemmapStorage
    plugin_dirs: 插件搜索目录列表
    auto_discover_plugins: 是否自动发现并注册插件
    enable_stats: 是否启用插件性能统计
    stats_mode: 统计模式 ('off', 'basic', 'detailed')
    stats_log_file: 统计日志文件路径
    work_dir: 工作目录（新版分层模式）。如果设置，数据将按 run_id 分目录存储。
    use_run_subdirs: 是否启用 run_id 子目录（仅当 work_dir 设置时生效）

Storage Modes:
    1. 旧版兼容模式（work_dir=None 且 storage_dir 有旧缓存）：
       - 所有文件在 storage_dir 根目录（扁平结构）

    2. 新版分层模式（work_dir=None 且 storage_dir 为空，或显式设置 work_dir）：
       - 数据按 run_id 分目录存储
       - 结构：work_dir/{run_id}/data/*.bin

Examples:
    >>> # 旧版兼容模式（storage_dir 有旧缓存会自动检测）
    >>> ctx = Context(storage_dir="./strax_data")

    >>> # 新版分层模式（显式指定 work_dir）
    >>> ctx = Context(work_dir="./workspace")

    >>> # 使用 SQLite 存储
    >>> from waveform_analysis.core.storage.backends import SQLiteBackend
    >>> ctx = Context(storage=SQLiteBackend("./data.db"))

    >>> # 启用详细统计和日志
    >>> ctx = Context(enable_stats=True, stats_mode='detailed', stats_log_file='./logs/plugins.log')

**示例:**

```python
>>> # 旧版兼容模式（storage_dir 有旧缓存会自动检测）
>>> ctx = Context(storage_dir="./strax_data")
```

---
#### `analyze_dependencies(self, target_name: str, include_performance: bool = True, run_id: Optional[str] = None)`

分析插件依赖关系，识别关键路径、并行机会和性能瓶颈

Args:
    target_name: 目标数据名称
    include_performance: 是否包含性能数据分析（需要enable_stats=True）
    run_id: 可选的run_id，用于获取特定运行的性能数据（暂未使用，为未来扩展预留）

Returns:
    DependencyAnalysisResult: 分析结果对象

Example:
    >>> ctx = Context(enable_stats=True)
    >>> # ... 注册插件并执行一些操作 ...
    >>> analysis = ctx.analyze_dependencies('paired_events')
    >>> print(analysis.summary())
    >>> analysis.to_markdown('report.md')  # 导出为 Markdown
    >>> data = analysis.to_dict()          # 导出为字典（可保存为 JSON）

    # 可视化增强
    >>> from waveform_analysis.utils.visualization import plot_lineage_labview
    >>> plot_lineage_labview(
    ...     ctx.get_lineage('paired_events'),
    ...     'paired_events',
    ...     context=ctx,
    ...     analysis_result=analysis,
    ...     highlight_critical_path=True,
    ...     highlight_bottlenecks=True
    ... )

**示例:**

```python
>>> ctx = Context(enable_stats=True)
>>> # ... 注册插件并执行一些操作 ...
>>> analysis = ctx.analyze_dependencies('paired_events')
>>> print(analysis.summary())
>>> analysis.to_markdown('report.md')  # 导出为 Markdown
>>> data = analysis.to_dict()          # 导出为字典（可保存为 JSON）
```

---
#### `build_time_index(self, run_id: str, data_name: str, time_field: str = 'time', endtime_field: Optional[str] = None, force_rebuild: bool = False)`

为数据构建时间索引

Args:
    run_id: 运行ID
    data_name: 数据名称
    time_field: 时间字段名
    endtime_field: 结束时间字段名('computed'表示计算endtime)
    force_rebuild: 强制重建索引

Examples:
    >>> # 预先构建索引以提高查询性能
    >>> ctx.build_time_index('run_001', 'st_waveforms', endtime_field='computed')

**示例:**

```python
>>> # 预先构建索引以提高查询性能
>>> ctx.build_time_index('run_001', 'st_waveforms', endtime_field='computed')
```

---
#### `check_cache_status(self, load_sig: bool = False) -> Dict[str, Dict[str, Any]]`

检查所有步骤的缓存状态。

Args:
    load_sig: 是否加载磁盘文件以验证签名（较慢）。


---
#### `clear_cache(self, step_name: Optional[str] = None) -> None`

清除指定步骤或所有步骤的缓存。


---
#### `clear_cache_for(self, run_id: str, data_name: Optional[str] = None, clear_memory: bool = True, clear_disk: bool = True, verbose: bool = True) -> int`

清理指定运行和步骤的缓存。

参数:
    run_id: 运行 ID
    data_name: 数据名称（步骤名称），如果为 None 则清理所有步骤
    clear_memory: 是否清理内存缓存
    clear_disk: 是否清理磁盘缓存
    verbose: 是否显示详细的清理信息

返回:
    清理的缓存项数量

示例:
    >>> ctx = Context()
    >>> # 清理单个步骤的缓存
    >>> ctx.clear_cache_for("run_001", "st_waveforms")
    >>> # 清理所有步骤的缓存
    >>> ctx.clear_cache_for("run_001")
    >>> # 只清理内存缓存
    >>> ctx.clear_cache_for("run_001", "df", clear_disk=False)


---
#### `clear_config_cache(self)`

Clear cached validated configurations.


---
#### `clear_performance_caches(self)`

Clear all performance optimization caches.

Should be called when plugins are registered/unregistered or
when plugin configurations change.


---
#### `clear_time_index(self, run_id: Optional[str] = None, data_name: Optional[str] = None)`

清除时间索引

Args:
    run_id: 运行ID,None则清除所有
    data_name: 数据名称,None则清除指定run_id的所有索引

Examples:
    >>> # 清除特定数据的索引
    >>> ctx.clear_time_index('run_001', 'st_waveforms')
    >>>
    >>> # 清除特定run的所有索引
    >>> ctx.clear_time_index('run_001')
    >>>
    >>> # 清除所有索引
    >>> ctx.clear_time_index()

**示例:**

```python
>>> # 清除特定数据的索引
>>> ctx.clear_time_index('run_001', 'st_waveforms')
>>>
>>> # 清除特定run的所有索引
>>> ctx.clear_time_index('run_001')
>>>
>>> # 清除所有索引
>>> ctx.clear_time_index()
```

---
#### `discover_and_register_plugins(self, allow_override: bool = False) -> int`

自动发现并注册插件

发现顺序：
1. Entry points (waveform_analysis.plugins)
2. 配置的插件目录

Args:
    allow_override: 是否允许覆盖已注册的插件

Returns:
    注册的插件数量


---
#### `get_cached_result(self, step_name: str) -> Optional[Dict[str, object]]`

返回指定步骤的内存缓存字典（若存在）。


---
#### `get_config(self, plugin: waveform_analysis.core.plugins.core.base.Plugin, name: str) -> Any`

获取插件的配置值（带验证和类型转换）。

这是获取插件配置的推荐方法。相比 _resolve_config_value，此方法会：
1. 应用插件选项的类型验证
2. 执行值的范围检查（如果定义）
3. 调用自定义验证器（如果存在）

配置支持命名空间，查找顺序同 _resolve_config_value。

Args:
    plugin: 目标插件实例
    name: 配置选项名称

Returns:
    验证并可能转换后的配置值

Raises:
    KeyError: 当插件没有该配置选项时
    ValueError: 当配置值不符合验证规则时
    TypeError: 当配置值类型不匹配时

Examples:
    >>> # 假设选项定义为 Option(type=int, validator=lambda x: 0 < x < 100)
    >>> ctx.config = {'my_plugin': {'threshold': '50'}}  # 字符串形式
    >>> ctx.get_config(plugin, 'threshold')
    50  # 自动转换为 int

    >>> ctx.config = {'threshold': 150}  # 超出范围
    >>> ctx.get_config(plugin, 'threshold')
    ValueError: threshold must satisfy validator

**示例:**

```python
>>> # 假设选项定义为 Option(type=int, validator=lambda x: 0 < x < 100)
>>> ctx.config = {'my_plugin': {'threshold': '50'}}  # 字符串形式
>>> ctx.get_config(plugin, 'threshold')
50  # 自动转换为 int
```

---
#### `get_data(self, run_id: str, data_name: str, show_progress: bool = False, progress_desc: Optional[str] = None, **kwargs) -> Any`

Retrieve data by name for a specific run.
If data is not in memory/cache, it will trigger the necessary plugins.

参数:
    run_id: Run identifier
    data_name: Name of the data to retrieve
    show_progress: Whether to show progress bar during plugin execution
    progress_desc: Custom description for progress bar (default: auto-generated)
    **kwargs: Additional arguments passed to plugins


---
#### `get_data_time_range(self, run_id: str, data_name: str, start_time: Optional[int] = None, end_time: Optional[int] = None, time_field: str = 'time', endtime_field: Optional[str] = None, auto_build_index: bool = True) -> numpy.ndarray`

查询数据的时间范围

Args:
    run_id: 运行ID
    data_name: 数据名称
    start_time: 起始时间(包含)
    end_time: 结束时间(不包含)
    time_field: 时间字段名
    endtime_field: 结束时间字段名('computed'表示计算endtime)
    auto_build_index: 自动构建时间索引

Returns:
    符合条件的数据子集

Examples:
    >>> # 查询特定时间范围的波形数据
    >>> data = ctx.get_data_time_range('run_001', 'st_waveforms',
    ...                                 start_time=1000000, end_time=2000000)
    >>>
    >>> # 查询所有数据后特定时间的记录
    >>> data = ctx.get_data_time_range('run_001', 'st_waveforms', start_time=1000000)

**示例:**

```python
>>> # 查询特定时间范围的波形数据
>>> data = ctx.get_data_time_range('run_001', 'st_waveforms',
...                                 start_time=1000000, end_time=2000000)
>>>
>>> # 查询所有数据后特定时间的记录
>>> data = ctx.get_data_time_range('run_001', 'st_waveforms', start_time=1000000)
```

---
#### `get_lineage(self, data_name: str, _visited: Optional[set] = None) -> Dict[str, Any]`

Get the lineage (recipe) for a data type.

Uses caching for performance optimization.


---
#### `get_performance_report(self, plugin_name: Optional[str] = None, format: str = 'text') -> Any`

获取插件性能统计报告

Args:
    plugin_name: 插件名称,None返回所有插件的统计
    format: 报告格式 ('text' 或 'dict')

Returns:
    性能报告(文本或字典格式)

Example:
    >>> ctx = Context(enable_stats=True, stats_mode='detailed')
    >>> # ... 执行一些插件 ...
    >>> print(ctx.get_performance_report())
    >>> # 或获取特定插件的统计
    >>> stats = ctx.get_performance_report(plugin_name='my_plugin', format='dict')

**示例:**

```python
>>> ctx = Context(enable_stats=True, stats_mode='detailed')
>>> # ... 执行一些插件 ...
>>> print(ctx.get_performance_report())
>>> # 或获取特定插件的统计
>>> stats = ctx.get_performance_report(plugin_name='my_plugin', format='dict')
```

---
#### `get_plugin(self, plugin_name: str) -> waveform_analysis.core.plugins.core.base.Plugin`

获取已注册的插件对象

返回插件对象，可以直接访问和修改其属性。

Args:
    plugin_name: 插件名称（provides 属性）

Returns:
    Plugin: 插件对象

Raises:
    KeyError: 当插件未注册时

Examples:
    >>> ctx = Context()
    >>> ctx.register(WaveformsPlugin())
    >>>
    >>> # 获取插件并修改属性
    >>> plugin = ctx.get_plugin('waveforms')
    >>> plugin.save_when = 'always'
    >>> plugin.timeout = 300
    >>>
    >>> # 链式调用
    >>> ctx.get_plugin('st_waveforms').save_when = 'never'
    >>>
    >>> # 查看插件配置
    >>> print(ctx.get_plugin('waveforms').save_when)
    >>> print(ctx.get_plugin('waveforms').options)

**示例:**

```python
>>> ctx = Context()
>>> ctx.register(WaveformsPlugin())
>>>
>>> # 获取插件并修改属性
>>> plugin = ctx.get_plugin('waveforms')
>>> plugin.save_when = 'always'
>>> plugin.timeout = 300
>>>
>>> # 链式调用
>>> ctx.get_plugin('st_waveforms').save_when = 'never'
>>>
>>> # 查看插件配置
>>> print(ctx.get_plugin('waveforms').save_when)
>>> print(ctx.get_plugin('waveforms').options)
```

---
#### `get_time_index_stats(self) -> Dict[str, Any]`

获取时间索引统计信息

Returns:
    统计信息字典

Examples:
    >>> stats = ctx.get_time_index_stats()
    >>> print(f"Total indices: {stats['total_indices']}")

**示例:**

```python
>>> stats = ctx.get_time_index_stats()
>>> print(f"Total indices: {stats['total_indices']}")
```

---
#### `help(self, topic: Optional[str] = None, search: Optional[str] = None, verbose: bool = False) -> str`

显示帮助信息

Args:
    topic: 帮助主题 ('quickstart', 'config', 'plugins', 'performance', 'examples')
    search: 搜索关键词（在方法名、插件名、配置项中搜索）
    verbose: 显示详细信息（新手模式）

Returns:
    帮助文本

Examples:
    >>> ctx.help()  # 显示快速参考
    >>> ctx.help('quickstart')  # 快速开始指南
    >>> ctx.help('config')  # 配置管理帮助
    >>> ctx.help(search='time_range')  # 搜索相关方法
    >>> ctx.help('quickstart', verbose=True)  # 详细模式

**示例:**

```python
>>> ctx.help()  # 显示快速参考
>>> ctx.help('quickstart')  # 快速开始指南
>>> ctx.help('config')  # 配置管理帮助
>>> ctx.help(search='time_range')  # 搜索相关方法
>>> ctx.help('quickstart', verbose=True)  # 详细模式
```

---
#### `key_for(self, run_id: str, data_name: str) -> str`

Get a unique key (hash) for a data type and run.

Uses caching for performance optimization.


---
#### `list_plugin_configs(self, plugin_name: Optional[str] = None, show_current_values: bool = True, verbose: bool = True) -> Dict[str, Any]`

列出所有插件的配置选项

显示每个插件可用的配置选项，包括：
- 选项名称
- 默认值
- 类型
- 帮助文本
- 当前配置值（如果已设置）

Args:
    plugin_name: 可选，指定插件名称以只显示该插件的配置
    show_current_values: 是否显示当前配置值
    verbose: 是否显示详细信息（类型、帮助文本等）

Returns:
    插件配置信息字典

Examples:
    >>> ctx = Context()
    >>> ctx.register(RawFilesPlugin(), WaveformsPlugin())
    >>>
    >>> # 列出所有插件的配置选项
    >>> ctx.list_plugin_configs()
    >>>
    >>> # 只列出特定插件的配置
    >>> ctx.list_plugin_configs(plugin_name='waveforms')
    >>>
    >>> # 获取配置字典而不打印
    >>> config_info = ctx.list_plugin_configs(verbose=False)

**示例:**

```python
>>> ctx = Context()
>>> ctx.register(RawFilesPlugin(), WaveformsPlugin())
>>>
>>> # 列出所有插件的配置选项
>>> ctx.list_plugin_configs()
>>>
>>> # 只列出特定插件的配置
>>> ctx.list_plugin_configs(plugin_name='waveforms')
>>>
>>> # 获取配置字典而不打印
>>> config_info = ctx.list_plugin_configs(verbose=False)
```

---
#### `list_provided_data(self) -> List[str]`

List all data types provided by registered plugins.


---
#### `plot_lineage(self, data_name: str, kind: str = 'labview', **kwargs)`

Visualize the lineage of a data type.

Args:
    data_name: Name of the target data.
    kind: Visualization style ('labview', 'mermaid', or 'plotly').
    **kwargs: Additional arguments passed to the visualizer.


---
#### `print_cache_report(self, verify: bool = False) -> None`

打印缓存状态报告。

Args:
    verify: 是否通过加载磁盘文件来验证签名（对于大文件可能较慢）。


---
#### `quickstart(self, template: str = 'basic', **params) -> str`

生成快速开始代码模板

Args:
    template: 模板名称 ('basic', 'basic_analysis', 'memory_efficient')
    **params: 模板参数（如 run_id, n_channels）

Returns:
    可执行的 Python 代码字符串

Examples:
    >>> code = ctx.quickstart('basic')
    >>> print(code)  # 或保存到文件
    >>>
    >>> # 自定义参数
    >>> code = ctx.quickstart('basic', run_id='run_002', n_channels=4)
    >>>
    >>> # 保存到文件
    >>> with open('my_analysis.py', 'w') as f:
    ...     f.write(ctx.quickstart('basic'))

**示例:**

```python
>>> code = ctx.quickstart('basic')
>>> print(code)  # 或保存到文件
>>>
>>> # 自定义参数
>>> code = ctx.quickstart('basic', run_id='run_002', n_channels=4)
>>>
>>> # 保存到文件
>>> with open('my_analysis.py', 'w') as f:
...     f.write(ctx.quickstart('basic'))
```

---
#### `register(self, *plugins: Union[waveform_analysis.core.plugins.core.base.Plugin, Type[waveform_analysis.core.plugins.core.base.Plugin], Any], allow_override: bool = False)`

注册一个或多个插件到 Context 中。

此方法是注册插件的便捷接口，支持多种输入类型：
- 插件实例：直接注册
- 插件类：自动实例化后注册
- Python 模块：自动发现模块中的所有 Plugin 子类并注册

注册后的插件可以通过其 `provides` 属性标识的数据名称来访问。
Context 会自动管理插件之间的依赖关系，并在获取数据时按需执行。

Args:
    *plugins: 要注册的插件，可以是以下类型之一：
        - Plugin 实例：已实例化的插件对象
        - Plugin 类：插件类，会自动调用无参构造函数实例化
        - Python 模块：包含 Plugin 子类的模块，会自动发现并注册所有插件类
    allow_override: 如果为 True，允许覆盖已注册的同名插件（基于 `provides` 属性）
                  如果为 False（默认），注册同名插件会抛出 RuntimeError

Raises:
    RuntimeError: 当尝试注册已存在的插件且 `allow_override=False` 时
    ValueError: 当插件验证失败时（通过 `plugin.validate()` 方法）
    TypeError: 当插件依赖版本不兼容时

Examples:
    >>> from waveform_analysis.core.context import Context
    >>> from waveform_analysis.core.plugins.builtin.standard import (
    ...     RawFilesPlugin, WaveformsPlugin, StWaveformsPlugin
    ... )
    >>>
    >>> ctx = Context(storage_dir="./strax_data")
    >>>
    >>> # 方式1: 注册插件实例
    >>> ctx.register(RawFilesPlugin())
    >>>
    >>> # 方式2: 注册插件类（会自动实例化）
    >>> ctx.register(WaveformsPlugin)
    >>>
    >>> # 方式3: 一次注册多个插件
    >>> ctx.register(
    ...     RawFilesPlugin(),
    ...     WaveformsPlugin(),
    ...     StWaveformsPlugin()
    ... )
    >>>
    >>> # 方式4: 注册模块中的所有插件
    >>> import waveform_analysis.core.plugins.builtin.standard as standard_plugins
    >>> ctx.register(standard_plugins)
    >>>
    >>> # 方式5: 允许覆盖已注册的插件
    >>> ctx.register(RawFilesPlugin(), allow_override=True)
    >>>
    >>> # 注册后可以通过数据名称访问
    >>> raw_files = ctx.get_data("run_001", "raw_files")

Notes:
    - 插件注册时会自动调用 `plugin.validate()` 进行验证
    - 注册插件会清除相关的执行计划缓存，确保依赖关系正确
    - 如果插件类需要参数，请先实例化再传入，不要直接传入类
    - 模块注册会递归查找所有 Plugin 子类，但会跳过 Plugin 基类本身

**示例:**

```python
>>> from waveform_analysis.core.context import Context
>>> from waveform_analysis.core.plugins.builtin.standard import (
...     RawFilesPlugin, WaveformsPlugin, StWaveformsPlugin
... )
>>>
>>> ctx = Context(storage_dir="./strax_data")
>>>
>>> # 方式1: 注册插件实例
>>> ctx.register(RawFilesPlugin())
>>>
>>> # 方式2: 注册插件类（会自动实例化）
>>> ctx.register(WaveformsPlugin)
>>>
>>> # 方式3: 一次注册多个插件
>>> ctx.register(
...     RawFilesPlugin(),
...     WaveformsPlugin(),
...     StWaveformsPlugin()
... )
>>>
>>> # 方式4: 注册模块中的所有插件
>>> import waveform_analysis.core.plugins.builtin.standard as standard_plugins
>>> ctx.register(standard_plugins)
>>>
>>> # 方式5: 允许覆盖已注册的插件
>>> ctx.register(RawFilesPlugin(), allow_override=True)
>>>
>>> # 注册后可以通过数据名称访问
>>> raw_files = ctx.get_data("run_001", "raw_files")
```

---
#### `register_plugin(self, plugin: Any, allow_override: bool = False) -> None`

Register a plugin instance with strict validation.


---
#### `resolve_dependencies(self, target: str) -> List[str]`

Resolve dependencies and return a list of data_names to compute in order.
Uses topological sort to determine execution order and detect cycles.


---
#### `run_plugin(self, run_id: str, data_name: str, show_progress: bool = False, progress_desc: Optional[str] = None, **kwargs) -> Any`

Override run_plugin to add saving logic and config resolution.

参数:
    run_id: Run identifier
    data_name: Name of the data to produce
    show_progress: Whether to show progress bar during plugin execution
    progress_desc: Custom description for progress bar (default: auto-generated)
    **kwargs: Additional arguments passed to plugins


---
#### `save_step_cache(self, step_name: str, path: str, backend: str = 'joblib') -> bool`

将当前内存缓存写入磁盘，格式与装饰器加载时期待的 persist 文件兼容。


---
#### `set_config(self, config: Dict[str, Any], plugin_name: Optional[str] = None)`

更新上下文配置。

支持三种配置方式：
1. 全局配置：set_config({'threshold': 50})
2. 插件特定配置（命名空间）：set_config({'threshold': 50}, plugin_name='my_plugin')
3. 嵌套字典格式：set_config({'my_plugin': {'threshold': 50}})

Args:
    config: 配置字典
    plugin_name: 可选，如果提供，则所有配置项都会作为该插件的命名空间配置

Examples:
    >>> # 全局配置
    >>> ctx.set_config({'n_channels': 2, 'threshold': 50})
    
    >>> # 插件特定配置（推荐，避免冲突）
    >>> ctx.set_config({'threshold': 50}, plugin_name='peaks')
    >>> # 等价于: ctx.set_config({'peaks': {'threshold': 50}})
    >>> # 或: ctx.set_config({'peaks.threshold': 50})
    
    >>> # 查看配置归属
    >>> ctx.list_plugin_configs()  # 列出所有插件的配置选项

**示例:**

```python
>>> # 全局配置
>>> ctx.set_config({'n_channels': 2, 'threshold': 50})
```

---
#### `set_step_cache(self, step_name: str, enabled: bool = True, attrs: Optional[List[str]] = None, persist_path: Optional[str] = None, watch_attrs: Optional[List[str]] = None, backend: str = 'joblib') -> None`

配置指定步骤的缓存。


---
#### `show_config(self, data_name: Optional[str] = None, show_usage: bool = True)`

显示当前配置，并标识每个配置项对应的插件

Args:
    data_name: 可选，指定插件名称以只显示该插件的配置
    show_usage: 是否显示配置项被哪些插件使用（仅在显示全局配置时有效）

Examples:
    >>> # 显示全局配置，包含配置项使用情况
    >>> ctx.show_config()

    >>> # 显示特定插件的配置
    >>> ctx.show_config('waveforms')

    >>> # 显示全局配置，但不显示使用情况
    >>> ctx.show_config(show_usage=False)

**示例:**

```python
>>> # 显示全局配置，包含配置项使用情况
>>> ctx.show_config()
```

---

## WaveformDataset

统一的波形数据集容器，封装整个数据处理流程。
支持链式调用，简化数据加载、预处理和分析。

使用示例：
    dataset = WaveformDataset(run_name="50V_OV_circulation_20thr", n_channels=2)
    dataset.load_raw_data().extract_waveforms().structure_waveforms()\
           .build_waveform_features().build_dataframe().group_events()\
           .pair_events().save_results()
    
    df_paired = dataset.get_paired_events()
    summary = dataset.summary()

### 方法

#### `__init__(self, run_name: str = '50V_OV_circulation_20thr', n_channels: int = 2, start_channel_slice: int = 6, data_root: str = 'DAQ', load_waveforms: bool = True, use_daq_scan: bool = False, daq_root: Optional[str] = None, daq_report: Optional[str] = None, cache_waveforms: bool = True, cache_dir: Optional[str] = None, **kwargs)`

初始化数据集。

参数:
    run_name: 数据集标识符
    n_channels: 要处理的通道数
    start_channel_slice: 开始通道索引（通常为 6 表示 CH6/CH7）
    data_root: 数据根目录
    load_waveforms: 是否加载原始波形数据（默认 True）
                   - True: 加载所有波形，支持 get_waveform_at()
                   - False: 仅加载特征（峰值、电荷等），节省内存 (70-80% 内存节省)
    cache_waveforms: 是否缓存提取后的波形数据到磁盘（默认 True）
    cache_dir: 缓存目录，默认为 outputs/_cache


---
#### `build_dataframe(self, verbose: bool = True) -> 'WaveformDataset'`

构建波形 DataFrame。


---
#### `build_waveform_features(self, peaks_range: Optional[Tuple[int, int]] = None, charge_range: Optional[Tuple[int, int]] = None, verbose: bool = True) -> 'WaveformDataset'`

计算波形特征（peaks 和 charges）。


---
#### `chainable_step(fn: Callable)`

Decorator for chainable steps with integrated caching and error handling.


---
#### `check_cache_status(self, load_sig: bool = False) -> Dict[str, Dict[str, Any]]`

检查所有步骤的缓存状态。

Args:
    load_sig: 是否加载磁盘文件以验证签名（较慢）。


---
#### `check_daq_status(self)`

尝试使用 DAQAnalyzer（或 JSON 报告）获取当前运行的元信息。

返回: dict 或 None（若没有找到）


---
#### `clear_cache(self, step_name: Optional[str] = None, clear_memory: bool = True, clear_disk: bool = True) -> int`

清理缓存。

参数:
    step_name: 步骤名称（如 "st_waveforms", "df"），如果为 None 则清理所有步骤
    clear_memory: 是否清理内存缓存
    clear_disk: 是否清理磁盘缓存

返回:
    清理的缓存项数量

示例:
    >>> ds = WaveformDataset(...)
    >>> # 清理单个步骤的缓存
    >>> ds.clear_cache("st_waveforms")
    >>> # 清理所有缓存
    >>> ds.clear_cache()
    >>> # 只清理内存缓存
    >>> ds.clear_cache("df", clear_disk=False)


---
#### `clear_step_errors(self) -> None`




---
#### `clear_waveforms(self) -> None`

释放波形相关的大块内存（waveforms 与 st_waveforms）。


---
#### `extract_waveforms(self, verbose: bool = True, **kwargs) -> 'WaveformDataset'`

从原始文件中提取波形数据。


---
#### `get_cached_result(self, step_name: str) -> Optional[Dict[str, object]]`

返回指定步骤的内存缓存字典（若存在）。


---
#### `get_error_statistics(self) -> Dict[str, Any]`

获取错误统计信息


---
#### `get_error_summary(self) -> Dict[str, Any]`

获取所有错误的汇总报告


---
#### `get_grouped_events(self) -> Optional[pandas.core.frame.DataFrame]`

获取分组后的事件 DataFrame。


---
#### `get_paired_events(self) -> Optional[pandas.core.frame.DataFrame]`

获取配对的事件 DataFrame。


---
#### `get_raw_events(self) -> Optional[pandas.core.frame.DataFrame]`

获取原始事件 DataFrame（未分组）。


---
#### `get_step_errors(self) -> Dict[str, Dict[str, Any]]`




---
#### `get_waveform_at(self, event_idx: int, channel: int = 0) -> Optional[Tuple[numpy.ndarray, float]]`

获取指定事件和通道的原始波形及其 baseline。

参数:
    event_idx: df_paired 中的事件索引
    channel: 通道索引（相对于 start_channel_slice）

返回: (波形数组, baseline) 或 None


---
#### `group_events(self, time_window_ns: Optional[float] = None, use_numba: bool = True, n_processes: Optional[int] = None, verbose: bool = True) -> 'WaveformDataset'`

按时间窗口聚类多通道事件。

参数:
    time_window_ns: 时间窗口（纳秒）
    use_numba: 是否使用numba加速（默认True）
    n_processes: 多进程数量（None=单进程，>1=多进程）
    verbose: 是否打印日志


---
#### `help(self, topic: Optional[str] = None, verbose: bool = False) -> str`

显示数据集使用帮助

Args:
    topic: 帮助主题（None/'workflow' 显示链式调用流程，其他主题转发给 Context）
    verbose: 显示详细信息

Examples:
    >>> ds.help()  # 显示工作流程
    >>> ds.help('workflow')  # 显示工作流程（同上）
    >>> ds.help('config')  # 转发给 ctx.help('config')

**示例:**

```python
>>> ds.help()  # 显示工作流程
>>> ds.help('workflow')  # 显示工作流程（同上）
>>> ds.help('config')  # 转发给 ctx.help('config')
```

---
#### `load_raw_data(self, verbose: bool = True) -> 'WaveformDataset'`

加载原始 CSV 文件。


---
#### `pair_events(self, n_channels: Optional[int] = None, start_channel_slice: Optional[int] = None, verbose: bool = True) -> 'WaveformDataset'`

筛选成对的 N 通道事件。


---
#### `print_cache_report(self, verify: bool = False) -> None`

打印缓存状态报告。

Args:
    verify: 是否通过加载磁盘文件来验证签名（对于大文件可能较慢）。


---
#### `save_results(self, output_dir: str = 'outputs', verbose: bool = True) -> 'WaveformDataset'`

保存处理结果（CSV 和 Parquet 格式）。

参数:
    output_dir: 输出目录
    verbose: 是否打印日志

返回: self（便于链式调用）


---
#### `save_step_cache(self, step_name: str, path: str, backend: str = 'joblib') -> bool`

将当前内存缓存写入磁盘，格式与装饰器加载时期待的 persist 文件兼容。


---
#### `set_raise_on_error(self, value: bool) -> None`

Toggle whether chainable steps raise on failure.


---
#### `set_step_cache(self, step_name: str, enabled: bool = True, attrs: Optional[List[str]] = None, persist_path: Optional[str] = None, watch_attrs: Optional[List[str]] = None, backend: str = 'joblib') -> None`

配置指定步骤的缓存。


---
#### `set_store_traceback(self, value: bool) -> None`

Toggle whether to store traceback in error info.


---
#### `structure_waveforms(self, verbose: bool = True) -> 'WaveformDataset'`

将波形数据转换为结构化 numpy 数组。


---
#### `summary(self) -> Dict[str, Any]`

获取数据处理摘要信息。

返回: 包含各个处理阶段信息的字典


---


---

**生成时间**: 2026-01-11 15:31:46
**工具**: WaveformAnalysis DocGenerator