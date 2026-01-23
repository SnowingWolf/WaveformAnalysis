**导航**: [文档中心](../../README.md) > [功能特性](../README.md) > [Context 功能](README.md) > 依赖分析

---

# 依赖分析功能使用指南

本文档展示如何使用 WaveformAnalysis 的依赖分析功能。

---

## 📖 功能概述

依赖分析功能可以帮助您：
- 🔍 **理解数据流**：可视化插件之间的依赖关系
- ⚡ **识别并行机会**：发现可以并行执行的插件
- 🎯 **找到关键路径**：识别影响整体性能的瓶颈
- 📊 **性能分析**：基于实际执行数据分析性能
- 💡 **优化建议**：获得智能的优化建议

## 🚀 快速开始

### 1. 基础分析（静态）

不需要性能数据也能进行基本的依赖分析：

```python
from waveform_analysis.core.context import Context

# 创建 Context 并注册插件
ctx = Context()
# ... 注册插件 ...

# 执行静态分析
analysis = ctx.analyze_dependencies(
    'paired_events',
    include_performance=False  # 不使用性能数据
)

# 查看简要摘要
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
  首要建议: ⚡ 并行机会 #1：peaks, charges 可以并行执行，预计加速 2.0x
```

### 2. 性能分析（动态）

启用性能统计后，可以获得更详细的分析：

```python
from waveform_analysis.core.context import Context

# 启用性能统计
ctx = Context(
    enable_stats=True,
    stats_mode='detailed'  # 'basic' 或 'detailed'
)
# ... 注册插件并执行数据处理 ...

# 执行动态分析（包含性能数据）
analysis = ctx.analyze_dependencies(
    'paired_events',
    include_performance=True
)

# 查看详细摘要
print(analysis.summary())

# 查看瓶颈列表
print("\n性能瓶颈:")
for bottleneck in analysis.bottlenecks:
    print(f"  {bottleneck['severity']}: {bottleneck['plugin_name']}")
    print(f"    问题: {', '.join(bottleneck['issues'])}")
    print(f"    时间占比: {bottleneck['metrics']['time_percentage']:.1f}%")

# 查看所有优化建议
print("\n优化建议:")
for i, rec in enumerate(analysis.recommendations, 1):
    print(f"  {i}. {rec}")
```

输出示例：
```
=== 依赖分析摘要：paired_events ===
分析模式: 动态（含性能数据）
总插件数: 7
DAG 深度: 6, 宽度: 2

关键路径 (4 个插件):
  waveforms → grouped_events → st_waveforms → features
  总耗时: 15.23s

并行机会: 2 组
  理论加速比: 1.85x

性能瓶颈: 2 个
  高严重性: 1 个

优化建议: 5 条
  首要建议: 🎯 关键路径优化：重点关注 waveforms, grouped_events, st_waveforms（总耗时 15.23s）

性能瓶颈:
  high: waveforms
    问题: execution_time, cache_miss, critical_path
    时间占比: 55.8%
  medium: grouped_events
    问题: execution_time, critical_path
    时间占比: 21.0%

优化建议:
  1. 🎯 关键路径优化：重点关注 waveforms, grouped_events, st_waveforms（总耗时 15.23s），它们决定了整体执行时间
  2. ⚡ 并行机会 #1：peaks, charges 可以并行执行，预计加速 2.0x
  3. 🔴 瓶颈 #1: waveforms 占总执行时间 55.8%，建议优化算法或启用缓存
  4. 💾 缓存优化: waveforms 缓存命中率仅 15.0%，检查缓存失效原因
  5. 🟡 瓶颈 #2: grouped_events 占总执行时间 21.0%，建议优化算法或启用缓存
```

## 📊 导出报告

### 导出为 Markdown

```python
# 生成 Markdown 报告
analysis.to_markdown()  # 返回字符串

# 或者直接保存到文件
analysis.save_markdown('dependency_report.md')
```

生成的 Markdown 报告包含：
- 📊 概览信息
- 🏗️ 层次结构
- 🎯 关键路径详情
- ⚡ 并行机会列表
- 🔴 性能瓶颈分析
- 💡 优化建议

### 导出为 JSON

