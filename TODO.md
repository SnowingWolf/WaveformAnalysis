# TODO - 功能增强计划

## 高优先级（立即实施）

### 1. 统一进度追踪系统
- [ ] 创建统一的进度追踪装饰器 `@with_progress`
- [ ] 为 `parallel_map` 和 `parallel_apply` 添加进度条支持
- [x] 实现嵌套进度条（主任务 + 子任务）
- [x] 显示 ETA（预计剩余时间）和吞吐量统计
- [x] 支持 tqdm 和自定义进度条后端
- [x] 集成到 BatchProcessor 中（Context 和 StreamingPlugin 待集成）

### 2. 任务取消和中断机制
- [x] 实现 CancellationToken 支持 Ctrl+C 优雅中断
- [x] 添加 CancellationManager 管理取消令牌
- [ ] 添加 `cancel_pending_tasks()` 方法取消未开始的任务
- [ ] 实现任务超时后的强制取消机制
- [x] 添加资源清理逻辑（取消时自动释放）
- [x] 支持部分完成模式（部分任务成功时返回部分结果）

### 3. 数据质量标记和过滤系统
- [ ] 定义 `DataQuality` 枚举（GOOD, SUSPICIOUS, BAD, MISSING）
- [ ] 在插件中添加 `_assess_quality()` 方法
- [ ] 实现自动质量标记功能
- [ ] 添加 `quality_filter` 配置选项
- [ ] 实现质量报告生成功能
- [ ] 支持基于质量标记的自动过滤

## 中优先级（中期实施）

### 4. 动态负载均衡
- [x] 创建 `DynamicLoadBalancer` 类
- [x] 实现基于 CPU 使用率的动态 worker 调整
- [x] 添加内存使用率监控
- [x] 实现负载均衡算法（根据任务大小分配）
- [x] 添加配置选项（min_workers, max_workers, cpu_threshold, memory_threshold）
- [ ] 集成到 ExecutorManager 中

### 5. 数据一致性检查器
- [ ] 创建 `DataConsistencyChecker` 类
- [ ] 实现时间戳对齐检查
- [ ] 实现通道映射一致性检查
- [ ] 实现事件计数验证
- [ ] 添加跨插件数据一致性验证
- [ ] 生成详细的一致性报告

### 6. 智能缓存策略
- [ ] 实现 LRU（最近最少使用）缓存策略
- [ ] 实现 LFU（最不经常使用）缓存策略
- [ ] 实现基于大小的缓存清理
- [ ] 实现基于时间的缓存过期
- [x] 添加缓存策略配置接口（CacheManager 已实现基础功能）
- [x] 集成到 Context 的缓存管理中（基础缓存管理已集成）

### 7. 任务优先级队列
- [ ] 创建 `PriorityExecutor` 类
- [ ] 实现优先级任务队列（PriorityQueue）
- [ ] 支持任务暂停和恢复
- [ ] 实现优先级抢占机制
- [ ] 添加优先级配置接口
- [ ] 集成到 ExecutorManager 中

### 8. 文件结构重构（代码质量改进）🟡

#### 阶段1：合并和重命名（低风险，高收益）
- [ ] **合并 processor 文件**
  - [ ] 将 `processor_optimized.py` 的内容整合到 `processor.py`
  - [ ] 使用条件导入或特性标志（`USE_NUMBA`）选择优化版本
  - [ ] 删除 `processor_optimized.py`
  - [ ] 更新所有导入路径

- [ ] **解决 loader.py 命名冲突**
  - [ ] 重命名 `core/loader.py` → `core/waveform_loader.py`
  - [ ] 更新 `core/__init__.py` 中的导入
  - [ ] 更新所有引用 `WaveformLoader` 的代码
  - [ ] 保持 `utils/loader.py` 不变（工具函数）

- [ ] **重命名混乱的文件**
  - [ ] `processor_optimized.py` → 合并到 `processor.py`（见上）
  - [ ] 检查 `storage_backends.py` 的使用情况，决定是否合并或重命名

