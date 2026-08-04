# 系统架构与数据模型

**导航**: [文档中心](../README.md) > 系统架构与数据模型

理解 Plugin 如何运行、数据如何关联，以及单 run 与多 run 的处理边界。

## 文档列表

| 文档 | 说明 |
|------|------|
| [系统架构与数据流](ARCHITECTURE.md) | 默认数据流与各层职责 |
| [插件执行链与缓存](PLUGIN_DAG_LINEAGE_CACHE.md) | 从依赖解析到缓存复用的主线 |
| [插件缓存架构](PLUGIN_CACHE_ARCHITECTURE.md) | 缓存分层、键与身份、命中/写盘/失效路径 |
| [数据产物与波形访问](DATA_PRODUCTS.md) | 正式产物契约、实体关系、派生聚合与 records/pool 波形访问 |
| [分析查询与批量运行](ACCESSOR_ANALYSIS.md) | 处理完成后的只读查询，以及多 run 调度与执行边界 |

## 学习路径

1. [系统架构与数据流](ARCHITECTURE.md) - 了解默认数据流与层次边界
2. [插件执行链与缓存](PLUGIN_DAG_LINEAGE_CACHE.md) - 理解处理如何执行和复用
3. [插件缓存架构](PLUGIN_CACHE_ARCHITECTURE.md) - 理解缓存分层与命中/失效路径
4. [数据产物与波形访问](DATA_PRODUCTS.md) - 理解正式输出、ID 关系与波形配对
5. [分析查询与批量运行](ACCESSOR_ANALYSIS.md) - 理解分析阶段的只读接口与批量边界

## 相关资源

- [API 参考](../api/README.md) - 查看具体 API
- [功能特性](../features/README.md) - 了解功能实现
- [开发指南](../development/README.md) - 贡献代码
