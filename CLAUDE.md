# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

WaveformAnalysis is a Python package for processing and analyzing DAQ (Data Acquisition) system waveform data. It features a **plugin-based architecture** inspired by strax, with support for both static and streaming data processing, automatic caching with lineage tracking, and memory-optimized workflows.

**Key Characteristics:**
- Plugin-based processing with automatic dependency resolution (DAG)
- Context-managed stateless execution (explicit `run_id` required)
- Zero-copy caching via `numpy.memmap` with atomic writes
- Streaming support for memory-efficient processing of large datasets
- Global executor management for thread/process pool reuse

## Development Commands

### Installation
```bash
# Quick install (recommended)
./install.sh

# Manual install (development mode)
pip install -e .

# With development dependencies
pip install -e ".[dev]"
```

### Testing
```bash
# Run tests (auto-activates conda env pyroot-kernel)
./scripts/run_tests.sh

# Or via Makefile
make test

# Run tests with specific pytest args
./scripts/run_tests.sh -v -k test_name

# Custom conda environment
CONDA_ENV=my-env ./scripts/run_tests.sh
```

### Benchmarking
```bash
# Run I/O benchmark
make bench

# Custom benchmark parameters
python scripts/benchmark_io.py --n-files 100 --n-channels 2 --n-samples 500 --reps 3
```

### Code Quality
```bash
# Format code (Black)
black waveform_analysis/ --line-length 100

# Type checking
mypy waveform_analysis/

# Run tests with coverage
pytest -v --cov=waveform_analysis --cov-report=html
```

### CLI Usage
```bash
# Process a run
waveform-process --run-name 50V_OV_circulation_20thr --verbose

# Scan DAQ directory
waveform-process --scan-daq --daq-root DAQ

# Show DAQ overview
waveform-process --show-daq --daq-root DAQ
```

## Configuration Management

WaveformAnalysis 提供灵活的配置系统，支持全局配置和插件特定配置。

### 查看插件配置选项

```python
# 列出所有插件的配置选项
ctx.list_plugin_configs()

# 只查看特定插件的配置
ctx.list_plugin_configs(plugin_name='waveforms')

# 获取配置字典而不打印（用于程序化处理）
config_info = ctx.list_plugin_configs(verbose=False)
```

`list_plugin_configs()` 功能特性：
- 📦 显示所有插件的配置选项、默认值、类型和帮助文本
- ✓/⚙️ 图标区分默认值和已修改的配置
- 🔧 明确标记已自定义的配置值
- 📊 统计已注册插件数、配置选项总数和已修改配置数
- 📝 自动换行处理长描述和帮助文本
- 🎨 清晰的表格边框和层次结构

### 查看当前配置值

```python
# 显示全局配置（包含配置项使用情况）
ctx.show_config()

# 显示特定插件的详细配置
ctx.show_config('waveforms')

# 显示全局配置但不显示使用情况
ctx.show_config(show_usage=False)
```

`show_config()` 增强功能特性：
- 🔍 **智能分析配置项使用情况** - 自动识别哪些插件使用了每个全局配置项
- 📂 **三类配置分组显示**：
  - **全局配置项** - 被插件使用的配置，显示使用插件列表
  - **插件特定配置** - 仅对单个插件生效的配置（嵌套字典或点分隔）
  - **未使用配置** - 未被任何插件使用的配置项（帮助发现配置错误）
- ⚙️ **详细的插件配置视图** - 查看特定插件时显示完整信息：
  - 配置值与默认值对比
  - 配置项类型和说明
  - 自定义状态标记
- 📊 **统计概览** - 一目了然地看到配置项分布情况

### 设置配置

```python
# 全局配置
ctx.set_config({'n_channels': 2, 'threshold': 50})

# 插件特定配置（推荐，避免冲突）
ctx.set_config({'threshold': 50}, plugin_name='peaks')

# 查看当前配置值
ctx.show_config('plugin_name')
```

### 配置解析系统 (ConfigResolver) [NEW - 2026-01]

WaveformAnalysis 提供统一的配置解析系统，支持多级配置来源和 adapter 推断。

#### 配置优先级

配置合并优先级（从高到低）：
1. **显式配置** - 用户通过 `set_config()` 设置
2. **Adapter 推断** - 从 DAQ adapter 自动推断（如采样率、时间间隔）
3. **插件默认值** - `plugin.options[key].default`

#### 查看解析后的配置

```python
# 获取解析后的配置（包含来源信息）
resolved = ctx.get_resolved_config('peaks', adapter_name='vx2730')
print(resolved.summary(verbose=True))

# 显示配置及来源
ctx.show_resolved_config('peaks')
```

#### 可推断的配置项

以下配置项可从 DAQ adapter 自动推断：

| 配置项 | 说明 | 示例值 (VX2730) |
|--------|------|-----------------|
| `sampling_rate_hz` | 采样率 (Hz) | 500000000.0 |
| `sampling_rate` / `fs` | 采样率 (GHz) | 0.5 |
| `dt_ns` / `sampling_interval_ns` | 采样间隔 (ns) | 2.0 |
| `dt_ps` | 采样间隔 (ps) | 2000.0 |
| `timestamp_unit` | 时间戳单位 | 'ps' |
| `expected_samples` | 预期采样点数 | 1030 |

#### 兼容层管理 (CompatManager)

处理参数别名和弃用警告：

```python
from waveform_analysis.core.config import CompatManager, DeprecationInfo

# 注册参数别名
CompatManager.register_alias('old_param', 'new_param', plugin_name='peaks')

# 注册弃用信息
CompatManager.register_deprecation(DeprecationInfo(
    old_name='break_threshold_ns',
    new_name='break_threshold_ps',
    deprecated_in='1.1.0',
    removed_in='2.0.0'
))

# 查看兼容层摘要
manager = CompatManager()
print(manager.summary())
```

**弃用过期检查**：当前版本 >= `removed_in` 时，使用已弃用参数会抛出 `ValueError`。