#### 阶段2：创建存储子目录（存储相关文件较多）
- [ ] **创建 `core/storage/` 目录**
  - [ ] 创建 `core/storage/__init__.py`
  - [ ] 移动 `storage.py` → `storage/memmap.py`
  - [ ] 移动 `storage_backends.py` → `storage/backends.py`
  - [ ] 移动 `cache.py` → `storage/cache.py`
  - [ ] 移动 `compression.py` → `storage/compression.py`
  - [ ] 移动 `integrity.py` → `storage/integrity.py`

- [ ] **更新 storage/__init__.py**
  - [ ] 导出主要接口：`MemmapStorage`, `StorageBackend`, `CacheManager`, `CompressionManager`, `IntegrityChecker`
  - [ ] 保持向后兼容的导入路径

- [ ] **更新所有导入路径**
  - [ ] 更新 `core/context.py` 中的导入
  - [ ] 更新 `core/dataset.py` 中的导入
  - [ ] 更新测试文件中的导入
  - [ ] 更新文档中的示例代码

- [ ] **添加向后兼容层（可选）**
  - [ ] 在 `core/__init__.py` 中添加兼容性导入
  - [ ] 添加 DeprecationWarning（如果决定废弃旧路径）

#### 阶段3：创建执行器子目录（执行器相关文件较多）
- [ ] **创建 `core/execution/` 目录**
  - [ ] 创建 `core/execution/__init__.py`
  - [ ] 移动 `executor_manager.py` → `execution/manager.py`
  - [ ] 移动 `executor_config.py` → `execution/config.py`
  - [ ] 移动 `timeout_manager.py` → `execution/timeout.py`

- [ ] **更新 execution/__init__.py**
  - [ ] 导出主要接口：`ExecutorManager`, `get_executor`, `parallel_map`, `parallel_apply`
  - [ ] 导出配置：`EXECUTOR_CONFIGS`, `get_config`
  - [ ] 导出超时管理：`TimeoutManager`, `get_timeout_manager`

- [ ] **更新所有导入路径**
  - [ ] 更新 `core/context.py` 中的导入
  - [ ] 更新 `core/streaming.py` 中的导入
  - [ ] 更新 `core/processor.py` 中的导入
  - [ ] 更新 `utils/io.py` 中的导入
  - [ ] 更新所有使用执行器的插件
  - [ ] 更新测试文件

- [ ] **添加向后兼容层（可选）**
  - [ ] 在 `core/__init__.py` 中添加兼容性导入
  - [ ] 添加 DeprecationWarning

#### 阶段4：创建插件子目录（分离核心基础设施和内置插件）
- [ ] **创建 `core/plugins/` 目录结构**
  - [ ] 创建 `core/plugins/__init__.py`
  - [ ] 创建 `core/plugins/core/` 子目录（核心基础设施）
  - [ ] 创建 `core/plugins/builtin/` 子目录（内置标准插件）

- [ ] **移动核心基础设施到 `plugins/core/`**
  - [ ] 创建 `plugins/core/__init__.py`
  - [ ] 移动 `plugins.py` → `plugins/core/base.py`（Plugin, Option 基类）
  - [ ] 移动 `streaming.py` → `plugins/core/streaming.py`（StreamingPlugin 基类）
  - [ ] 移动 `plugin_loader.py` → `plugins/core/loader.py`（PluginLoader）
  - [ ] 移动 `plugin_stats.py` → `plugins/core/stats.py`（PluginStatsCollector）
  - [ ] 移动 `hot_reload.py` → `plugins/core/hot_reload.py`（PluginHotReloader）
  - [ ] 移动 `strax_adapter.py` → `plugins/core/adapters.py`（StraxPluginAdapter）

