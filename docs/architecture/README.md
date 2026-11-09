# 系统架构与数据模型

**导航**: [文档中心](../README.md) > 系统架构与数据模型

理解 Plugin 如何运行、数据如何关联，以及单 run、多 run 与并行资源的处理边界。Context 的执行工作流、
ExecutorManager 和 Context API 已收敛到站点的 Context 单一入口（`/contexts/context/#execution-framework`）。

## 文档列表

| 文档 | 说明 |
|------|------|
| [系统架构与数据流](ARCHITECTURE.md) | 默认数据流与各层职责 |
| [插件执行链与缓存](PLUGIN_DAG_LINEAGE_CACHE.md) | 从依赖解析到缓存复用的主线 |
| [插件缓存架构](PLUGIN_CACHE_ARCHITECTURE.md) | 缓存分层、键与身份、命中/写盘/失效路径 |
| [数据产物与波形访问](DATA_PRODUCTS.md) | 正式产物契约、实体关系、派生聚合与 records/pool 波形访问 |
| [分析查询与批量运行](ACCESSOR_ANALYSIS.md) | 处理完成后的只读查询，以及多 run 调度与执行边界 |
| [项目结构](PROJECT_STRUCTURE.md) | 代码、文档、示例和质量检查的目录边界 |