## Architecture Overview

### Core Structure (Modular Subdirectories)

从 2026-01 版本开始，`core/` 目录采用**模块化子目录架构**，将原本扁平的 27 个文件重构为 6 个功能子目录：

- **`storage/`**: 存储层（memmap, backends, cache, compression, integrity）
- **`execution/`**: 执行层（manager, config, timeout）
- **`plugins/`**: 插件系统（分离 core/ 和 builtin/）
- **`processing/`**: 数据处理（loader, processor, analyzer, chunk）
- **`data/`**: 数据管理（query, export）
- **`foundation/`**: 框架基础（exceptions, mixins, model, utils, progress）

核心文件 `context.py` 和 `dataset.py` 保持在 core/ 根目录。

新增模块：
- **`config/`**: 配置系统（resolver, compat, adapter_info, types）

### Core Components

1. **Context Layer** (`core/context.py`)
   - Central coordinator managing plugins, configuration, and caching
   - **Stateless**: All operations require explicit `run_id` parameter
   - Data stored in `_results[(run_id, data_name)]`
   - Automatic dependency resolution with cycle detection
   - Lineage-based caching with SHA1 hashing of plugin code, version, config, dtype

2. **Plugin System** (`core/plugins/`)
   - **Modular**: Core infrastructure (`plugins/core/`) 与内置插件（`plugins/builtin/`）分离
   - **Accelerator-based Architecture** (since 2026-01): 按加速器划分插件
     - `builtin/cpu/`: CPU 实现（NumPy/SciPy/Numba）
     - `builtin/jax/`: JAX GPU 实现（待开发）
     - `builtin/streaming/`: 流式处理插件（CPU 已有 SignalPeaksStreamPlugin，其它待开发）
     - `builtin/legacy/`: 向后兼容层（弃用警告）
   - Each plugin declares: `provides`, `depends_on`, `options`, `version`, `dtype`
   - `compute()` returns ndarray or generator
   - `is_side_effect=True` isolates outputs to `_side_effects/{run_id}/{plugin_name}`
   - **CPU Standard Plugins**:
     - Data processing: RawFiles → Waveforms → StWaveforms → Features → DataFrame → GroupedEvents → PairedEvents
     - Signal processing: FilteredWaveforms (Butterworth/Savitzky-Golay), SignalPeaks (scipy.signal)
   - **Plugin Organization**:
     - `cpu/standard.py`: 10个标准数据处理插件
     - `cpu/filtering.py`: FilteredWaveformsPlugin
     - `cpu/peak_finding.py`: SignalPeaksPlugin

3. **Storage Layer** (`core/storage/`)
   - `MemmapStorage` (`storage/memmap.py`): Zero-copy array persistence with atomic writes (`.tmp` → rename)
   - `StorageBackend` (`storage/backends.py`): Pluggable backends (SQLite, etc.)
   - `CacheManager` (`storage/cache.py`): Lineage-based cache validation
   - `CompressionManager` (`storage/compression.py`): Blosc2, LZ4, Zstd, Gzip
   - `IntegrityChecker` (`storage/integrity.py`): Checksum validation
   - Validates `dtype.descr` and `STORAGE_VERSION`
   - File locking for concurrent access protection
   - Watch signature (`WATCH_SIG_KEY`) tracks input file mtime/size for cache invalidation

4. **Streaming Framework** (`core/plugins/core/streaming.py`, `core/plugins/builtin/streaming/`)
   - `StreamingPlugin`: Returns chunk iterators instead of static data
   - `StreamingContext`: Manages chunk flows with automatic parallelization
   - Time-aligned chunk processing with boundary validation
   - Mixed static/streaming plugin support

5. **Executor Management** (`core/execution/`)
   - `ExecutorManager` (`execution/manager.py`): Global singleton for thread/process pool reuse
   - `EXECUTOR_CONFIGS` (`execution/config.py`): Predefined configs: `io_intensive`, `cpu_intensive`, `large_data`, `small_data`
   - `TimeoutManager` (`execution/timeout.py`): Timeout control
   - Context manager support: `with get_executor('io_intensive') as executor:`
   - Helper functions: `parallel_map()`, `parallel_apply()`

6. **Dataset API** (`core/dataset.py`)
   - High-level chainable interface wrapping Context
   - Memory optimization: `load_waveforms=False` skips waveform extraction (saves 70-80% memory)
   - Feature registration system
   - Timestamp indexing for fast `get_waveform_at()` lookups

7. **Chunk Utilities** (`core/processing/chunk.py`)
   - `Chunk(data, start, end, run_id, ...)`: Encapsulates data with time boundaries
   - Time range operations: `select_time_range()`, `clip_to_time_range()`
   - Validation: `check_monotonic()`, `check_no_overlap()`, `check_chunk_boundaries()`
   - Splitting/merging: `split_by_time()`, `merge_chunks()`, `rechunk()`

8. **Time Range Query** (`core/data/query.py`) [NEW - Phase 2.2]
   - `TimeIndex`: Efficient time indexing with O(log n) binary search queries
   - `TimeRangeQueryEngine`: Manages multiple data type indices
   - Context integration: `time_range()`, `clear_time_index()`
   - Query result caching for repeated queries
   - Example: `ctx.time_range('run_001', 'st_waveforms', start_time=1000, end_time=2000)`

9. **Strax Plugin Adapter** (`core/plugins/core/adapters.py`) [NEW - Phase 2.3]
   - `StraxPluginAdapter`: Wraps strax plugins for seamless integration
   - `StraxContextAdapter`: Provides strax-style API (`get_array`, `get_df`, `search_field`)
   - Automatic metadata extraction and parameter mapping
   - Configuration option compatibility
   - Example: `adapter = wrap_strax_plugin(MyStraxPlugin); ctx.register_plugin(adapter)`

