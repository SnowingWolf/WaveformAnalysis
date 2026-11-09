# 依赖分析退役迁移

本页保留旧文档地址，说明已删除接口的迁移方式。`Context.analyze_dependencies()`、
`DependencyAnalyzer` 及其分析结果类型已退役；自动关键路径、理论并行潜力、瓶颈建议和分析结果高亮
不再属于公开功能。实际 DAG 调度与依赖解析仍保留。

## 当前入口

| 目的 | 当前入口 | 边界 |
| --- | --- | --- |
| 查看上游拓扑顺序 | `ctx.resolve_dependencies(target, run_id=run_id)` | 不报告本次缓存命中或重算范围 |
| 检查配置和版本组成的缓存身份 | `ctx.get_lineage(target)` | 不验证磁盘缓存完整性 |
| 查看普通依赖图 | `ctx.plot_lineage(target)` | 不接收分析结果或高级高亮参数 |
| 查看实际插件耗时、缓存命中率与失败 | `ctx.get_performance_report()` | 需要提前启用统计并实际执行 |
| 检查缓存问题 | `ctx.diagnose_cache(run_id)` | 只检查；修复使用缓存 CLI |

```python
# ctx 已注册插件；这些查询不会计算目标产物
order = ctx.resolve_dependencies("peaks", run_id="run_001")
lineage = ctx.get_lineage("peaks")
ctx.plot_lineage("peaks", kind="mermaid")
```

`preview_execution()` 同时退役，以上查询不能等价替代执行前的缓存命中和重算步骤预览。
实际运行的耗时可以用于人工定位慢插件，不再自动推导理论加速比或瓶颈建议。

## 相关文档

- [配置与诊断 API 迁移](CONFIGURATION.md#context-api-迁移)
- [血缘可视化](LINEAGE_VISUALIZATION_GUIDE.md)
- [Plugin DAG、lineage 与缓存](../../architecture/PLUGIN_DAG_LINEAGE_CACHE.md)
- [缓存 CLI](../../cli/WAVEFORM_CACHE.md)
