# 更新日志

所有重要的项目变更都会记录在此文件中。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
本项目遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [未发布]

### 新增 (Phase 2 & 3)

#### Phase 2.2: 数据时间范围查询优化
- **时间索引系统**: 新增高效的时间索引功能 (`core/time_range_query.py`)
  - `TimeIndex`: O(log n)复杂度的二分查找时间索引
  - `TimeRangeQueryEngine`: 管理多数据类型的时间索引
  - `TimeRangeCache`: 查询结果缓存
- **Context集成**: 新增时间范围查询方法
  - `get_data_time_range()`: 查询指定时间范围的数据
  - `build_time_index()`: 预构建时间索引
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
- **批量处理器**: 高效的多运行并行处理 (`core/batch_export.py`)
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
  - 集成到 `BatchProcessor.process_runs()` 和 `process_with_custom_func()`

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
- **统一导出器**: 多格式数据导出支持 (`core/batch_export.py`)
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
  - 相关文档：`docs/CSV_HEADER_HANDLING.md`
  - 测试：`tests/test_csv_header_handling.py`

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