10. **Batch Processing & Export** (`core/data/export.py`) [NEW - Phase 3.1 & 3.2]
    - `BatchProcessor`: Parallel/serial processing of multiple runs
    - `DataExporter`: Unified export interface (Parquet, HDF5, CSV, JSON, NumPy)
    - Progress tracking and flexible error handling
    - Example: `processor.process_runs(run_ids, 'peaks', max_workers=4)`
    - Example: `exporter.export(data, 'output.parquet')`

11. **Hot Reload** (`core/plugins/core/hot_reload.py`) [NEW - Phase 3.3]
    - `PluginHotReloader`: File change monitoring and automatic module reloading
    - Cache consistency maintenance after reload
    - Auto-reload daemon thread support
    - Example: `reloader = enable_hot_reload(ctx, ['my_plugin'], auto_reload=True)`

12. **WaveformStruct DAQ Decoupling** (`core/processing/processor.py`) [NEW - 2026-01]
    - `WaveformStructConfig`: Configuration class for DAQ format specifications
    - `WaveformStruct`: Decoupled from VX2730 hardware, supports multiple DAQ formats
    - Dynamic `RECORD_DTYPE` creation based on actual waveform length
    - Column mapping from `FormatSpec` (board, channel, timestamp, samples_start, baseline_start/end)
    - **Backward Compatible**: No-config usage defaults to VX2730 format
    - **Usage Modes**:
      - Default (VX2730): `WaveformStruct(waveforms)`
      - From adapter: `WaveformStruct.from_adapter(waveforms, "vx2730")`
      - Custom config: `WaveformStruct(waveforms, config=WaveformStructConfig(format_spec=custom_spec))`
    - **Plugin Integration**: `StWaveformsPlugin` supports `daq_adapter` option
      - Example: `ctx.set_config({'daq_adapter': 'vx2730'}, plugin_name='st_waveforms')`

13. **Time Field Unification** (`core/processing/processor.py`) [NEW - 2026-01]
    - **RECORD_DTYPE** now includes both `time` and `timestamp` fields:
      - `time` (i8): Absolute system time (Unix timestamp, nanoseconds)
      - `timestamp` (i8): ADC raw timestamp (picoseconds, unified to ps)
    - **Time Conversion**: `time = epoch_ns + timestamp // 1000`
    - **Epoch Source**: Automatically obtained from file creation time via `DAQAdapter.get_file_epoch()`
    - **Backward Compatible**: Without epoch, falls back to relative time (`time = timestamp // 1000`)
    - **Auto-effective**: `chunk.py` and `query.py` prioritize `time` by default; `streaming.py` defaults to `timestamp` (ps)
    - **Usage**: Set `daq_adapter` to enable automatic epoch extraction
      - Example: `ctx.set_config({'daq_adapter': 'vx2730'})`

14. **Config System** (`core/config/`) [NEW - 2026-01]
    - `ConfigResolver`: 统一配置解析，支持多级来源（显式 > adapter推断 > 插件默认）
    - `CompatManager`: 兼容层管理，处理参数别名和弃用警告
    - `AdapterInfo`: DAQ adapter 信息，用于配置推断
    - `ResolvedConfig`: 解析后的配置集合，包含来源追踪
    - **弃用过期检查**: 当前版本 >= `removed_in` 时抛出 `ValueError`
    - Context 集成: `get_resolved_config()`, `show_resolved_config()`, `get_adapter_info()`

15. **Plugin Specification** (`core/plugins/core/spec.py`) [NEW - 2026-01]
    - `PluginSpec`: 插件完整契约规范，用于注册校验、文档生成、lineage hash
    - `ConfigField`: 声明式配置规范，与 `Option`（运行时验证）互补
    - `OutputSchema`: 输出数据 schema，支持从 dtype 自动创建
    - `InputRequirement`: 输入依赖需求，支持版本约束
    - `Capabilities`: 插件能力声明（streaming, parallel, GPU, idempotent）
    - **自动提取**: `PluginSpec.from_plugin(plugin)` 从插件实例自动生成规范
    - **严格校验**: `ctx.register(plugin, require_spec=True)` 启用注册时校验

### Data Flow (Standard Pipeline)

```
CSV Files → RawFilesPlugin → WaveformsPlugin → StWaveformsPlugin
                                                       ↓
                                              ┌───────┴───────┐
                                              ↓               ↓
                                        PeaksPlugin    ChargesPlugin
                                              ↓               ↓
                                              └───────┬───────┘
                                                      ↓
                                               DataFramePlugin
                                                      ↓
                                            GroupedEventsPlugin
                                               (Numba + MP)
                                                      ↓
                                            PairedEventsPlugin
```

## Important Conventions

### Architecture & Responsibility Separation
- **Context**: Only manages plugin DAG, config, lineage, and caching
- **Dataset**: Provides chainable interface and result access (delegates to Context)
- **Never** maintain parallel state in Dataset; map attributes (like `self.char` → Context) to ensure single source of truth
- **Plugin Responsibility**: Each plugin does ONE thing; add new features as new plugins, not by expanding existing ones

### Run Identification
- **Always use `run_name`** instead of `char` (legacy term being phased out)
- Pass `run_id` explicitly to all `Context.get_data()` calls
- Missing `run_id` causes data overwrites and lineage conflicts

### Module Exports (`core/foundation/utils.py`)
All new modules **must** use the `exporter()` pattern:

```python
from waveform_analysis.core.foundation.utils import exporter
export, __all__ = exporter()

@export
class MyClass: ...

@export(name="AlternativeName")
def my_func(): ...

MY_CONST = export(42, name="MY_CONST")
```

### Naming Conventions
- Classes: `PascalCase`
- Functions/variables: `snake_case`
- Constants: `UPPER_SNAKE_CASE`
- Terminology: Use consistent business terms (waveforms/events/hits/chunks) across code and docs
- Event size: Use `event_length`, not `pair_len` or `pair_length`

