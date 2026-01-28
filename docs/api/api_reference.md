**导航**: [文档中心](../README.md) > [API 参考](README.md) > API 参考文档

# API 参考文档

> 自动生成于 2026-01-22 18:31:44

本文档包含 WaveformAnalysis 的完整 API 参考。

---

## 目录

- [Context](#context)

---

## Context

The Context orchestrates plugins and manages data storage/caching.
Inspired by strax, it is the main entry point for data analysis.

### 方法

#### `__init__(self, config: Union[Dict[str, Any], NoneType] = None, storage: Union[Any, NoneType] = None, storage_dir: Union[str, NoneType] = None, plugin_dirs: Union[List[str], NoneType] = None, auto_discover_plugins: bool = False, enable_stats: bool = False, stats_mode: str = 'basic', stats_log_file: Union[str, NoneType] = None)`

Initialize Context.


**参数:**
- `config`: 全局配置字典
- `可选配置`: config['plugin_backends'] = {'peaks': SQLiteBackend(...), ...}
- `storage_dir`: (Old:run_name)存储目录 (默认的 memmap 后端), 数据按 run_id 分目录存储。 如果为 None，将使用 config['data_root'] 作为存储目录。
- `storage`: 自定义存储后端（必须实现 StorageBackend 接口） 如果为 None，使用默认的 MemmapStorage
- `plugin_dirs`: 插件搜索目录列表
- `auto_discover_plugins`: 是否自动发现并注册插件
- `enable_stats`: 是否启用插件性能统计
- `stats_mode`: 统计模式 ('off', 'basic', 'detailed')
- `stats_log_file`: 统计日志文件路径 Storage Structure: 数据按 run_id 分目录存储：storage_dir/{run_id}/_cache/*.bin

**示例:**

```python
>>> # 使用 data_root 作为存储目录（推荐）
>>> ctx = Context(config={"data_root": "DAQ"})
>>> # 缓存将存储在 DAQ/{run_id}/_cache/
```

---
#### `analyze_cache(self, run_id: Union[str, NoneType] = None, verbose: bool = True) -> waveform_analysis.core.storage.cache_analyzer.CacheAnalyzer`

获取缓存分析器实例并执行扫描

创建一个 CacheAnalyzer 实例来分析缓存状态，支持按 run_id 过滤。


**参数:**
- `run_id`: 仅分析指定运行的缓存，None 则分析所有
- `verbose`: 是否显示扫描进度

**返回:**

CacheAnalyzer 实例（已完成扫描）

**示例:**

```python
>>> # 获取缓存分析器
>>> analyzer = ctx.analyze_cache()
>>>
>>> # 查看所有条目
>>> entries = analyzer.get_entries()
>>> print(f"共 {len(entries)} 个缓存条目")
>>>
>>> # 按条件过滤
>>> large = analyzer.get_entries(min_size=1024*1024)
>>> old = analyzer.get_entries(max_age_days=30)
>>>
>>> # 打印摘要
>>> analyzer.print_summary(detailed=True)
```

---
#### `analyze_dependencies(self, target_name: str, include_performance: bool = True, run_id: Union[str, NoneType] = None)`

分析插件依赖关系，识别关键路径、并行机会和性能瓶颈


**参数:**
- `target_name`: 目标数据名称
- `include_performance`: 是否包含性能数据分析（需要enable_stats=True）
- `run_id`: 可选的run_id，用于获取特定运行的性能数据（暂未使用，为未来扩展预留）

**返回:**

DependencyAnalysisResult: 分析结果对象

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
#### `auto_extract_epoch(self, run_id: str, strategy: str = 'auto', file_paths: Union[List[str], NoneType] = None) -> Any`

自动从数据文件提取 epoch


**参数:**
- `run_id`: 运行标识符
- `strategy`: 提取策略（"auto", "filename", "csv_header", "first_event"）
- `file_paths`: 数据文件路径列表（如果为 None，从 raw_files 获取）

**返回:**

提取的 EpochInfo 实例

**异常:**
- `ValueError`: 如果无法提取 epoch

**示例:**

```python
>>> # 自动提取（优先从文件名）
>>> epoch_info = ctx.auto_extract_epoch('run_001')
>>>
>>> # 指定策略
>>> epoch_info = ctx.auto_extract_epoch('run_001', strategy='filename')
```

---
#### `build_time_index(self, run_id: str, data_name: str, time_field: str = 'time', endtime_field: Union[str, NoneType] = None, force_rebuild: bool = False) -> Dict[str, Any]`

为数据构建时间索引

支持两种数据类型：
- 单个结构化数组: 构建单个索引
- List[np.ndarray]: 为每个通道分别构建索引


**参数:**
- `run_id`: 运行ID
- `data_name`: 数据名称
- `time_field`: 时间字段名
- `endtime_field`: 结束时间字段名('computed'表示计算endtime)
- `force_rebuild`: 强制重建索引

**返回:**

索引构建结果字典，包含： - 'type': 'single' 或 'multi_channel' - 'indices': 索引名称列表 - 'stats': 各索引的统计信息

**示例:**

```python
>>> # 为 st_waveforms (List[np.ndarray]) 构建多通道索引
>>> result = ctx.build_time_index('run_001', 'st_waveforms', endtime_field='computed')
>>> print(result['type'])  # 'multi_channel'
>>> print(result['indices'])  # ['st_waveforms_ch0', 'st_waveforms_ch1']
>>>
>>> # 为单个结构化数组构建索引
>>> ctx.build_time_index('run_001', 'basic_features')
```

---
#### `cache_stats(self, run_id: Union[str, NoneType] = None, detailed: bool = False, export_path: Union[str, NoneType] = None) -> waveform_analysis.core.storage.cache_statistics.CacheStatistics`

获取缓存统计信息

收集并显示缓存使用情况的统计信息。


**参数:**
- `run_id`: 仅统计指定运行，None 则统计所有
- `detailed`: 是否显示详细统计（按运行、按数据类型）
- `export_path`: 如果指定，导出统计到文件（支持 .json, .csv）

**返回:**

CacheStatistics 统计数据

**示例:**

```python
>>> # 获取基本统计
>>> stats = ctx.cache_stats()
>>>
>>> # 详细统计
>>> stats = ctx.cache_stats(detailed=True)
>>>
>>> # 特定运行的统计
>>> stats = ctx.cache_stats(run_id='run_001', detailed=True)
>>>
>>> # 导出统计
>>> stats = ctx.cache_stats(export_path='cache_stats.json')
```

---
#### `check_cache_status(self, load_sig: bool = False) -> Dict[str, Dict[str, Any]]`

检查所有步骤的缓存状态。


**参数:**
- `load_sig`: 是否加载磁盘文件以验证签名（较慢）。


---
#### `clear_cache(self, step_name: Union[str, NoneType] = None) -> None`

清除指定步骤或所有步骤的缓存。

注意：此方法来自 CacheMixin，用于清除旧的步骤级缓存系统（基于 _cache 和 _cache_config）。
对于 Context 的插件系统缓存，应该使用 clear_cache_for() 方法来清除运行级缓存。


**参数:**
- `step_name`: 步骤名称，如果为 None 则清除所有步骤的缓存
- `建议`: 对于 Context 的插件数据缓存，请使用 clear_cache_for(run_id, data_name) 方法。 此方法主要用于兼容旧的步骤级缓存系统。


---
#### `clear_cache_for(self, run_id: str, data_name: Union[str, NoneType] = None, clear_memory: bool = True, clear_disk: bool = True, verbose: bool = True) -> int`

清理指定运行和步骤的缓存。


**参数:**
- `run_id`: 运行 ID
- `data_name`: 数据名称（步骤名称），如果为 None 则清理所有步骤
- `clear_memory`: 是否清理内存缓存
- `clear_disk`: 是否清理磁盘缓存
- `verbose`: 是否显示详细的清理信息

**返回:**

清理的缓存项数量


---
#### `clear_config_cache(self)`

Clear cached validated configurations.


---
#### `clear_performance_caches(self)`

Clear all performance optimization caches.

Should be called when plugins are registered/unregistered or
when plugin configurations change.


---
#### `clear_time_index(self, run_id: Union[str, NoneType] = None, data_name: Union[str, NoneType] = None)`

清除时间索引


**参数:**
- `run_id`: 运行ID,None则清除所有
- `data_name`: 数据名称,None则清除指定run_id的所有索引

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
#### `diagnose_cache(self, run_id: Union[str, NoneType] = None, auto_fix: bool = False, dry_run: bool = True, verbose: bool = True) -> List[waveform_analysis.core.storage.cache_diagnostics.DiagnosticIssue]`

诊断缓存问题

检查缓存的完整性、版本一致性、孤儿文件等问题。


**参数:**
- `run_id`: 仅诊断指定运行，None 则诊断所有
- `auto_fix`: 是否自动修复可修复的问题
- `dry_run`: 如果 auto_fix=True，是否仅预演（不实际执行）
- `verbose`: 是否显示详细信息

**返回:**

List[DiagnosticIssue]

**示例:**

```python
>>> # 诊断所有缓存
>>> issues = ctx.diagnose_cache()
>>>
>>> # 诊断特定运行
>>> issues = ctx.diagnose_cache(run_id='run_001')
>>>
>>> # 自动修复（先 dry-run）
>>> issues = ctx.diagnose_cache(auto_fix=True, dry_run=True)
>>>
>>> # 实际修复
>>> issues = ctx.diagnose_cache(auto_fix=True, dry_run=False)
```

---
#### `discover_and_register_plugins(self, allow_override: bool = False) -> int`

自动发现并注册插件

发现顺序：
1. Entry points (waveform_analysis.plugins)
2. 配置的插件目录


**参数:**
- `allow_override`: 是否允许覆盖已注册的插件

**返回:**

注册的插件数量


---
#### `get_cached_result(self, step_name: str) -> Union[Dict[str, object], NoneType]`

返回指定步骤的内存缓存字典（若存在）。


---
#### `get_config(self, plugin: waveform_analysis.core.plugins.core.base.Plugin, name: str) -> Any`

获取插件的配置值（带验证和类型转换）。

这是获取插件配置的推荐方法。相比 _resolve_config_value，此方法会：
1. 应用插件选项的类型验证
2. 执行值的范围检查（如果定义）
3. 调用自定义验证器（如果存在）

配置支持命名空间，查找顺序同 _resolve_config_value。


**参数:**
- `plugin`: 目标插件实例
- `name`: 配置选项名称

**返回:**

验证并可能转换后的配置值

**异常:**
- `KeyError`: 当插件没有该配置选项时
- `ValueError`: 当配置值不符合验证规则时
- `TypeError`: 当配置值类型不匹配时

**示例:**

```python
>>> # 假设选项定义为 Option(type=int, validator=lambda x: 0 < x < 100)
>>> ctx.config = {'my_plugin': {'threshold': '50'}}  # 字符串形式
>>> ctx.get_config(plugin, 'threshold')
50  # 自动转换为 int
```

---
#### `get_data(self, run_id: str, data_name: str, show_progress: bool = False, progress_desc: Union[str, NoneType] = None, **kwargs) -> Any`

Retrieve data by name for a specific run.
If data is not in memory/cache, it will trigger the necessary plugins.


**参数:**
- `run_id`: Run identifier
- `data_name`: Name of the data to retrieve
- `show_progress`: Whether to show progress bar during plugin execution
- `progress_desc`: Custom description for progress bar (default: auto-generated) **kwargs: Additional arguments passed to plugins


---
#### `get_data_time_range(self, run_id: str, data_name: str, start_time: Union[int, NoneType] = None, end_time: Union[int, NoneType] = None, time_field: str = 'time', endtime_field: Union[str, NoneType] = None, auto_build_index: bool = True, channel: Union[int, NoneType] = None) -> Union[numpy.ndarray, List[numpy.ndarray]]`

查询数据的时间范围

支持两种数据类型：
- 单个结构化数组: 返回过滤后的数组
- List[np.ndarray]: 返回过滤后的列表（或指定通道的数组）


**参数:**
- `run_id`: 运行ID
- `data_name`: 数据名称
- `start_time`: 起始时间(包含)
- `end_time`: 结束时间(不包含)
- `time_field`: 时间字段名
- `endtime_field`: 结束时间字段名('computed'表示计算endtime)
- `auto_build_index`: 自动构建时间索引
- `channel`: 指定通道号（仅用于多通道数据），None 表示返回所有通道

**返回:**

符合条件的数据子集： - 单个数组数据: 返回 np.ndarray - 多通道数据: 返回 List[np.ndarray] 或指定通道的 np.ndarray

**示例:**

```python
>>> # 查询特定时间范围的波形数据（多通道）
>>> data = ctx.get_data_time_range('run_001', 'st_waveforms',
...                                 start_time=1000000, end_time=2000000)
>>> len(data)  # 返回列表，长度为通道数
2
>>>
>>> # 只查询特定通道
>>> ch0_data = ctx.get_data_time_range('run_001', 'st_waveforms',
...                                     start_time=1000000, end_time=2000000,
...                                     channel=0)
```

---
#### `get_data_time_range_absolute(self, run_id: str, data_name: str, start_dt: Union[datetime.datetime, NoneType] = None, end_dt: Union[datetime.datetime, NoneType] = None, time_field: str = 'time', endtime_field: Union[str, NoneType] = None, auto_build_index: bool = True, channel: Union[int, NoneType] = None, auto_extract_epoch: bool = True) -> Union[numpy.ndarray, List[numpy.ndarray]]`

使用绝对时间（datetime）查询数据

与 get_data_time_range() 功能相同，但使用 datetime 对象指定时间范围。


**参数:**
- `run_id`: 运行标识符
- `data_name`: 数据名称
- `start_dt`: 起始时间（datetime，包含）
- `end_dt`: 结束时间（datetime，不包含）
- `time_field`: 时间字段名
- `endtime_field`: 结束时间字段名
- `auto_build_index`: 自动构建时间索引
- `channel`: 指定通道号（仅用于多通道数据）
- `auto_extract_epoch`: 如果未设置 epoch，是否自动提取

**返回:**

符合条件的数据子集

**异常:**
- `ValueError`: 如果未设置 epoch 且无法自动提取

**示例:**

```python
>>> from datetime import datetime, timezone
>>>
>>> start = datetime(2024, 1, 1, 12, 0, 10, tzinfo=timezone.utc)
>>> end = datetime(2024, 1, 1, 12, 0, 20, tzinfo=timezone.utc)
>>>
>>> data = ctx.get_data_time_range_absolute(
...     'run_001', 'peaks',
...     start_dt=start, end_dt=end
... )
```

---
#### `get_epoch(self, run_id: str) -> Union[Any, NoneType]`

获取 run 的 epoch 元数据


**参数:**
- `run_id`: 运行标识符

**返回:**

EpochInfo 实例，如果未设置则返回 None

**示例:**

```python
>>> epoch_info = ctx.get_epoch('run_001')
>>> if epoch_info:
...     print(f"Epoch: {epoch_info.epoch_datetime}")
...     print(f"Source: {epoch_info.epoch_source}")
```

---
#### `get_lineage(self, data_name: str, _visited: Union[set, NoneType] = None) -> Dict[str, Any]`

Get the lineage (recipe) for a data type. Uses caching for performance optimization.


**参数:**
- `data_name`: The name of the data type for which to retrieve the lineage.
- `_visited`: Internal parameter used to track visited data names during recursion to detect and handle circular dependencies. Defaults to None.

**返回:**

A dictionary representing the lineage of the specified data type.


---
#### `get_performance_report(self, plugin_name: Union[str, NoneType] = None, format: str = 'text') -> Any`

获取插件性能统计报告


**参数:**
- `plugin_name`: 插件名称,None返回所有插件的统计
- `format`: 报告格式 ('text' 或 'dict')

**返回:**

性能报告(文本或字典格式)

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


**参数:**
- `plugin_name`: 插件名称（provides 属性）

**返回:**

Plugin: 插件对象

**异常:**
- `KeyError`: 当插件未注册时

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


**返回:**

统计信息字典

**示例:**

```python
>>> stats = ctx.get_time_index_stats()
>>> print(f"Total indices: {stats['total_indices']}")
```

---
#### `help(self, topic: Union[str, NoneType] = None, search: Union[str, NoneType] = None, verbose: bool = False) -> str`

显示帮助信息


**参数:**
- `topic`: 帮助主题 ('quickstart', 'config', 'plugins', 'performance', 'examples')
- `search`: 搜索关键词（在方法名、插件名、配置项中搜索）
- `verbose`: 显示详细信息（新手模式）

**返回:**

帮助文本

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
#### `list_plugin_configs(self, plugin_name: Union[str, NoneType] = None, show_current_values: bool = True, verbose: bool = True) -> Dict[str, Any]`

列出所有插件的配置选项

显示每个插件可用的配置选项，包括：
- 选项名称
- 默认值
- 类型
- 帮助文本
- 当前配置值（如果已设置）


**参数:**
- `plugin_name`: 可选，指定插件名称以只显示该插件的配置
- `show_current_values`: 是否显示当前配置值
- `verbose`: 是否显示详细信息（类型、帮助文本等）

**返回:**

插件配置信息字典

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


**参数:**
- `data_name`: Name of the target data.
- `kind`: Visualization style ('labview', 'mermaid', or 'plotly'). **kwargs: Additional arguments passed to the visualizer.


---
#### `preview_execution(self, run_id: str, data_name: str, show_tree: bool = True, show_config: bool = True, show_cache: bool = True, verbose: int = 1) -> Dict[str, Any]`

预览数据获取的执行计划（不实际执行计算）

在调用 get_data() 之前查看将要执行的操作，包括：
- 执行计划（插件执行顺序）
- 依赖关系树
- 配置参数（仅显示非默认值）
- 缓存状态（哪些数据已缓存，哪些需要计算）


**参数:**
- `run_id`: 运行标识符
- `data_name`: 要获取的数据名称
- `show_tree`: 是否显示依赖关系树
- `show_config`: 是否显示配置参数
- `show_cache`: 是否显示缓存状态
- `verbose`: 显示详细程度 (0=简洁, 1=标准, 2=详细)

**返回:**

包含执行计划详情的字典

**示例:**

```python
>>> # 基本预览
>>> ctx.preview_execution('run_001', 'signal_peaks')
```

---
#### `print_cache_report(self, verify: bool = False) -> None`

打印缓存状态报告。


**参数:**
- `verify`: 是否通过加载磁盘文件来验证签名（对于大文件可能较慢）。


---
#### `quickstart(self, template: str = 'basic', **params) -> str`

生成快速开始代码模板


**参数:**
- `template`: 模板名称 ('basic', 'basic_analysis') **params: 模板参数（如 run_id, n_channels）

**返回:**

可执行的 Python 代码字符串

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


**参数:**
- `allow_override`: 如果为 True，允许覆盖已注册的同名插件（基于 `provides` 属性） 如果为 False（默认），注册同名插件会抛出 RuntimeError

**异常:**
- `RuntimeError`: 当尝试注册已存在的插件且 `allow_override=False` 时
- `ValueError`: 当插件验证失败时（通过 `plugin.validate()` 方法）
- `TypeError`: 当插件依赖版本不兼容时

**注意:**
    - 插件注册时会自动调用 `plugin.validate()` 进行验证
    - 注册插件会清除相关的执行计划缓存，确保依赖关系正确
    - 如果插件类需要参数，请先实例化再传入，不要直接传入类
    - 模块注册会递归查找所有 Plugin 子类，但会跳过 Plugin 基类本身

**示例:**

```python
>>> from waveform_analysis.core.context import Context
>>> from waveform_analysis.core.plugins.builtin.cpu import (
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
>>> import waveform_analysis.core.plugins.builtin.cpu as standard_plugins
>>> ctx.register(standard_plugins)
>>>
>>> # 方式5: 允许覆盖已注册的插件
>>> ctx.register(RawFilesPlugin(), allow_override=True)
>>>
>>> # 注册后可以通过数据名称访问
>>> raw_files = ctx.get_data("run_001", "raw_files")
```

---
#### `register_plugin_(self, plugin: Any, allow_override: bool = False) -> None`

(DONT USE THIS METHOD DIRECTLY, USE CONTEXT.REGISTER INSTEAD)
Register a plugin instance with strict validation.


---
#### `resolve_dependencies(self, target: str) -> List[str]`

Resolve dependencies and return a list of data_names to compute in order.
Uses topological sort to determine execution order and detect cycles.


---
#### `run_plugin(self, run_id: str, data_name: str, show_progress: bool = False, progress_desc: Union[str, NoneType] = None, **kwargs) -> Any`

Override run_plugin to add saving logic and config resolution.


**参数:**
- `run_id`: Run identifier
- `data_name`: Name of the data to produce
- `show_progress`: Whether to show progress bar during plugin execution
- `progress_desc`: Custom description for progress bar (default: auto-generated) **kwargs: Additional arguments passed to plugins


---
#### `save_step_cache(self, step_name: str, path: str, backend: str = 'joblib') -> bool`

将当前内存缓存写入磁盘，格式与装饰器加载时期待的 persist 文件兼容。


---
#### `set_config(self, config: Dict[str, Any], plugin_name: Union[str, NoneType] = None)`

更新上下文配置。

支持三种配置方式：
1. 全局配置：set_config({'threshold': 50})
2. 插件特定配置（命名空间）：set_config({'threshold': 50}, plugin_name='my_plugin')
3. 嵌套字典格式：set_config({'my_plugin': {'threshold': 50}})


**参数:**
- `config`: 配置字典
- `plugin_name`: 可选，如果提供，则所有配置项都会作为该插件的命名空间配置

**示例:**

```python
>>> # 全局配置
>>> ctx.set_config({'n_channels': 2, 'threshold': 50})
```

---
#### `set_epoch(self, run_id: str, epoch: Union[datetime.datetime, float, str], time_unit: str = 'ns') -> None`

手动设置 run 的 epoch（时间基准）


**参数:**
- `run_id`: 运行标识符
- `epoch`: Epoch 值，支持多种格式： - datetime: Python datetime 对象 - float: Unix 时间戳（秒） - str: ISO 8601 格式字符串（如 "2024-01-01T12:00:00Z"）
- `time_unit`: 相对时间单位（"ps", "ns", "us", "ms", "s"）

**示例:**

```python
>>> from datetime import datetime, timezone
>>>
>>> # 使用 datetime 对象
>>> epoch = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
>>> ctx.set_epoch('run_001', epoch)
>>>
>>> # 使用 Unix 时间戳
>>> ctx.set_epoch('run_001', 1704110400.0)
>>>
>>> # 使用 ISO 字符串
>>> ctx.set_epoch('run_001', "2024-01-01T12:00:00Z")
```

---
#### `set_step_cache(self, step_name: str, enabled: bool = True, attrs: Union[List[str], NoneType] = None, persist_path: Union[str, NoneType] = None, watch_attrs: Union[List[str], NoneType] = None, backend: str = 'joblib') -> None`

配置指定步骤的缓存。


---
#### `show_config(self, data_name: Union[str, NoneType] = None, show_usage: bool = True)`

显示当前配置，并标识每个配置项对应的插件


**参数:**
- `data_name`: 可选，指定插件名称以只显示该插件的配置
- `show_usage`: 是否显示配置项被哪些插件使用（仅在显示全局配置时有效）

**示例:**

```python
>>> # 显示全局配置，包含配置项使用情况
>>> ctx.show_config()
```

---


**生成时间**: 2026-01-22 18:31:44
**工具**: WaveformAnalysis DocGenerator
