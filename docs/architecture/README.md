# 系统架构与数据模型

**导航**: [文档中心](../README.md) > 系统架构与数据模型

理解 Plugin 如何运行、数据如何关联，以及单 run 与多 run 的处理边界。

## 文档列表

| 文档 | 说明 |
|------|------|
| [系统总览：组件、边界与数据流](ARCHITECTURE.md) | 默认数据流与各层职责 |
| [插件执行链：DAG、动态依赖、Lineage 与缓存](PLUGIN_DAG_LINEAGE_CACHE.md) | 从依赖解析到缓存复用的主线 |
| [数据产物：实体关系与派生结果](DATA_PRODUCTS.md) | 唯一具名产物、实体关系与派生聚合 |
| [波形数据：records 与 Wave Pool 的配对访问](RECORDS_WAVE_POOL.md) | 结构化索引与对应波形池的访问边界 |
| [分析查询：Accessor 与只读数据访问](ACCESSOR_ANALYSIS.md) | 处理完成后的查询与组合职责 |
| [批量运行：多 Run 调度与执行（开发中）](MULTI_RUN_PROCESSING.md) | 当前批处理能力、隔离、调度与尚未稳定的边界 |

## 学习路径

1. [系统总览：组件、边界与数据流](ARCHITECTURE.md) - 了解默认数据流与层次边界
2. [插件执行链：DAG、动态依赖、Lineage 与缓存](PLUGIN_DAG_LINEAGE_CACHE.md) - 理解处理如何执行和复用
3. [数据产物：实体关系与派生结果](DATA_PRODUCTS.md) - 理解正式输出与 ID 关系
4. [波形数据：records 与 Wave Pool 的配对访问](RECORDS_WAVE_POOL.md) - 理解不同数据如何使用对应的索引产物和 pool
5. [分析查询：Accessor 与只读数据访问](ACCESSOR_ANALYSIS.md) - 理解分析阶段的只读接口
6. [批量运行：多 Run 调度与执行（开发中）](MULTI_RUN_PROCESSING.md) - 区分当前能力与仍在演进的批量边界

## 相关资源

- [API 参考](../api/README.md) - 查看具体 API
- [功能特性](../features/README.md) - 了解功能实现
- [开发指南](../development/README.md) - 贡献代码
