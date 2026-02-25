# 更新日志

所有重要的项目变更都会记录在此文件中。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
本项目遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [未发布]

### 变更

#### DAQ 采样率自动映射 (2026-01)
- **FormatSpec 新增采样率字段**: `sampling_rate_hz` 并由 DAQAdapter 暴露
- **VX2730 采样率配置**: 默认设置为 500 MHz
- **插件自动推断**: `signal_peaks`/`signal_peaks_stream` 在未显式配置时由适配器推断 `sampling_interval_ns`；
  `waveform_width` 在未显式配置时推断 `sampling_rate`（GHz）
- **滤波器采样率自动推断**: `filtered_waveforms` 在未显式配置 `fs` 时由适配器推断（GHz）
- **信号处理插件路径统一**: `builtin/signal_processing.py` 变为弃用兼容垫片，建议使用 `builtin/cpu`
- **峰值插件配置简化**: `signal_peaks`/`signal_peaks_stream` 移除 `daq_adapter` 插件选项，改为读取全局 `daq_adapter`

#### MemmapStorage 架构简化 (2026-01)
- **移除 Legacy 存储模式**: 删除旧的扁平存储结构支持 (`core/storage/memmap.py`)
  - 移除 `base_dir` 参数，统一使用 `work_dir`
  - 移除 `use_run_subdirs` 参数，强制使用分层结构
  - 简化所有方法，移除旧模式分支逻辑
  - **破坏性变更**: 不再支持扁平存储结构
- **API 变化**:
  - `MemmapStorage(work_dir)` - 必须提供 work_dir 参数
  - 所有数据操作方法都需要 `run_id` 参数
  - `list_keys(run_id)` - 必须指定 run_id
  - `verify_integrity(run_id=None)` - 支持验证单个或所有 runs
- **Context 更新**: 移除 `use_run_subdirs` 参数
  - 简化初始化：`MemmapStorage(work_dir=storage_dir, profiler=self.profiler)`
  - 更新 parquet 路径处理逻辑
- **测试更新**: 所有测试文件已更新以支持新 API
  - `test_storage.py`: 21 个测试全部通过
  - `test_integrity.py`: 20 个测试全部通过
  - `test_compression.py`: 16 个测试通过
  - `test_storage_backends.py`: 24/25 个测试通过
- **迁移指南**: 旧代码需要更新
  - 将 `MemmapStorage(base_dir)` 改为 `MemmapStorage(work_dir)`
- 所有存储操作添加 `run_id` 参数
  - 数据将存储在 `work_dir/{run_id}/_cache/` 而非 `base_dir/`

#### 时间字段统一方案 (2026-01-22)
- **ST_WAVEFORM_DTYPE 新增 time 字段**: 引入绝对系统时间支持 (`core/processing/processor.py`)
  - `time` (i8): 绝对系统时间（Unix 时间戳，纳秒 ns）
  - `timestamp` (i8): ADC 原始时间戳（皮秒 ps，统一为 ps）
  - 时间转换公式：`time = epoch_ns + timestamp // 1000`
- **DAQAdapter 新增方法**: `get_file_epoch()` 从文件创建时间获取 epoch (`utils/formats/adapter.py`)
  - 优先使用 `st_birthtime` (macOS)，否则使用 `st_mtime`
- **时间戳单位统一**: `st_waveforms` 的 `timestamp` 统一转换为 ps（按 `FormatSpec.timestamp_unit`）
- **流式默认时间字段**: `StreamingPlugin.time_field` 默认使用 `timestamp`（ps）
- **断点阈值单位**: `break_threshold_ps` 作为统一命名与单位（ps），替代 `break_threshold_ns`
- **兼容别名移除**: `break_threshold_ns` 兼容别名移除，统一使用 `break_threshold_ps`