### Cache Management
- Step-level cache: `set_step_cache(step, enabled=True, attrs=[...], persist_path=..., watch_attrs=[...])`
- Persistent cache writes `WATCH_SIG_KEY="__watch_sig__"` (mtime/size SHA1) for validation
- Cache automatically invalidates on plugin version/config/dtype changes
- Generator outputs consumed once; re-access triggers recomputation

### DAQ Adapter Configuration
- **Consistent Adapter Usage**: Use the same `daq_adapter` across the entire data flow (RawFiles → Waveforms → StWaveforms)
- **Global vs Plugin-Specific**: Prefer global config `ctx.set_config({'daq_adapter': 'vx2730'})` for consistency
- **Backward Compatibility**: Omitting `daq_adapter` defaults to VX2730 format
- **Custom Formats**: Create custom `FormatSpec` and register via `register_adapter()` for new DAQ systems
- **Plugin Support**: `RawFilesPlugin`, `WaveformsPlugin`, and `StWaveformsPlugin` all support `daq_adapter` option

### Time & Chunk Operations
- Records have `time`, `dt`, `length` fields; `endtime = time + dt * length`
- Chunk boundaries must be respected: record endtime ≤ chunk end
- Use `Chunk` objects for time-aligned data processing
- Validate with `check_sorted_by_time()` and `check_chunk_boundaries()`

### Performance Optimization
- **Numba JIT**: Available for hot loops (e.g., `group_multi_channel_hits` with `use_numba=True`)
- **Multiprocessing**: Use for large-scale CPU-bound tasks
- **Vectorization**: Prefer NumPy broadcasting over explicit loops
- **IO parallelization**: Use `ExecutorManager` with `io_intensive` config
- **CPU parallelization**: Use `ExecutorManager` with `cpu_intensive` config

## Plugin Architecture and Import Guide

### Accelerator-Based Plugin Organization (Since 2026-01)

插件按照计算加速器类型组织，支持 CPU、JAX（GPU）和流式处理：

```
builtin/
├── cpu/              # CPU 实现 (NumPy/SciPy/Numba)
│   ├── standard.py   # 标准数据处理插件
│   ├── filtering.py  # 滤波插件
│   └── peak_finding.py # 寻峰插件
├── jax/              # JAX GPU 实现（待开发）
├── streaming/        # 流式处理插件（CPU 已有 SignalPeaksStreamPlugin）
└── legacy/           # 向后兼容（弃用）
```

### Plugin Import Methods

```python
# 方法 1: 从 cpu/ 直接导入（推荐，明确指定加速器）
from waveform_analysis.core.plugins.builtin.cpu import (
    RawFilesPlugin,
    WaveformsPlugin,
    FilteredWaveformsPlugin,
    SignalPeaksPlugin,
)

# 方法 2: 从 builtin/ 导入（向后兼容，默认使用 CPU 实现）
from waveform_analysis.core.plugins.builtin.cpu import (
    RawFilesPlugin,
    WaveformsPlugin,
    FilteredWaveformsPlugin,
    SignalPeaksPlugin,
)

# 方法 3: 从 legacy/ 导入（不推荐，会发出弃用警告）
from waveform_analysis.core.plugins.builtin.cpu import RawFilesPlugin
# DeprecationWarning: RawFilesPlugin 已被弃用，将在下一个主版本中移除...
```

### Available CPU Plugins

#### 标准数据处理插件 (`cpu/standard.py`)
- `RawFilesPlugin`: 扫描和分组原始 CSV 文件
  - 支持 `daq_adapter` 选项指定 DAQ 格式（如 'vx2730'）
  - 集成 DAQ 元数据扫描功能
- `WaveformsPlugin`: 提取波形数据
  - 支持 `daq_adapter` 选项用于格式特定的数据加载
  - 支持多进程并行加载和自定义执行器
- `StWaveformsPlugin`: 结构化波形数组
  - 支持 `daq_adapter` 选项，通过 `WaveformStructConfig` 解耦 DAQ 格式
  - 向后兼容：默认使用 VX2730 配置
- `HitFinderPlugin`: 检测 Hit 事件
- `PeaksPlugin`: 峰值特征计算（直接依赖 st_waveforms）
- `ChargesPlugin`: 电荷积分计算（直接依赖 st_waveforms）
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
  - 返回 `ADVANCED_PEAK_DTYPE` 结构化数组

### Migration Guide from Legacy Plugins

如果你的代码使用了旧的导入方式，建议迁移到新架构：

```python
# 旧方式（会发出警告）
from waveform_analysis.core.plugins.builtin.cpu import RawFilesPlugin
from waveform_analysis.core.plugins.builtin.cpu import FilteredWaveformsPlugin

# 新方式（推荐）
from waveform_analysis.core.plugins.builtin.cpu import RawFilesPlugin, FilteredWaveformsPlugin
```

## Common Patterns

### Basic Dataset Usage
```python
from waveform_analysis import WaveformDataset

ds = WaveformDataset(run_name="50V_OV_circulation_20thr", n_channels=2)
(ds
    .load_raw_data()
    .extract_waveforms()
    .structure_waveforms()
    .build_waveform_features()
    .build_dataframe()
    .group_events(time_window_ns=100)
    .pair_events())

df = ds.get_paired_events()
```

### Memory-Optimized Workflow
```python
# Skip waveform extraction (saves 70-80% memory)
ds = WaveformDataset(run_name="...", load_waveforms=False)
ds.load_raw_data().extract_waveforms().structure_waveforms()  # All skipped
ds.build_waveform_features()  # Still computes features
ds.get_waveform_at(0)  # Returns None with warning
```

### Plugin-Based Context Usage
```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.standard_plugins import *

# 推荐：使用 data_root 配置，缓存将存储在 DAQ/{run_id}/_cache/
ctx = Context(config={"data_root": "DAQ", "n_channels": 2})
ctx.register_plugin(RawFilesPlugin())
ctx.register_plugin(WaveformsPlugin())

# 或者显式指定存储目录
# ctx = Context(storage_dir="./strax_data")

hits = ctx.get_data("run_001", "hits")  # Auto-resolves dependencies
```