- [ ] **移动内置插件到 `plugins/builtin/`**
  - [ ] 创建 `plugins/builtin/__init__.py`
  - [ ] 移动 `standard_plugins.py` → `plugins/builtin/standard.py`（RawFilesPlugin, WaveformsPlugin等）
  - [ ] 移动 `streaming_plugins.py` → `plugins/builtin/streaming_examples.py`（StreamingStWaveformsPlugin等）

- [ ] **更新 plugins/core/__init__.py**
  - [ ] 导出核心基类：`Plugin`, `Option`
  - [ ] 导出流式基类：`StreamingPlugin`
  - [ ] 导出工具：`PluginLoader`, `PluginStatsCollector`, `PluginHotReloader`, `enable_hot_reload`
  - [ ] 导出适配器：`StraxPluginAdapter`, `wrap_strax_plugin`, `create_strax_context`

- [ ] **更新 plugins/builtin/__init__.py**
  - [ ] 导出标准插件：`RawFilesPlugin`, `WaveformsPlugin`, `StWaveformsPlugin`, `BasicFeaturesPlugin`, `DataFramePlugin`, `GroupedEventsPlugin`, `PairedEventsPlugin`
  - [ ] 导出流式插件示例：`StreamingStWaveformsPlugin`, `StreamingBasicFeaturesPlugin`, `StreamingFilterPlugin`

- [ ] **更新 plugins/__init__.py（统一导出）**
  - [ ] 从 `core` 子模块导出核心基础设施
  - [ ] 从 `builtin` 子模块导出内置插件
  - [ ] 保持向后兼容的导入路径

- [ ] **更新所有导入路径**
  - [ ] 更新 `core/context.py` 中的导入
  - [ ] 更新 `core/dataset.py` 中的导入
  - [ ] 更新 `core/mixins.py` 中的导入
  - [ ] 更新所有使用插件的测试文件
  - [ ] 更新文档中的示例代码

- [ ] **添加向后兼容层（重要）**
  - [ ] 在 `core/__init__.py` 中添加兼容性导入
  - [ ] 确保 `from waveform_analysis.core.plugins import Plugin` 仍然可用
  - [ ] 确保 `from waveform_analysis.core.standard_plugins import RawFilesPlugin` 仍然可用
  - [ ] 确保 `from waveform_analysis.core.plugin_loader import PluginLoader` 仍然可用
  - [ ] 添加 DeprecationWarning（建议使用新路径 `plugins.core` 和 `plugins.builtin`）

#### 阶段5：创建数据处理子目录（数据处理流水线相关文件）
- [ ] **创建 `core/processing/` 目录**
  - [ ] 创建 `core/processing/__init__.py`
  - [ ] 移动 `waveform_loader.py` → `processing/loader.py`
  - [ ] 移动 `processor.py` → `processing/processor.py`（已合并 processor_optimized.py）
  - [ ] 移动 `analyzer.py` → `processing/analyzer.py`
  - [ ] 移动 `chunk_utils.py` → `processing/chunk.py`

- [ ] **更新 processing/__init__.py**
  - [ ] 导出数据加载：`WaveformLoader`
  - [ ] 导出信号处理：`WaveformStruct`, `build_waveform_df`, `group_multi_channel_hits`
  - [ ] 导出事件分析：`EventAnalyzer`
  - [ ] 导出 Chunk 工具：`Chunk`, `ChunkInfo`, `ValidationResult`, 以及所有 chunk 相关函数
  - [ ] 保持向后兼容的导入路径

- [ ] **更新所有导入路径**
  - [ ] 更新 `core/context.py` 中的导入
  - [ ] 更新 `core/dataset.py` 中的导入
  - [ ] 更新 `core/plugins/standard.py` 中的导入
  - [ ] 更新所有使用处理功能的测试文件
  - [ ] 更新文档中的示例代码

- [ ] **添加向后兼容层（重要）**
  - [ ] 在 `core/__init__.py` 中添加兼容性导入
  - [ ] 确保 `from waveform_analysis.core.processor import WaveformStruct` 仍然可用
  - [ ] 确保 `from waveform_analysis.core.chunk_utils import Chunk` 仍然可用
  - [ ] 添加 DeprecationWarning（建议使用新路径）