#### 流式执行优化 (2026-02)
- **并行批处理**: 流式插件支持批量提交与顺序回收，失败时取消未完成任务
- **配置扩展**: 支持 `executor_config`/`parallel_batch_size`/`load_balancer_config.worker_buckets`
- **进程池回退**: `executor_type="process"` 不可 pickle 时自动回退到线程池并告警

#### CLI 处理流程调整 (2026-02)
- `waveform-process` 改为基于 `Context` + `standard_plugins` 执行
- 未指定 `--output` 时默认输出到 `outputs/{run_name}_paired.csv`

#### 执行器释放策略调整 (2026-02)
- `ExecutorManager.release_executor()` 增加 `wait` 参数，支持非阻塞释放

#### WaveformStruct DAQ 解耦 (2026-01)
- **WaveformStructConfig 配置类**: 新增配置类解耦 DAQ 格式依赖 (`core/processing/processor.py`)
  - `WaveformStructConfig`: 封装 `FormatSpec` 和波形长度配置
  - `default_vx2730()`: 返回 VX2730 默认配置（向后兼容）
  - `from_adapter(adapter_name)`: 从已注册的 DAQ 适配器创建配置
  - `get_wave_length()`: 获取波形长度（优先级：wave_length > format_spec.expected_samples > DEFAULT）
  - `get_record_dtype()`: 动态创建 ST_WAVEFORM_DTYPE
- **WaveformStruct 重构**: 移除 VX2730 硬编码，支持多种 DAQ 格式
  - 添加 `config` 参数，支持自定义 DAQ 格式
  - 添加 `from_adapter()` 类方法，便捷地从适配器名称创建实例
  - 替换所有硬编码列索引（board, channel, timestamp, samples_start, baseline_start/end）
  - 支持动态波形长度，自动适配实际数据
  - **向后兼容**: 无参数调用默认使用 VX2730 配置
- **插件集成**: `StWaveformsPlugin` 支持 `daq_adapter` 配置选项
  - 根据配置选择使用适配器或默认 VX2730 配置
  - 与 `RawFilesPlugin` 和 `WaveformsPlugin` 的 `daq_adapter` 选项保持一致
- **测试**: 新增 15 个单元测试全部通过 (`tests/test_waveform_struct_decoupling.py`)
  - 配置类功能测试（4 个）
  - 动态 dtype 创建测试（3 个）
  - 解耦功能测试（5 个）
  - 边界情况测试（3 个）
- **文档**: 更新 CLAUDE.md，添加使用示例和最佳实践

#### 缓存路径优化 (2026-01)
- **缓存目录重命名**: 将缓存子目录从 `data/` 改为 `_cache/`
  - 新路径格式：`{data_root}/{run_id}/_cache/*.bin`
  - 例如：`DAQ/run_001/_cache/run_001-peaks-abc123.bin`
  - 更清晰地区分原始数据和缓存数据
- **Context 初始化优化**: `storage_dir` 参数改为可选
  - 如果未指定 `storage_dir`，将使用 `config['data_root']` 作为存储目录
  - 推荐用法：`Context(config={"data_root": "DAQ"})`
  - 向后兼容：仍可显式指定 `storage_dir`

### 新增

#### 缓存分析插件 (2026-02)
- **CacheAnalysisPlugin**: 内置缓存分析插件，可在 Context 中直接生成缓存报告

#### DAQ 完整适配器层 (2026-01)
- **统一格式读取接口** (`utils/formats/`)
  - `FormatSpec`: 数据格式规范（列映射、时间戳单位、分隔符等）
  - `ColumnMapping`: CSV 列索引配置（board, channel, timestamp, samples）
  - `TimestampUnit`: 时间戳单位枚举（ps, ns, us, ms, s）
  - `FormatReader`: 格式读取器抽象基类

- **目录结构适配** (`utils/formats/directory.py`)
  - `DirectoryLayout`: 目录结构配置（raw_subdir, file patterns, channel regex）
  - 支持灵活的目录布局（VX2730 标准布局、扁平布局等）
  - 自动文件扫描和通道识别