### Preview Execution (运行前确认 Lineage)
```python
# 在实际执行前预览执行计划
ctx.preview_execution('run_001', 'signal_peaks')

# 输出包含：
# - 执行计划（插件执行顺序）
# - 依赖关系树
# - 自定义配置参数（仅显示非默认值）
# - 缓存状态（哪些已缓存，哪些需要计算）

# 程序化使用预览结果
result = ctx.preview_execution('run_001', 'signal_peaks')
needs_compute = [p for p, s in result['cache_status'].items() if s['needs_compute']]
print(f"需要计算 {len(needs_compute)} 个插件")

# 确认后执行
data = ctx.get_data('run_001', 'signal_peaks')

# 不同详细程度
ctx.preview_execution('run_001', 'signal_peaks', verbose=0)  # 简洁
ctx.preview_execution('run_001', 'signal_peaks', verbose=1)  # 标准（默认）
ctx.preview_execution('run_001', 'signal_peaks', verbose=2)  # 详细

# 选择性显示
ctx.preview_execution('run_001', 'signal_peaks',
                      show_tree=False,   # 不显示依赖树
                      show_config=True,  # 显示配置
                      show_cache=True)   # 显示缓存状态
```

### Streaming Processing
```python
from waveform_analysis.core.streaming import get_streaming_context

stream_ctx = get_streaming_context(ctx, run_id="run_001", chunk_size=50000)
for chunk in stream_ctx.get_stream("st_waveforms_stream"):
    process_chunk(chunk)
```

### Adding Custom Features
```python
def my_feature_fn(self, st_waveforms, event_length, **params):
    # Returns list of feature arrays (one per channel)
    return [np.array(...) for _ in range(self.n_channels)]

ds.register_feature("my_feature", my_feature_fn, param1=value1)
ds.compute_registered_features()  # Called during build_dataframe()
```

### WaveformStruct with Custom DAQ Formats
```python
from waveform_analysis.core.processing.processor import WaveformStruct, WaveformStructConfig
from waveform_analysis.utils.formats import FormatSpec, ColumnMapping

# 方式1: 默认 VX2730（向后兼容，现有代码无需修改）
struct = WaveformStruct(waveforms)
st_waveforms = struct.structure_waveforms()

# 方式2: 通过适配器名称
struct = WaveformStruct.from_adapter(waveforms, "vx2730")

# 方式3: 自定义格式
custom_spec = FormatSpec(
    name="custom_daq",
    columns=ColumnMapping(
        board=0, channel=1, timestamp=3,  # 时间戳在列3
        samples_start=10,  # 波形数据从列10开始
        baseline_start=10, baseline_end=50
    ),
    expected_samples=1000  # 1000个采样点
)
config = WaveformStructConfig(format_spec=custom_spec)
struct = WaveformStruct(waveforms, config=config)

# 方式4: 在插件中使用
from waveform_analysis.core.context import Context
ctx = Context()
ctx.set_config({'daq_adapter': 'vx2730'}, plugin_name='st_waveforms')
st_waveforms = ctx.get_data('run_001', 'st_waveforms')

# 方式5: 在完整数据流中使用 daq_adapter（推荐）
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import (
    RawFilesPlugin, WaveformsPlugin, StWaveformsPlugin
)

ctx = Context(config={"data_root": "DAQ", "n_channels": 2})
ctx.register_plugin(RawFilesPlugin())
ctx.register_plugin(WaveformsPlugin())
ctx.register_plugin(StWaveformsPlugin())

# 为所有相关插件设置 daq_adapter（全局配置）
ctx.set_config({'daq_adapter': 'vx2730'})

# 或者为特定插件设置（插件特定配置）
ctx.set_config({'daq_adapter': 'vx2730'}, plugin_name='raw_files')
ctx.set_config({'daq_adapter': 'vx2730'}, plugin_name='waveforms')
ctx.set_config({'daq_adapter': 'vx2730'}, plugin_name='st_waveforms')

# 获取数据（自动使用配置的适配器）
st_waveforms = ctx.get_data('run_001', 'st_waveforms')
```

### Using New Features (Phase 2 & 3)

#### Time Range Queries
```python
from waveform_analysis.core.context import Context

ctx = Context()
# ... register plugins and set config ...

# Query specific time range (单个结构化数组)
peaks_data = ctx.time_range(
    'run_001', 'peaks',
    start_time=1000000,
    end_time=2000000
)

# Query multi-channel data (List[np.ndarray])
# 返回过滤后的列表，每个通道一个数组
st_waveforms = ctx.time_range(
    'run_001', 'st_waveforms',
    start_time=1000000,
    end_time=2000000
)
print(len(st_waveforms))  # 2 (通道数)

# 只查询特定通道
ch0_data = ctx.time_range(
    'run_001', 'st_waveforms',
    start_time=1000000,
    end_time=2000000,
    channel=0  # 只返回通道0的数据
)

# First query triggers index build (for better performance on repeated queries)
_ = ctx.time_range('run_001', 'st_waveforms', start_time=0, end_time=1, endtime_field='computed')

# Get index statistics
stats = ctx.get_time_index_stats()
print(f"Total indices: {stats['total_indices']}")
```

**多通道数据支持**：
- `time_range()` 自动检测 `List[np.ndarray]` 类型，为每个通道分别建立索引
- 索引 key 格式为 `{data_name}_ch{i}`（如 `st_waveforms_ch0`）
- `time_range()` 支持 `channel` 参数，可查询单个通道或所有通道

#### Absolute Time Queries (绝对时间查询)

支持使用 Python `datetime` 对象进行数据查询，需要先设置 epoch（时间基准）：

