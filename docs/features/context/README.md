# Context 功能

**导航**: [文档中心](../../README.md) > [功能特性](../README.md) > Context 功能

Context 相关的功能文档，包括依赖查询、血缘可视化、缓存诊断和配置管理。Context API、端到端执行工作流、
全局 ExecutorManager 与正式数据产物边界统一从[系统架构](../../architecture/ARCHITECTURE.md)进入。
公开方法精简与旧调用迁移见[配置管理](CONFIGURATION.md#context-api-迁移)。

## 文档列表

| 文档 | 说明 |
|------|------|
| [配置管理](CONFIGURATION.md) | 配置管理功能 |
| [分层缓存](LAYERED_CACHE.md) | 发布共享基础快照并使用私人缓存 |
| [Plugin DAG、lineage 与缓存](../../architecture/PLUGIN_DAG_LINEAGE_CACHE.md) | 依赖、缓存与诊断边界 |
| [数据产物与波形访问](../../architecture/DATA_PRODUCTS.md) | records-backed 波形构建边界 |
| [血缘可视化](LINEAGE_VISUALIZATION_GUIDE.md) | 血缘可视化功能使用指南 |
| [批处理器](BATCH_PROCESSOR.md) | 批处理器文档 |