- **完整 DAQ 适配器** (`utils/formats/adapter.py`)
  - `DAQAdapter`: 结合 FormatReader + DirectoryLayout 的完整适配器
  - `scan_run()`: 扫描运行目录，返回按通道分组的文件
  - `load_channel()`: 加载单个通道数据
  - `extract_and_convert()`: 提取列并转换时间戳
  - 适配器注册表：`register_adapter()`, `get_adapter()`, `list_adapters()`

- **VX2730 实现** (`utils/formats/vx2730.py`)
  - `VX2730_SPEC`: CAEN VX2730 格式规范（分号分隔、2行头部、ps时间戳、800采样点）
  - `VX2730_LAYOUT`: VX2730 目录布局（RAW 子目录、CH\d+ 模式）
  - `VX2730Reader`: CSV 格式读取器（支持 pandas 和 numpy 回退）
  - `VX2730_ADAPTER`: 预注册的完整适配器

- **向后兼容集成**
  - `io.py`: 添加 `format_type` 和 `format_reader` 参数
  - `daq_run.py`: 使用 `DirectoryLayout` 替代硬编码
  - `loader.py`: 支持 `daq_adapter` 参数
  - `standard.py`: 插件支持 `daq_adapter` 配置选项
  - `preview.py`: `WaveformPreviewer` 支持适配器

- **测试**: `tests/test_daq_adapter.py` - 21个单元测试全部通过

#### 缓存管理工具 (2026-01)
- **缓存分析器** (`core/storage/cache_analyzer.py`)
  - `CacheAnalyzer`: 扫描和分析缓存条目
  - `CacheEntry`: 缓存条目数据类
  - 按条件过滤（大小、年龄、运行ID）

- **缓存诊断** (`core/storage/cache_diagnostics.py`)
  - `CacheDiagnostics`: 检测缓存问题
  - 问题类型：版本不匹配、元数据缺失、校验失败等
  - 自动修复功能（支持 dry-run）

- **智能清理** (`core/storage/cache_cleaner.py`)
  - `CacheCleaner`: 多策略清理
  - 清理策略：LRU、OLDEST、LARGEST、VERSION_MISMATCH、FAILED_INTEGRITY 等
  - 支持 dry-run 预演、按 run 或数据类型限定范围
  - 清理计划预览与执行统计

- **统计收集** (`core/storage/cache_statistics.py`)
  - `CacheStatsCollector`: 收集详细统计
  - 导出统计到 JSON

- **CLI 命令**: `waveform-cache` (info, stats, diagnose, list, clean)

### 新增 (Phase 2 & 3)

#### Phase 2.2: 数据时间范围查询优化
- **时间索引系统**: 新增高效的时间索引功能 (`core/time_range_query.py`)
  - `TimeIndex`: O(log n)复杂度的二分查找时间索引
  - `TimeRangeQueryEngine`: 管理多数据类型的时间索引
  - `TimeRangeCache`: 查询结果缓存
- **Context集成**: 新增时间范围查询方法
  - `time_range()`: 查询指定时间范围的数据（首次查询会自动构建索引）
  - `clear_time_index()`: 清除时间索引
  - `get_time_index_stats()`: 获取索引统计信息
- **测试**: 完整的单元测试 (`tests/test_time_range_query.py`)
- **文档**: 详细的使用说明和示例

#### Phase 2.3: Strax插件适配器
- **Strax兼容层**: 无缝集成现有strax插件 (`core/strax_adapter.py`)
  - `StraxPluginAdapter`: 包装strax插件的适配器
  - `StraxContextAdapter`: 提供strax风格API
  - 自动元数据提取（provides, depends_on, dtype, version）
  - 智能参数映射和配置兼容
- **API支持**: strax风格的数据访问接口
  - `get_array()`: 获取numpy数组
  - `get_df()`: 获取DataFrame
  - `search_field()`: 搜索数据字段
  - `set_config()`: 配置管理