```python
from datetime import datetime, timezone
from waveform_analysis.core.context import Context

ctx = Context()
# ... register plugins and set config ...

# 方法1: 自动从文件名提取 epoch
ctx.auto_extract_epoch('run_001')

# 方法2: 手动设置 epoch
epoch = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
ctx.set_epoch('run_001', epoch)

# 使用 datetime 对象查询
start = datetime(2024, 1, 1, 12, 0, 10, tzinfo=timezone.utc)
end = datetime(2024, 1, 1, 12, 0, 20, tzinfo=timezone.utc)

data = ctx.get_data_time_range_absolute(
    'run_001',
    'peaks',
    start_dt=start,
    end_dt=end
)

# 查看 epoch 信息
epoch_info = ctx.get_epoch('run_001')
print(f"Epoch: {epoch_info.epoch_datetime}")
print(f"Source: {epoch_info.epoch_source}")
```

**Epoch 提取策略**（优先级从高到低）：
1. `filename`: 从文件名解析（如 `data_2024-01-01_12-00-00.csv`）
2. `csv_header`: 从 CSV 头部注释提取
3. `first_event`: 从首个事件时间戳推导

**详细文档**: 参见 `docs/features/context/ABSOLUTE_TIME_GUIDE.md`

#### Strax Plugin Integration
```python
from waveform_analysis.core.strax_adapter import (
    wrap_strax_plugin,
    create_strax_context
)

# Wrap existing strax plugin
adapter = wrap_strax_plugin(MyStraxPlugin)
ctx.register_plugin(adapter)

# Or use strax-style API
strax_ctx = create_strax_context('./data')
strax_ctx.register(MyStraxPlugin)
data = strax_ctx.get_array('run_001', 'peaks')
df = strax_ctx.get_df('run_001', ['peaks', 'hits'])
```

#### Batch Processing
```python
from waveform_analysis.core.batch_export import BatchProcessor

processor = BatchProcessor(ctx)

# Process multiple runs in parallel
results = processor.process_runs(
    run_ids=['run_001', 'run_002', 'run_003'],
    data_name='peaks',
    max_workers=4,
    show_progress=True,
    on_error='continue'  # 'continue', 'stop', or 'raise'
)

# Access results
for run_id, data in results['results'].items():
    print(f"{run_id}: {len(data)} events")

# Check errors
if results['errors']:
    print(f"Errors: {results['errors']}")
```

#### Data Export
```python
from waveform_analysis.core.batch_export import DataExporter, batch_export

# Export single dataset
exporter = DataExporter()
exporter.export(data, 'output.parquet')  # Auto-detect format
exporter.export(data, 'output.hdf5', key='waveforms')
exporter.export(data, 'output.csv')

# Batch export multiple runs
batch_export(
    ctx,
    run_ids=['run_001', 'run_002'],
    data_name='peaks',
    output_dir='./exports',
    format='parquet',
    max_workers=4
)
```

#### Hot Reload (Development)
```python
from waveform_analysis.core.hot_reload import enable_hot_reload

# Enable auto-reload for development
reloader = enable_hot_reload(
    ctx,
    plugin_names=['my_plugin'],
    auto_reload=True,
    interval=2.0  # Check every 2 seconds
)

# Manually reload after changes
reloader.reload_plugin('my_plugin', clear_cache=True)

# Disable when done
reloader.disable_auto_reload()
```

#### PluginSpec 契约系统 (高级)

为插件定义机器可读契约，用于注册校验、文档生成和 lineage hash：

```python
from waveform_analysis.core.plugins.core import (
    Plugin, Option, PluginSpec, ConfigField,
    OutputSchema, InputRequirement, Capabilities
)

class MyPlugin(Plugin):
    provides = 'my_data'
    version = '1.0.0'
    depends_on = ['st_waveforms']
    options = {
        'threshold_mv': Option(default=10.0, type=float, help='Threshold in mV'),
    }

    # 可选：手动定义 SPEC 提供更丰富的元信息
    SPEC = PluginSpec(
        name='MyPlugin',
        provides='my_data',
        version='1.0.0',
        depends_on=(InputRequirement(name='st_waveforms', version_spec='>=1.0.0'),),
        config_spec={
            'threshold_mv': ConfigField(
                type='float', default=10.0,
                doc='Detection threshold', units='mV'
            ),
        },
        capabilities=Capabilities(supports_streaming=False, supports_parallel=True),
    )

# 自动提取 spec（推荐，无需手动定义 SPEC）
spec = PluginSpec.from_plugin(MyPlugin())
print(spec.config_keys)  # ('threshold_mv',)

# 严格模式注册（生产环境推荐）
ctx.register(MyPlugin(), require_spec=True)
```

**ConfigField vs Option**:
- `Option`: 运行时配置验证和类型转换（插件开发必需）
- `ConfigField`: 静态契约声明，用于文档生成、lineage hash、IDE 提示（可选）

#### Lineage Visualization (血缘图可视化)

WaveformAnalysis 提供两种高级血缘图可视化模式，支持智能颜色高亮和完整交互功能。

##### LabVIEW 风格（Matplotlib）
```python
# 基础用法
ctx.plot_lineage("df_paired", kind="labview")

# 交互式模式（鼠标悬停显示详情、点击显示依赖）
ctx.plot_lineage("df_paired", kind="labview", interactive=True)

# 显示详细信息
ctx.plot_lineage("df_paired", kind="labview", verbose=2, interactive=True)
```

##### Plotly 高级交互式
```python
# Plotly 模式（始终交互式，支持缩放、平移、悬停）
ctx.plot_lineage("df_paired", kind="plotly", verbose=2)

# 自定义样式
from waveform_analysis.core.foundation.utils import LineageStyle
style = LineageStyle(
    node_width=4.0,
    node_height=2.0,
    verbose=2
)
ctx.plot_lineage("df_paired", kind="plotly", style=style)
```

##### Verbose 等级说明
- `verbose=0`: 仅显示插件标题
- `verbose=1`: 显示标题 + key
- `verbose=2`: 显示标题 + key + class（推荐）
- `verbose>=3`: 同 verbose=2

