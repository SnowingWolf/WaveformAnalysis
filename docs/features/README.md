# 功能特性

**导航**: [文档中心](../README.md) > 功能特性

详细的功能说明和使用指南，按主题分类组织。

## 使用建议

- 想了解系统能力全貌：从本页的功能分类进入
- 只关心某个功能：直接跳到"按场景查找"
- 需要插件具体细节：查看 [插件详解](../plugins/README.md)

## 按角色选择入口

| 角色 | 入口 | 说明 |
|---|---|---|
| 使用者 | [Context 功能](context/README.md) | 配置、缓存、执行链等核心能力 |
| 使用者 | [插件详解](../plugins/README.md) | 内置插件的具体用法与实现细节 |
| 开发者 | [开发者指南](../development/README.md) | 系统架构、插件开发和代码规范 |
| 运维 | [命令行工具](../cli/README.md) | CLI 使用指南 |

## 功能分类

### [Context 功能](context/README.md)

依赖分析、血缘可视化、执行预览、配置管理等。正式产物、缓存与波形访问的架构边界见下方专题。

- [配置管理](context/CONFIGURATION.md)
- [Plugin DAG、lineage 与缓存](../architecture/PLUGIN_DAG_LINEAGE_CACHE.md)
- [数据产物与波形访问](../architecture/DATA_PRODUCTS.md)
- [依赖分析](context/DEPENDENCY_ANALYSIS_GUIDE.md)
- [血缘可视化](context/LINEAGE_VISUALIZATION_GUIDE.md)
- [批处理器](context/BATCH_PROCESSOR.md)

### [核心功能](context/README.md)

绝对时间查询与 DAQ 时间基准。

- [绝对时间查询](context/ABSOLUTE_TIME_GUIDE.md)
- [DAQ 适配器](../plugins/reference/ADAPTER_SYSTEM_GUIDE.md)

### [插件功能](../plugins/README.md)

信号处理插件、流式处理插件、Strax 适配器、插件开发教程。

- [插件系统与模板 API](../plugins/PLUGIN_SYSTEM_OVERVIEW.md)
- [滤波插件参考](../plugins/reference/agent/filtered_waveforms.md)
- [峰值检测插件参考](../plugins/reference/agent/hit.md)
- [流式处理插件](../plugins/guides/STREAMING_PLUGINS_GUIDE.md)

### [高级功能](advanced/README.md)

进度追踪等高级功能。全局执行器与 Context 执行协作见[系统架构](../architecture/ARCHITECTURE.md)。

- [进度追踪](advanced/PROGRESS_TRACKING_GUIDE.md)

### [工具函数](utils/README.md)

DAQ 适配器、DAQ 运行分析与事件筛选等实用工具。

- [DAQ 适配器](../plugins/reference/ADAPTER_SYSTEM_GUIDE.md)
- [DAQ 分析器](utils/DAQ_ANALYZER_GUIDE.md)

### 可视化功能

- [位置二维 Dashboard](visualizations/POSITION_DASHBOARD_GUIDE.md) - 位置重建、S1/S2 分布与交互式二维检查

## 按场景查找

| 场景 | 文档 |
|------|------|
| 管理执行器 | [系统架构：执行器管理框架](../architecture/ARCHITECTURE.md#执行器管理框架) |
| 了解缓存机制 | [PLUGIN_DAG_LINEAGE_CACHE.md](../architecture/PLUGIN_DAG_LINEAGE_CACHE.md) |
| 追踪进度 | [PROGRESS_TRACKING_GUIDE.md](advanced/PROGRESS_TRACKING_GUIDE.md) |
| 配置 DAQ 数据格式 | [ADAPTER_SYSTEM_GUIDE.md](../plugins/reference/ADAPTER_SYSTEM_GUIDE.md) |
| 查看 DAQ 运行概览 | [DAQ_ANALYZER_GUIDE.md](utils/DAQ_ANALYZER_GUIDE.md) |
| 使用位置二维 Dashboard | [POSITION_DASHBOARD_GUIDE.md](visualizations/POSITION_DASHBOARD_GUIDE.md) |
| 可视化数据血缘 | [LINEAGE_VISUALIZATION_GUIDE.md](context/LINEAGE_VISUALIZATION_GUIDE.md) |
| 分析依赖关系 | [DEPENDENCY_ANALYSIS_GUIDE.md](context/DEPENDENCY_ANALYSIS_GUIDE.md) |
| 管理配置 | [CONFIGURATION.md](context/CONFIGURATION.md) |
| 绝对时间查询 | [ABSOLUTE_TIME_GUIDE.md](context/ABSOLUTE_TIME_GUIDE.md) |
| 使用滤波插件 | [filtered_waveforms.md](../plugins/reference/agent/filtered_waveforms.md) |
| 使用峰值检测插件 | [hit.md](../plugins/reference/agent/hit.md) |
| 开发自定义插件 | [PLUGIN_SYSTEM_OVERVIEW.md](../plugins/PLUGIN_SYSTEM_OVERVIEW.md) |

## 学习路径

### 基础功能

1. [Context 功能](context/README.md)
2. [核心功能](context/README.md)
3. [工具函数](utils/README.md)

### 高级功能

1. 基础功能
2. [高级功能](advanced/README.md)
3. [插件功能](../plugins/README.md)

## 相关资源

- [系统架构与数据模型](../architecture/README.md) - 系统架构
- [插件详解](../plugins/README.md) - 内置插件说明