#### 阶段6：创建数据管理子目录（数据查询和导出相关文件）
- [ ] **创建 `core/data/` 目录**
  - [ ] 创建 `core/data/__init__.py`
  - [ ] 移动 `time_range_query.py` → `data/query.py`
  - [ ] 移动 `batch_export.py` → `data/export.py`

- [ ] **更新 data/__init__.py**
  - [ ] 导出时间查询：`TimeIndex`, `TimeRangeQueryEngine`, `TimeRangeCache`
  - [ ] 导出批量处理：`BatchProcessor`
  - [ ] 导出数据导出：`DataExporter`, `batch_export`
  - [ ] 保持向后兼容的导入路径

- [ ] **更新所有导入路径**
  - [ ] 更新 `core/context.py` 中的导入
  - [ ] 更新 `core/dataset.py` 中的导入
  - [ ] 更新所有使用数据管理功能的测试文件
  - [ ] 更新文档中的示例代码

- [ ] **添加向后兼容层（可选）**
  - [ ] 在 `core/__init__.py` 中添加兼容性导入
  - [ ] 添加 DeprecationWarning

#### 阶段7：创建框架基础设施子目录（框架基础组件）
- [ ] **创建 `core/foundation/` 目录**
  - [ ] 创建 `core/foundation/__init__.py`
  - [ ] 移动 `exceptions.py` → `foundation/exceptions.py`
  - [ ] 移动 `mixins.py` → `foundation/mixins.py`
  - [ ] 移动 `model.py` → `foundation/model.py`
  - [ ] 移动 `utils.py` → `foundation/utils.py`
  - [ ] 移动 `progress_tracker.py` → `foundation/progress.py`

- [ ] **更新 foundation/__init__.py**
  - [ ] 导出异常：`ErrorSeverity`, `PluginError`, `ErrorContext`, `PluginTimeoutError`
  - [ ] 导出 Mixin：`CacheMixin`, `StepMixin`, `chainable_step`
  - [ ] 导出模型：`PortModel`, `NodeModel`, `EdgeModel`, `LineageGraphModel`
  - [ ] 导出工具：`exporter`, `Profiler`, `LineageStyle`, `OneTimeGenerator`
  - [ ] 导出进度：`ProgressTracker`
  - [ ] 保持向后兼容的导入路径

- [ ] **更新所有导入路径**
  - [ ] 更新 `core/context.py` 中的导入
  - [ ] 更新 `core/dataset.py` 中的导入
  - [ ] 更新 `core/mixins.py` 中的导入（如果还在使用）
  - [ ] 更新所有使用基础组件的文件
  - [ ] 更新测试文件

- [ ] **添加向后兼容层（重要）**
  - [ ] 在 `core/__init__.py` 中添加兼容性导入
  - [ ] 确保 `from waveform_analysis.core.exceptions import PluginError` 仍然可用
  - [ ] 确保 `from waveform_analysis.core.utils import exporter` 仍然可用
  - [ ] 添加 DeprecationWarning（建议使用新路径）

#### 阶段8：验证和测试
- [ ] **运行完整测试套件**
  - [ ] 确保所有单元测试通过
  - [ ] 确保所有集成测试通过
  - [ ] 检查导入路径是否正确

- [ ] **更新文档**
  - [ ] 更新 `docs/PROJECT_STRUCTURE.md`
  - [ ] 更新 `CLAUDE.md` 中的架构说明
  - [ ] 更新所有示例代码中的导入路径

- [ ] **代码审查**
  - [ ] 检查是否有遗漏的导入路径
  - [ ] 检查向后兼容性是否完整
  - [ ] 确认重构后的结构更清晰