##### 智能颜色高亮

系统自动根据节点类型应用颜色方案：

| 节点类型 | 颜色 | 识别规则 |
|---------|------|---------|
| 原始数据 | 🔵 蓝色系 | RawFiles, Loader, Reader |
| 结构化数组 | 🟢 绿色系 | 多字段 dtype（如 `[('time', '<f8'), ...]`）|
| DataFrame | 🟠 橙色系 | DataFrame, df 关键词 |
| 聚合数据 | 🟣 紫色系 | Group, Pair, Aggregate, Merge |
| 副作用 | 🌸 粉红色系 | Export, Save, Write |
| 中间处理 | ⚪ 灰色系 | 其他节点 |

颜色高亮在两种模式下均自动生效，无需额外配置。

##### Plotly 模式特性

- ✅ **真实矩形绘制**：使用 shapes API 绘制节点和端口，尺寸精确
- ✅ **完整交互性**：缩放、平移、悬停提示、框选
- ✅ **坐标同步修复**：拖拽时光标和节点位置完全同步
- ✅ **1:1 比例保持**：确保节点不变形
- ✅ **端口可见**：显示彩色输入/输出端口
- ✅ **类型标注**：悬停提示包含节点类型信息

##### 注意事项

1. **Interactive 参数**：
   - LabVIEW 模式：`interactive=True` 启用 matplotlib 交互功能
   - Plotly 模式：始终交互式，`interactive` 参数被忽略

2. **性能考虑**：
   - LabVIEW 模式适合静态导出和简单交互
   - Plotly 模式适合复杂图形的深度探索

3. **依赖**：
   - LabVIEW 模式：需要 matplotlib（标准依赖）
   - Plotly 模式：需要 `pip install plotly`

## Cache Management (缓存管理)

WaveformAnalysis 提供完整的缓存管理工具集，用于分析、诊断、清理和统计缓存数据。

### Python API

#### 快速使用

```python
# 获取缓存分析器
analyzer = ctx.analyze_cache()

# 查看缓存统计
stats = ctx.cache_stats(detailed=True)

# 诊断缓存问题
issues = ctx.diagnose_cache(run_id='run_001')

# 自动修复（dry-run）
ctx.diagnose_cache(run_id='run_001', auto_fix=True, dry_run=True)
```

#### 高级用法

```python
from waveform_analysis.core.storage import (
    CacheAnalyzer,
    CacheDiagnostics,
    CacheCleaner,
    CacheStatsCollector,
    CleanupStrategy,
)

# 1. 分析缓存
analyzer = CacheAnalyzer(ctx)
analyzer.scan()

# 获取所有条目
entries = analyzer.get_entries()

# 按条件过滤
large = analyzer.get_entries(min_size=1024*1024)  # > 1MB
old = analyzer.get_entries(max_age_days=30)       # > 30 天
run_entries = analyzer.get_entries(run_id='run_001')

# 打印摘要
analyzer.print_summary(detailed=True)

# 2. 诊断问题
diag = CacheDiagnostics(analyzer)
issues = diag.diagnose()
diag.print_report(issues)

# 自动修复
result = diag.auto_fix(issues, dry_run=True)

# 3. 智能清理
cleaner = CacheCleaner(analyzer)

# 创建清理计划
plan = cleaner.plan_cleanup(
    strategy=CleanupStrategy.LRU,
    target_size_mb=1024
)
cleaner.preview_plan(plan, detailed=True)

# 执行清理
cleaner.execute(plan, dry_run=False)

# 按年龄清理
cleaner.cleanup_by_age(max_age_days=30, dry_run=True)

# 清理到目标大小
cleaner.cleanup_to_target_size(target_total_mb=500, dry_run=True)

# 4. 统计收集
collector = CacheStatsCollector(analyzer)
stats = collector.collect()
collector.print_summary(stats, detailed=True)

# 导出统计
collector.export_stats(stats, 'cache_stats.json')
```

### 清理策略

| 策略 | 说明 |
|------|------|
| `LRU` | 按创建时间排序，删除最旧的 |
| `OLDEST` | 最旧的优先 |
| `LARGEST` | 最大的优先 |
| `VERSION_MISMATCH` | 插件版本不匹配的 |
| `FAILED_INTEGRITY` | 完整性检查失败的 |
| `BY_RUN` | 按运行清理 |
| `BY_DATA_TYPE` | 按数据类型清理 |

### CLI 命令

```bash
# 缓存概览
waveform-cache info [--run RUN_ID] [--detailed] [--storage-dir PATH]

# 详细统计
waveform-cache stats [--run RUN_ID] [--detailed] [--export stats.json]

# 诊断问题
waveform-cache diagnose [--run RUN_ID] [--fix] [--dry-run]

# 列出缓存条目
waveform-cache list [--run RUN_ID] [--data-type TYPE] [--min-size BYTES]

# 清理缓存
waveform-cache clean --strategy lru --size-mb 500 [--dry-run]
waveform-cache clean --strategy oldest --days 30 [--no-dry-run]
waveform-cache clean --strategy largest --max-entries 10 --dry-run
```

### 诊断问题类型

| 类型 | 严重性 | 说明 |
|------|--------|------|
| `VERSION_MISMATCH` | warning | 插件版本与缓存不匹配 |
| `MISSING_METADATA` | error | 元数据文件缺失 |
| `MISSING_DATA_FILE` | error | 数据文件缺失 |
| `SIZE_MISMATCH` | error | 文件大小不匹配 |
| `CHECKSUM_FAILED` | error | 校验和验证失败 |
| `ORPHAN_FILE` | warning | 孤儿文件（无元数据） |
| `STORAGE_VERSION_MISMATCH` | warning | 存储版本不匹配 |

### 安全特性