- **便捷函数**:
  - `wrap_strax_plugin()`: 快速包装strax插件
  - `create_strax_context()`: 创建strax兼容的Context
- **测试**: 全面的适配器测试 (`tests/test_strax_adapter.py`)

#### Phase 3.1: 多运行批量处理
- **批量处理器**: 高效的多运行并行处理 (`core/data/batch_processor.py`)
  - `BatchProcessor`: 支持串行/并行处理
  - 进度跟踪和实时反馈
  - 灵活的错误处理策略 (`continue`, `stop`, `raise`)
  - 自定义处理函数支持
- **性能优化**:
  - 基于ThreadPoolExecutor的并行执行
  - 可配置的工作进程数
  - 任务完成状态跟踪

#### Phase 3 Enhancement: 批量处理高级功能 (NEW)
- **统一进度追踪系统** (`core/progress_tracker.py`)
  - `ProgressTracker`: tqdm集成的进度条系统
  - 支持嵌套进度条显示
  - 自动计算ETA和吞吐量
  - 线程安全设计
  - 辅助函数：`format_time()`, `format_throughput()`
  - 集成到 `BatchProcessor.process_runs()` 和 `process_func()`

- **任务取消机制** (`core/cancellation.py`)
  - `CancellationToken`: 线程安全的取消令牌
  - `CancellationManager`: 全局取消管理器（单例模式）
  - 信号处理：优雅的Ctrl+C中断处理
  - 取消回调：自动资源清理
  - `TaskCancelledException`: 任务取消异常
  - 集成到 `BatchProcessor` 支持中途取消任务

- **动态负载均衡** (`core/load_balancer.py`)
  - `DynamicLoadBalancer`: 自适应worker数量调整
  - 基于psutil的系统资源监控（CPU、内存）
  - 可配置的阈值（cpu_threshold, memory_threshold）
  - 根据任务大小智能分配资源
  - 任务历史记录和统计
  - 辅助函数：`get_system_info()`

- **改进的错误处理**:
  - 批处理中的取消检查
  - Future清理和executor shutdown
  - KeyboardInterrupt捕获和转换

#### Phase 3.2: 数据导出统一接口
- **统一导出器**: 多格式数据导出支持 (`core/data/export.py`)
  - `DataExporter`: 统一的导出接口
  - 支持格式: Parquet, HDF5, CSV, JSON, NumPy (.npy, .npz)
  - 自动格式推断（从文件扩展名）
  - 智能数据类型转换（DataFrame/NumPy/Dict）
- **批量导出**:
  - `batch_export()`: 批量导出多个run的数据
  - 并行导出支持
  - 进度跟踪
- **格式特定选项**: 支持各格式的高级参数
  - Parquet: 压缩选项
  - HDF5: 自定义key
  - CSV: 分隔符配置
  - JSON: 格式化选项

#### Phase 3.3: 插件热重载
- **热重载系统**: 开发友好的插件热重载 (`core/hot_reload.py`)
  - `PluginHotReloader`: 文件变化监控和自动重载
  - 文件变化检测（mtime + MD5 hash）
  - 模块动态重载
  - 缓存一致性维护
- **自动重载**: 守护线程支持
  - 可配置的检查间隔
  - 自动模块刷新
  - 缓存自动清理
- **开发工作流**:
  - `enable_hot_reload()`: 一键启用热重载
  - 手动重载控制
  - 批量重载支持
  - 开发/生产环境分离

### 文档
- **新增**: `docs/NEW_FEATURES.md` - Phase 2和3新功能完整文档
- **更新**: `CLAUDE.md` - 添加新组件说明和使用示例
- **代码示例**: 每个新功能都包含详细的使用示例