```python
# 转换为字典（可保存为 JSON）
data = analysis.to_dict()

# 或者直接保存为 JSON 文件
analysis.to_json('dependency_analysis.json', indent=2)
```

JSON 格式适合：
- 程序化处理
- 集成到CI/CD流程
- 性能趋势追踪
- 自动化报告生成

## 🎨 可视化增强

结合依赖图可视化，高亮显示分析结果：

```python
from waveform_analysis.utils.visualization import plot_lineage_labview

# 执行分析
analysis = ctx.analyze_dependencies('paired_events')

# 可视化并高亮关键路径和瓶颈
plot_lineage_labview(
    lineage=ctx.get_lineage('paired_events'),
    target_name='paired_events',
    context=ctx,
    analysis_result=analysis,  # 传入分析结果
    highlight_critical_path=True,  # 高亮关键路径（红色粗边框）
    highlight_bottlenecks=True,    # 高亮瓶颈节点（红/橙/黄背景）
    highlight_parallel_groups=True, # 标记并行组（彩色徽章）
    interactive=True  # 启用交互式功能
)
```

可视化特性：
- 🔴 **关键路径**：红色粗边框
- 🟥 **高严重性瓶颈**：红色背景 + 红色边框
- 🟧 **中严重性瓶颈**：橙色背景 + 橙色边框
- 🟨 **低严重性瓶颈**：黄色背景
- 🎨 **并行组**：右上角带颜色徽章（P1, P2, ...）
- 🖱️ **交互式**：鼠标悬停显示详细信息

## 💼 实际应用场景

### 场景 1：新项目理解数据流

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
ctx = Context(enable_stats=True, stats_mode='detailed')
# ... 执行数据处理 ...

# 2. 分析瓶颈
analysis = ctx.analyze_dependencies('final_output')

# 3. 按严重性处理瓶颈
for bottleneck in analysis.bottlenecks:
    if bottleneck['severity'] == 'high':
        plugin = bottleneck['plugin_name']
        issues = bottleneck['issues']

        if 'cache_miss' in issues:
            print(f"检查 {plugin} 的缓存配置")
        if 'memory' in issues:
            print(f"优化 {plugin} 的内存使用")
        if 'execution_time' in issues:
            print(f"优化 {plugin} 的算法")

# 4. 验证优化效果
# ... 应用优化措施 ...
analysis_after = ctx.analyze_dependencies('final_output')
print(f"优化前: {analysis.critical_path_time:.2f}s")
print(f"优化后: {analysis_after.critical_path_time:.2f}s")
```

### 场景 3：并行执行规划

```python
# 1. 识别并行机会
analysis = ctx.analyze_dependencies('final_output')

# 2. 查看可并行插件
for i, group in enumerate(analysis.parallel_groups, 1):
    print(f"\n并行组 {i}:")
    print(f"  插件: {', '.join(group)}")
    print(f"  插件数: {len(group)}")

# 3. 估算加速比
print(f"\n理论加速比: {analysis.parallelization_potential:.2f}x")

# 4. 配置并行执行
from waveform_analysis.core.execution import enable_global_load_balancing

enable_global_load_balancing(
    min_workers=1,
    max_workers=len(max(analysis.parallel_groups, key=len))  # 根据最大并行组设置
)
```

### 场景 4：CI/CD 集成

```python
import json

# 在 CI/CD 流程中自动分析
analysis = ctx.analyze_dependencies('final_output')

# 导出 JSON 用于趋势追踪
data = analysis.to_dict()
data['commit_sha'] = os.getenv('CI_COMMIT_SHA')
data['timestamp'] = datetime.now().isoformat()

with open(f'performance_{data["commit_sha"][:8]}.json', 'w') as f:
    json.dump(data, f, indent=2)

# 检查是否有高严重性瓶颈（失败构建）
high_bottlenecks = [b for b in analysis.bottlenecks if b['severity'] == 'high']
if len(high_bottlenecks) > 3:
    print(f"❌ 发现 {len(high_bottlenecks)} 个高严重性瓶颈，请优化！")
    exit(1)
```

## 🔧 高级用法

### 自定义分析逻辑

```python
# 获取原始分析数据
analysis = ctx.analyze_dependencies('target')

