# 功能特性

**导航**: [文档中心](../README.md) > 功能特性

详细的功能说明和使用指南，按主题分类组织。

## 使用建议

- 想了解系统能力全貌：从本页的功能分类进入
- 只关心某个功能：直接跳到"按场景查找"
- 需要插件具体细节：查看 [插件详解](../plugins/README.md)

## 功能分类

### [Context 功能](context/README.md)

依赖分析、血缘可视化、执行预览、配置管理、数据访问等。

- [配置管理](context/CONFIGURATION.md)
- [数据访问](context/DATA_ACCESS.md)
- [依赖分析](context/DEPENDENCY_ANALYSIS_GUIDE.md)
- [血缘可视化](context/LINEAGE_VISUALIZATION_GUIDE.md)
- [执行预览](context/PREVIEW_EXECUTION.md)
- [批处理器](context/BATCH_PROCESSOR.md)
- [插件管理](context/PLUGIN_MANAGEMENT.md)

### [核心功能](context/README.md)

绝对时间查询与 DAQ 时间基准。

- [绝对时间查询](context/ABSOLUTE_TIME_GUIDE.md)
- [DAQ 适配器](../plugins/DAQ_ADAPTER_GUIDE.md)

### [插件功能](plugin/README.md)

信号处理插件、流式处理插件、Strax 适配器、插件开发教程。

- [插件功能概述](plugin/PLUGIN_FEATURE.md)
- [信号处理插件](plugin/SIGNAL_PROCESSING_PLUGINS.md)
- [流式处理插件](plugin/STREAMING_PLUGINS_GUIDE.md)
- [插件开发教程](plugin/SIMPLE_PLUGIN_GUIDE.md)

### [高级功能](advanced/README.md)

执行器管理、进度追踪、CSV 处理等。

- [执行器管理](advanced/EXECUTOR_MANAGER_GUIDE.md)
- [进度追踪](advanced/PROGRESS_TRACKING_GUIDE.md)
- [CSV 文件头处理](advanced/IO_CSV_HEADER_HANDLING.md)

### [工具函数](utils/README.md)

DAQ 适配器、事件筛选、波形预览等实用工具。

- [DAQ 适配器](utils/DAQ_ADAPTER_GUIDE.md)
- [DAQ 分析器](utils/DAQ_ANALYZER_GUIDE.md)
- [事件筛选](utils/EVENT_FILTERS_GUIDE.md)
- [波形预览](utils/waveform_preview.md)

## 按场景查找

| 场景 | 文档 |
|------|------|
| 管理执行器 | [EXECUTOR_MANAGER_GUIDE.md](advanced/EXECUTOR_MANAGER_GUIDE.md) |
| 了解缓存机制 | [DATA_ACCESS.md](context/DATA_ACCESS.md) |
| 追踪进度 | [PROGRESS_TRACKING_GUIDE.md](advanced/PROGRESS_TRACKING_GUIDE.md) |
| 处理 CSV 文件头 | [IO_CSV_HEADER_HANDLING.md](advanced/IO_CSV_HEADER_HANDLING.md) |
| 配置 DAQ 数据格式 | [DAQ_ADAPTER_GUIDE.md](utils/DAQ_ADAPTER_GUIDE.md) |
| 查看 DAQ 运行概览 | [DAQ_ANALYZER_GUIDE.md](utils/DAQ_ANALYZER_GUIDE.md) |
| 可视化数据血缘 | [LINEAGE_VISUALIZATION_GUIDE.md](context/LINEAGE_VISUALIZATION_GUIDE.md) |
| 分析依赖关系 | [DEPENDENCY_ANALYSIS_GUIDE.md](context/DEPENDENCY_ANALYSIS_GUIDE.md) |
| 预览执行计划 | [PREVIEW_EXECUTION.md](context/PREVIEW_EXECUTION.md) |
| 管理配置 | [CONFIGURATION.md](context/CONFIGURATION.md) |
| 绝对时间查询 | [ABSOLUTE_TIME_GUIDE.md](context/ABSOLUTE_TIME_GUIDE.md) |
| 筛选事件数据 | [EVENT_FILTERS_GUIDE.md](utils/EVENT_FILTERS_GUIDE.md) |
| 预览波形 | [waveform_preview.md](utils/waveform_preview.md) |
| 使用信号处理插件 | [SIGNAL_PROCESSING_PLUGINS.md](plugin/SIGNAL_PROCESSING_PLUGINS.md) |
| 开发自定义插件 | [SIMPLE_PLUGIN_GUIDE.md](plugin/SIMPLE_PLUGIN_GUIDE.md) |

## 学习路径

### 基础功能

1. [Context 功能](context/README.md)
2. [核心功能](core/README.md)
3. [工具函数](utils/README.md)

### 高级功能

1. 基础功能
2. [高级功能](advanced/README.md)
3. [插件功能](plugin/README.md)

## 相关资源

- [用户指南](../user-guide/README.md) - 快速入门
- [API 参考](../api/README.md) - API 文档
- [架构设计](../architecture/README.md) - 系统架构
- [插件详解](../plugins/README.md) - 内置插件说明