### 测试
- **新增**: `tests/test_time_range_query.py` - 时间范围查询测试 (7个测试, 全部通过)
- **新增**: `tests/test_strax_adapter.py` - Strax适配器测试 (10个测试, 核心功能通过)
- **覆盖率**: 新增模块代码覆盖率 46-80%

### 依赖
- **新增**: `tqdm>=4.66.0` - 进度条显示库（用于统一进度追踪）
- **新增**: `psutil>=5.9.0` - 系统资源监控库（用于动态负载均衡）

### 修复
- **CSV 表头处理**: 修复了 CSV 文件读取时的表头处理问题
  - 现在只有每个通道的第一个文件会跳过表头行（`skiprows`）
  - 后续文件不再跳过任何行（`skiprows=0`），因为它们不包含表头
  - 影响函数：`parse_and_stack_files` 和 `parse_files_generator`
  - 相关文档：`docs/DAQ_CSV_HEADER_HANDLING.md`
  - 测试：`tests/test_DAQ_CSV_HEADER_HANDLING.py`

### 性能改进
- **时间查询**: 从O(n)线性扫描优化到O(log n)二分查找
- **批量处理**: 并行处理支持，显著提升多run处理速度
- **数据导出**: Parquet格式提供高性能和压缩比

### 计划功能
- 更多内置拟合模型
- 交互式可视化工具
- Web 界面
- 进一步性能优化

## [0.1.0] - 2024-12-24

### 新增
- 🎉 首次发布
- 完整的包结构重组
- 标准化的 Python 包
- 模块化架构设计
- 链式 API 调用支持
- 特征注册系统
- 自定义配对策略支持
- 时间戳索引缓存优化
- 命令行工具 `waveform-process`
- 完整的文档体系
- 示例脚本和教程
- 测试框架
- CI/CD 配置（预留）

### 核心功能
- **数据加载**:
  - 高效的多通道数据加载
  - 文件自动识别和排序
  - 错误处理和空文件跳过

- **数据处理**:
  - 波形结构化
  - 基线校正
  - 峰值和电荷计算
  - 事件时间戳提取

- **事件配对**:
  - 基于时间窗口的多通道配对
  - 可配置的时间窗口
  - 自定义配对策略支持

- **特征提取**:
  - 内置峰值和电荷计算
  - 可扩展的特征注册系统
  - 自动特征计算和缓存

- **数据导出**:
  - CSV 格式支持
  - Parquet 格式支持
  - 灵活的保存选项

### 拟合模块
- Landau-Gauss 卷积拟合
- JAX 加速计算
- 基于 iminuit 的优化

### 文档
- README.md - 项目主文档
- QUICKSTART.md - 快速开始指南
- USAGE.md - 详细使用文档
- PROJECT_STRUCTURE.md - 项目结构说明
- CONTRIBUTING.md - 贡献指南
- 原模块文档保留

### 工具
- 快速安装脚本 `install.sh`
- 安装验证脚本 `verify_install.py`
- 命令行接口

### 测试
- 基础功能测试
- 数据加载测试
- pytest 配置

### 配置
- pyproject.toml - 现代配置
- setup.py - 向后兼容
- requirements.txt - 依赖管理
- .gitignore - Git 配置

## [0.0.1] - 2024-12-XX (内部版本)

### 初始实现
- 基础数据加载功能
- 简单的数据处理
- Jupyter 笔记本示例
- 独立的 Python 脚本

---

## 版本说明

### 语义化版本格式

- **主版本号 (MAJOR)**: 不兼容的 API 修改
- **次版本号 (MINOR)**: 向下兼容的功能性新增
- **修订号 (PATCH)**: 向下兼容的问题修正

### 变更类型

- `新增` - 新功能
- `变更` - 已有功能的变更
- `弃用` - 即将移除的功能
- `移除` - 已移除的功能
- `修复` - 问题修复
- `安全` - 安全相关的修复

---

[未发布]: https://github.com/yourusername/waveform-analysis/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/yourusername/waveform-analysis/releases/tag/v0.1.0