#### 重构后的目标结构
```
core/
├── __init__.py                    # 统一导出，保持向后兼容
│
├── # 核心文件（保持扁平，最常用）
├── context.py
├── dataset.py
│
├── # 插件相关（子目录，分离核心和内置）
├── plugins/
│   ├── __init__.py                # 统一导出，保持向后兼容
│   │
│   ├── core/                      # 核心基础设施
│   │   ├── __init__.py
│   │   ├── base.py                # 原 plugins.py (Plugin, Option)
│   │   ├── streaming.py           # 原 streaming.py (StreamingPlugin)
│   │   ├── loader.py              # 原 plugin_loader.py
│   │   ├── stats.py               # 原 plugin_stats.py
│   │   ├── hot_reload.py          # 原 hot_reload.py
│   │   └── adapters.py            # 原 strax_adapter.py
│   │
│   └── builtin/                   # 内置标准插件
│       ├── __init__.py
│       ├── standard.py            # 原 standard_plugins.py
│       └── streaming_examples.py  # 原 streaming_plugins.py
│
├── # 存储相关（子目录）
├── storage/
│   ├── __init__.py
│   ├── memmap.py                 # 原 storage.py
│   ├── backends.py               # 原 storage_backends.py
│   ├── cache.py                  # 原 cache.py
│   ├── compression.py            # 原 compression.py
│   └── integrity.py              # 原 integrity.py
│
├── # 执行器相关（子目录）
├── execution/
│   ├── __init__.py
│   ├── manager.py                # 原 executor_manager.py
│   ├── config.py                 # 原 executor_config.py
│   └── timeout.py                # 原 timeout_manager.py
│
├── # 数据处理流水线（子目录）
├── processing/
│   ├── __init__.py
│   ├── loader.py                 # 原 waveform_loader.py
│   ├── processor.py              # 合并 processor_optimized.py
│   ├── analyzer.py               # 原 analyzer.py
│   └── chunk.py                  # 原 chunk_utils.py
│
├── # 数据管理和查询（子目录）
├── data/
│   ├── __init__.py
│   ├── query.py                  # 原 time_range_query.py
│   └── export.py                 # 原 batch_export.py
│
└── # 框架基础设施（子目录）
    └── foundation/
        ├── __init__.py
        ├── exceptions.py         # 原 exceptions.py
        ├── mixins.py             # 原 mixins.py
        ├── model.py              # 原 model.py
        ├── utils.py              # 原 utils.py
        └── progress.py           # 原 progress_tracker.py
```

#### 重构原则
- ✅ **模块化组织**：创建六个主要子目录（plugins/, storage/, execution/, processing/, data/, foundation/）
- ✅ **插件分离**：将核心基础设施（core/）和内置插件（builtin/）分离，职责更清晰
- ✅ **大幅减少扁平文件**：从27个扁平文件减少到2个核心文件（context.py, dataset.py）
- ✅ **保持兼容**：通过 `__init__.py` 保持向后兼容
- ✅ **渐进式**：分阶段实施，每步可独立验证
- ✅ **低风险**：优先处理低风险的重命名和合并
- ✅ **逻辑分组**：按功能领域分组，便于理解和维护
- ✅ **易于扩展**：用户自定义插件可以独立管理，不混入核心代码

## 低优先级（按需实施）

### 9. 数据版本管理和回滚
- [ ] 实现数据版本保存功能 `save_version()`
- [ ] 实现版本回滚功能 `rollback()`
- [ ] 实现版本对比功能 `compare_versions()`
- [ ] 添加版本元数据管理
- [ ] 实现版本清理策略（保留最近 N 个版本）

### 10. 数据采样和预览
- [ ] 实现智能采样功能 `get_data_sample()`
- [ ] 支持多种采样策略（random, stratified, time_based）
- [ ] 实现快速预览功能 `preview()`
- [ ] 添加采样配置选项
- [ ] 优化大数据集的探索体验