# 自定义过滤瓶颈
cache_issues = [
    b for b in analysis.bottlenecks
    if 'cache_miss' in b['issues'] and b['metrics']['cache_hit_rate'] < 0.2
]

memory_issues = [
    b for b in analysis.bottlenecks
    if 'memory' in b['issues'] and b['metrics']['peak_memory_mb'] > 2048
]

# 生成自定义报告
print("缓存问题:")
for issue in cache_issues:
    print(f"  {issue['plugin_name']}: {issue['metrics']['cache_hit_rate']:.1%}")

print("\n内存问题:")
for issue in memory_issues:
    print(f"  {issue['plugin_name']}: {issue['metrics']['peak_memory_mb']:.1f}MB")
```

### 批量分析多个目标

```python
targets = ['st_waveforms', 'features', 'dataframe', 'paired_events']

for target in targets:
    print(f"\n{'='*60}")
    print(f"分析目标: {target}")
    print('='*60)

    analysis = ctx.analyze_dependencies(target)
    print(analysis.summary())

    # 保存报告
    analysis.save_markdown(f'report_{target}.md')
```

## 📚 参考

### API 文档

**Context.analyze_dependencies()**
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
- `include_performance`: 是否包含性能数据（需要 `enable_stats=True`）
- `run_id`: 保留参数，当前未使用

返回：`DependencyAnalysisResult` 对象

**DependencyAnalysisResult 属性**
- `target_name`: 目标名称
- `total_plugins`: 总插件数
- `execution_plan`: 执行计划（拓扑排序）
- `max_depth`: DAG 最大深度
- `max_width`: DAG 最大宽度
- `layers`: 按深度分层的插件
- `critical_path`: 关键路径插件列表
- `critical_path_time`: 关键路径总时间（如有性能数据）
- `parallel_groups`: 可并行执行的插件组
- `parallelization_potential`: 理论加速比
- `bottlenecks`: 性能瓶颈列表
- `recommendations`: 优化建议列表
- `has_performance_data`: 是否包含性能数据

**DependencyAnalysisResult 方法**
- `summary()`: 生成简要文本摘要
- `to_dict()`: 转换为字典
- `to_json(filepath=None)`: 转换为 JSON
- `to_markdown()`: 生成 Markdown 报告
- `save_markdown(filepath)`: 保存 Markdown 报告

### 相关文档

- [ARCHITECTURE.md](../../architecture/ARCHITECTURE.md) - 整体架构
- [缓存机制](DATA_ACCESS.md#缓存机制) - 缓存机制
- [EXECUTOR_MANAGER_GUIDE.md](../advanced/EXECUTOR_MANAGER_GUIDE.md) - 并行执行

## ❓ 常见问题

### Q: 如何启用性能统计？

A: 在创建 Context 时设置 `enable_stats=True`：
```python
ctx = Context(enable_stats=True, stats_mode='detailed')
```

### Q: 静态分析和动态分析有什么区别？

A:
- **静态分析**：仅基于依赖关系图，不需要实际执行数据
- **动态分析**：结合实际执行时间、缓存命中率、内存使用等性能数据

### Q: 如何理解加速比？

A: 加速比 = 顺序执行时间 / 并行执行时间。例如：
- 加速比 2.0x 表示理论上可以快一倍
- 实际加速比通常小于理论值（受并行开销、资源限制等影响）

### Q: 瓶颈严重性如何判断？

A: 基于多个维度综合评估：
- **High**: 时间占比 >20% 或在关键路径上且有其他问题
- **Medium**: 时间占比 10-20% 或缓存命中率低
- **Low**: 有潜在问题但影响较小

### Q: 如何导出完整的性能报告？

A: 结合使用：
```python
# 1. 依赖分析报告
analysis = ctx.analyze_dependencies('target')
analysis.save_markdown('dependency_report.md')

# 2. 性能统计报告
with open('performance_stats.txt', 'w') as f:
    f.write(ctx.get_performance_report())
```

## 🎉 总结

依赖分析功能帮助您：
1. ✅ 快速理解复杂的数据流和依赖关系
2. ✅ 识别性能瓶颈和优化机会
3. ✅ 获得可执行的优化建议
4. ✅ 通过可视化直观展示分析结果
5. ✅ 导出报告用于文档和趋势追踪

Happy analyzing! 🚀
