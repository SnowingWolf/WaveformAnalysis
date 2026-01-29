**导航**: [文档中心](../../README.md) > [功能特性](../README.md) > [Context 功能](README.md) > 依赖分析

---

# 依赖分析功能使用指南

本文档展示如何使用 WaveformAnalysis 的依赖分析功能。

## 功能概述

依赖分析功能可以帮助您：

- **理解数据流**：可视化插件之间的依赖关系
- **识别并行机会**：发现可以并行执行的插件
- **找到关键路径**：识别影响整体性能的瓶颈
- **性能分析**：基于实际执行数据分析性能
- **优化建议**：获得智能的优化建议

## 快速开始

### 基础分析（静态）

不需要性能数据也能进行基本的依赖分析：

```python
from waveform_analysis.core.context import Context

ctx = Context()
# ... 注册插件 ...

# 执行静态分析
analysis = ctx.analyze_dependencies(
    'paired_events',
    include_performance=False
)

print(analysis.summary())
```

输出示例：

```
=== 依赖分析摘要：paired_events ===
分析模式: 静态
总插件数: 7
DAG 深度: 6, 宽度: 2

关键路径 (6 个插件):
  raw_files → waveforms → st_waveforms → features → dataframe → paired_events

并行机会: 2 组
  理论加速比: 2.00x

优化建议: 3 条
```

### 性能分析（动态）

启用性能统计后，可以获得更详细的分析：

```python
# 启用性能统计
ctx = Context(
    stats_mode='detailed'  # 'off', 'basic' 或 'detailed'
)
# ... 注册插件并执行数据处理 ...

# 执行动态分析（包含性能数据）
analysis = ctx.analyze_dependencies('paired_events', include_performance=True)

print(analysis.summary())

# 查看瓶颈列表
for bottleneck in analysis.bottlenecks:
    print(f"  {bottleneck['severity']}: {bottleneck['plugin_name']}")
    print(f"    时间占比: {bottleneck['metrics']['time_percentage']:.1f}%")

# 查看优化建议
for i, rec in enumerate(analysis.recommendations, 1):
    print(f"  {i}. {rec}")
```

## 导出报告

### 导出为 Markdown

```python
analysis.to_markdown()  # 返回字符串
analysis.save_markdown('dependency_report.md')  # 保存到文件
```

### 导出为 JSON

```python
data = analysis.to_dict()  # 转换为字典
analysis.to_json('dependency_analysis.json', indent=2)  # 保存为 JSON
```

## 可视化增强

结合依赖图可视化，高亮显示分析结果：

```python
from waveform_analysis.utils.visualization import plot_lineage_labview

analysis = ctx.analyze_dependencies('paired_events')

plot_lineage_labview(
    lineage=ctx.get_lineage('paired_events'),
    target_name='paired_events',
    context=ctx,
    analysis_result=analysis,
    highlight_critical_path=True,   # 高亮关键路径（红色粗边框）
    highlight_bottlenecks=True,     # 高亮瓶颈节点（红/橙/黄背景）
    highlight_parallel_groups=True, # 标记并行组（彩色徽章）
    interactive=True
)
```

## 实际应用场景

### 场景 1：静态分析

```python
# 1. 静态分析快速理解
analysis = ctx.analyze_dependencies('final_output', include_performance=False)
print(analysis.summary())

# 2. 查看层次结构
for depth, plugins in analysis.layers.items():
    print(f"深度 {depth}: {', '.join(plugins)}")

# 3. 导出文档
analysis.save_markdown('project_architecture.md')
```

### 场景 2：性能调优

```python
# 1. 启用详细性能统计
ctx = Context(stats_mode='detailed')
# ... 执行数据处理 ...

# 分析瓶颈
analysis = ctx.analyze_dependencies('final_output')

# 按严重性处理瓶颈
for bottleneck in analysis.bottlenecks:
    if bottleneck['severity'] == 'high':
        plugin = bottleneck['plugin_name']
        issues = bottleneck['issues']

        if 'cache_miss' in issues:
            print(f"检查 {plugin} 的缓存配置")
        if 'execution_time' in issues:
            print(f"优化 {plugin} 的算法")

# 验证优化效果
# ... 应用优化措施 ...
analysis_after = ctx.analyze_dependencies('final_output')
print(f"优化前: {analysis.critical_path_time:.2f}s")
print(f"优化后: {analysis_after.critical_path_time:.2f}s")
```

### 场景 2：并行执行规划

```python
analysis = ctx.analyze_dependencies('final_output')

# 查看可并行插件
for i, group in enumerate(analysis.parallel_groups, 1):
    print(f"并行组 {i}: {', '.join(group)}")

# 估算加速比
print(f"理论加速比: {analysis.parallelization_potential:.2f}x")

# 配置并行执行
from waveform_analysis.core.execution import enable_global_load_balancing

enable_global_load_balancing(
    min_workers=1,
    max_workers=len(max(analysis.parallel_groups, key=len))
)
```

## API 参考

### Context.analyze_dependencies()

```python
def analyze_dependencies(
    self,
    target_name: str,
    include_performance: bool = True,
    run_id: Optional[str] = None
) -> DependencyAnalysisResult
```

参数：
- `target_name`: 目标数据名称
- `include_performance`: 是否包含性能数据（需要 `stats_mode='basic'` 或 `'detailed'`）
- `run_id`: 保留参数，当前未使用

### DependencyAnalysisResult 属性

| 属性 | 说明 |
|------|------|
| `target_name` | 目标名称 |
| `total_plugins` | 总插件数 |
| `execution_plan` | 执行计划（拓扑排序） |
| `max_depth` | DAG 最大深度 |
| `max_width` | DAG 最大宽度 |
| `layers` | 按深度分层的插件 |
| `critical_path` | 关键路径插件列表 |
| `critical_path_time` | 关键路径总时间（如有性能数据） |
| `parallel_groups` | 可并行执行的插件组 |
| `parallelization_potential` | 理论加速比 |
| `bottlenecks` | 性能瓶颈列表 |
| `recommendations` | 优化建议列表 |
| `has_performance_data` | 是否包含性能数据 |

### DependencyAnalysisResult 方法

| 方法 | 说明 |
|------|------|
| `summary()` | 生成简要文本摘要 |
| `to_dict()` | 转换为字典 |
| `to_json(filepath=None)` | 转换为 JSON |
| `to_markdown()` | 生成 Markdown 报告 |
| `save_markdown(filepath)` | 保存 Markdown 报告 |

## 常见问题

### Q: 如何启用性能统计？

在创建 Context 时设置 `stats_mode`：
```python
ctx = Context(stats_mode='detailed')
```

### Q: 静态分析和动态分析有什么区别？

- **静态分析**：仅基于依赖关系图，不需要实际执行数据
- **动态分析**：结合实际执行时间、缓存命中率、内存使用等性能数据

### Q: 瓶颈严重性如何判断？

基于多个维度综合评估：
- **High**: 时间占比 >20% 或在关键路径上且有其他问题
- **Medium**: 时间占比 10-20% 或缓存命中率低
- **Low**: 有潜在问题但影响较小

## 相关文档

- [架构文档](../../architecture/ARCHITECTURE.md)
- [缓存机制](DATA_ACCESS.md#缓存机制)
- [并行执行](../advanced/EXECUTOR_MANAGER_GUIDE.md)