### 11. 插件依赖可视化增强
- [ ] 实现交互式依赖图（使用 plotly/d3.js）
- [ ] 添加依赖分析功能 `analyze_dependencies()`
- [ ] 识别关键路径和并行机会
- [ ] 识别性能瓶颈
- [ ] 生成优化建议

### 12. 数据血缘追踪增强
- [ ] 实现详细的血缘追踪 `get_detailed_lineage()`
- [ ] 记录处理步骤的时间戳和配置
- [ ] 记录数据转换历史
- [ ] 实现影响分析 `get_affected_data()`
- [ ] 支持血缘查询和过滤

### 13. 插件性能基准测试
- [ ] 创建 `PluginBenchmark` 类
- [ ] 实现多数据规模的基准测试
- [ ] 生成性能报告（执行时间、内存、吞吐量）
- [ ] 支持性能回归检测
- [ ] 添加基准测试结果可视化

### 14. 数据导出格式增强
- [ ] 支持 ROOT 格式导出（高能物理常用）
- [ ] 支持 HDF5 格式导出
- [ ] 支持 Apache Arrow 格式导出
- [ ] 实现自定义导出器注册机制
- [ ] 添加导出器插件系统

### 15. 实时监控和告警
- [ ] 创建 `SystemMonitor` 类
- [ ] 实现系统资源监控（CPU、内存、磁盘）
- [ ] 实现插件执行监控
- [ ] 添加告警阈值配置
- [ ] 实现 Web 监控面板（可选）
- [ ] 支持通知回调（邮件、Slack 等）

### 16. 插件性能自动优化建议
- [ ] 创建 `PerformanceAnalyzer` 类
- [ ] 实现性能问题自动检测
- [ ] 生成优化建议（内存优化、并行优化等）
- [ ] 估算优化后的性能提升
- [ ] 提供一键应用优化建议

## 已识别但未实施的 Strax 特性

### 多运行批量处理
- [x] 已实现 `BatchProcessor`（Phase 3.1）
- [x] 已集成进度追踪和取消机制

### 数据压缩选项
- [x] 已实现压缩支持（blosc2, lz4, zstd, gzip）
- [x] 已实现 `CompressionManager` 和多种压缩后端

### 插件超时控制
- [x] 已实现 `TimeoutManager` 和 `PluginTimeoutError`
- [x] 已集成到插件执行流程中

### 数据完整性校验
- [x] 已实现 `IntegrityChecker` 和 checksum 支持
- [x] 支持多种哈希算法（xxhash64, sha256, md5）

### 插件热重载
- [x] 已实现 `PluginHotReloader`（Phase 3.3）
- [x] 支持文件监控和自动重载

### 数据导出统一接口
- [x] 已实现 `DataExporter`（Phase 3.2）
- [x] 支持多种格式（Parquet, HDF5, CSV, JSON, NumPy）

### 时间范围查询优化
- [x] 已实现 `TimeRangeQueryEngine`（Phase 2.2）
- [x] 已实现 `TimeIndex` 和高效查询算法

## 性能优化建议（来自 TODO.md 原始内容）

### 数据加载与 I/O 优化
- [ ] 并行读取 CSV 文件：利用 ThreadPoolExecutor 或 joblib 同时读取多个文件
- [ ] 分块读取与流式处理：使用 `parse_files_generator` 逐块处理，降低内存峰值
- [ ] 利用高效数据格式：将波形数据转换为二进制格式（.npy, Feather/Parquet, HDF5）

### 内存占用与缓存优化
- [ ] 按需保存与释放波形数据：改进 `load_waveforms=False` 模式，边读边算特征
- [ ] 利用缓存避免重复计算：使用 joblib 后端优化大数组序列化
- [ ] 缓存失效机制：引入文件 hash 或 mtime 监测，防止使用过期缓存

## 备注

- 优先级标记：🔴 高优先级、🟡 中优先级、🟢 低优先级
- 已完成的功能标记为 [x]
- 建议按优先级顺序实施，高优先级功能优顺序