- **默认 dry-run**: 所有清理和修复操作默认为演练模式
- **线程安全**: CacheAnalyzer 使用锁保护缓存索引
- **增量扫描**: 支持增量扫描避免重复遍历
- **详细预览**: 执行前可预览所有将要执行的操作

## Common Pitfalls

1. **Generator Exhaustion**: Generators can only be consumed once; repeat access triggers recomputation
2. **Missing run_id**: Always pass `run_id` to `Context.get_data()` to avoid data conflicts
3. **Cache Invalidation**: Bump `version` when changing plugin logic/dtype/options
4. **Data Paths**: Default data directory is `DAQ/<run_name>`; missing files cause `FileNotFoundError`
5. **Chunk Boundaries**: Record endtime must not exceed chunk boundary; validate with `check_chunk_boundaries()`
6. **Timestamp Index**: After modifying `st_waveforms`, call `_build_timestamp_index()` to rebuild index
7. **Waveform Access**: With `load_waveforms=False`, `get_waveform_at()` returns None
8. **Plugin dtype**: `output_dtype` can be either:
   - Valid NumPy dtype (e.g., `np.dtype([('time', '<f8'), ('charge', '<f4')])`)
   - Type annotation strings for non-array outputs (e.g., `"List[np.ndarray]"`, `"pd.DataFrame"`)
   - Framework automatically handles both cases in lineage tracking and validation

## Testing Notes

- Test script auto-activates conda environment `pyroot-kernel`
- If DAQ data files missing, tests will `pytest.skip()` gracefully
- Coverage report generated in `htmlcov/` directory
- Use `scripts/benchmark_io.py` to test I/O performance with different chunksizes

## File Structure Notes

- `waveform_analysis/core/`: Core processing logic (modular subdirectories since 2026-01)
  - `context.py`, `dataset.py`: Core files (root level)
  - `config/`: Configuration system (resolver, compat, adapter_info, types) [NEW - 2026-01]
    - `resolver.py`: ConfigResolver 配置解析器
    - `compat.py`: CompatManager 兼容层管理
    - `adapter_info.py`: AdapterInfo DAQ adapter 信息
    - `types.py`: ConfigSource, ConfigValue, ResolvedConfig 类型定义
  - `storage/`: Storage layer (memmap, backends, cache, compression, integrity)
    - `cache_analyzer.py`: 缓存分析器和 CacheEntry 数据类
    - `cache_diagnostics.py`: 缓存诊断和修复工具
    - `cache_cleaner.py`: 智能缓存清理策略
    - `cache_statistics.py`: 缓存统计收集和报告
  - `execution/`: Execution layer (manager, config, timeout)
  - `plugins/`: Plugin system (按加速器划分架构，since 2026-01)
    - `core/`: Plugin infrastructure (base, streaming, adapters, hot_reload, spec)
      - `spec.py`: PluginSpec, ConfigField, OutputSchema, Capabilities [NEW - 2026-01]
    - `builtin/`: Built-in plugins organized by accelerator
      - `cpu/`: CPU implementations (NumPy/SciPy/Numba)
        - `standard.py`: 10 standard data processing plugins
        - `filtering.py`: FilteredWaveformsPlugin (Butterworth, Savitzky-Golay)
        - `peak_finding.py`: SignalPeaksPlugin (scipy.signal.find_peaks)
      - `jax/`: JAX GPU implementations (待开发 - Phase 2)
      - `streaming/`: Streaming plugins (CPU 已有 SignalPeaksStreamPlugin)
        - `cpu/`: CPU streaming plugins (SignalPeaksStreamPlugin)
        - `jax/`: JAX streaming plugins (待开发)
      - `legacy/`: Deprecated plugins for backward compatibility
        - `__init__.py`: Lazy import with deprecation warnings
        - `standard.py`: Original standard plugins
        - `signal_processing.py`: Original signal processing plugins
  - `processing/`: Data processing (loader, processor, analyzer, chunk)
  - `data/`: Data management (query, export)
  - `foundation/`: Framework basics (exceptions, mixins, model, utils, progress)
- `waveform_analysis/cli_cache.py`: 缓存管理 CLI 命令 (waveform-cache)
- `waveform_analysis/utils/`: Utilities (DAQ adapters, I/O, visualization)
- `waveform_analysis/fitting/`: Physics fitting models
- `tests/`: Unit and integration tests
  - `test_cache_analyzer.py`: CacheAnalyzer 测试
  - `test_cache_diagnostics.py`: CacheDiagnostics 测试
  - `test_cache_cleaner.py`: CacheCleaner 测试
  - `test_cache_statistics.py`: CacheStatsCollector 测试
- `examples/`: Usage demonstrations
- `docs/`: Architecture, guides, and implementation details
- `scripts/`: Helper scripts (testing, benchmarking)
- `DAQ/`: Data directory (not in package)
- `outputs/`: Results directory (not in package)

## Key Documentation Files

- `docs/architecture/ARCHITECTURE.md`: Complete architecture and data flow
- `docs/features/context/DATA_ACCESS.md`: Data access, cache behavior, and cache analysis
- `docs/features/context/CONFIGURATION.md`: Configuration management and resolved config
- `docs/plugins/guides/STREAMING_PLUGINS_GUIDE.md`: Streaming framework usage
- `docs/features/advanced/EXECUTOR_MANAGER_GUIDE.md`: Parallel execution management
- `docs/user-guide/QUICKSTART_GUIDE.md`: Quick start examples
- `docs/features/context/PREVIEW_EXECUTION.md`: Preview execution plans before running
- `docs/plugins/tutorials/SIGNAL_PROCESSING_PLUGINS.md`: Signal processing plugins (filtering, peak detection)
- `docs/development/plugin-development/PLUGIN_SPEC_GUIDE.md`: PluginSpec and ConfigField advanced guide [NEW]
- **Lineage Visualization**: See `CLAUDE.md` § Lineage Visualization for color-coded interactive graph features
- `.github/copilot-instructions.md`: Detailed development guidelines (Chinese)
