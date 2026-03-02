**导航**: [文档中心](../../README.md) > [功能特性](../README.md) > [Context 功能](README.md) > 依赖分析与执行预览的关系

---

# 依赖分析与执行预览的关系

> **适合人群**: 数据分析用户、开发者

本文档详细说明依赖分析（`analyze_dependencies`）和执行预览（`preview_execution`）之间的关系、区别和如何结合使用。

---

## 📋 目录

1. [功能对比](#功能对比)
2. [核心区别](#核心区别)
3. [使用场景](#使用场景)
4. [如何结合使用](#如何结合使用)
5. [完整工作流示例](#完整工作流示例)
6. [选择指南](#选择指南)

---

## 功能对比

### 依赖分析 (`analyze_dependencies`)

**核心功能**：
- 🔍 分析插件依赖关系结构
- ⚡ 识别并行执行机会
- 🎯 找到关键路径
- 📊 性能瓶颈分析（需要性能数据）
- 💡 生成优化建议

**输出**：
- 分析报告对象（`DependencyAnalysisResult`）
- 可导出为 Markdown、JSON
- 可结合可视化高亮显示

**使用时机**：
- 性能优化前
- 理解复杂数据流
- 规划并行执行策略
- 生成性能报告

### 执行预览 (`preview_execution`)

**核心功能**：
- 📋 预览执行计划（哪些插件会被执行）
- ⚙️ 查看配置参数
- 🌳 显示依赖关系树
- 💾 确认缓存状态（哪些已缓存，哪些需要计算）

**输出**：
- 文本输出（可读性强）
- 字典数据（可程序化使用）

**使用时机**：
- 执行前确认
- 调试配置问题
- 检查缓存状态
- 学习依赖关系

---

## 核心区别

### 1. 关注点不同

| 维度 | 依赖分析 | 执行预览 |
|------|---------|---------|
| **主要关注** | 结构分析和性能优化 | 执行前确认和配置检查 |
| **时间维度** | 执行后分析（可静态/动态） | 执行前预览 |
| **数据来源** | 依赖图 + 可选性能数据 | 依赖图 + 缓存状态 + 配置 |
| **输出重点** | 分析结果和建议 | 执行计划和状态 |

### 2. 信息维度不同

**依赖分析提供**：
- ✅ 关键路径（影响总执行时间的路径）
- ✅ 并行组（可以并行执行的插件）
- ✅ 瓶颈节点（性能问题）
- ✅ 优化建议（可执行的建议）
- ✅ 理论加速比

**执行预览提供**：
- ✅ 执行顺序（拓扑排序的插件列表）
- ✅ 缓存状态（内存/磁盘/需计算）
- ✅ 配置参数（非默认配置）
- ✅ 依赖树（树状结构）

### 3. 使用场景不同

**依赖分析适合**：
- 性能调优
- 架构理解
- 并行规划
- 报告生成

**执行预览适合**：
- 执行前确认
- 配置调试
- 缓存检查
- 快速了解

---

## 使用场景

### 场景 1: 新项目理解

**第一步：执行预览（快速了解）**

```python
# 快速预览，了解执行计划
ctx.preview_execution('run_001', 'df_paired')
```

**第二步：依赖分析（深入理解）**

```python
# 深入分析，理解结构和性能
analysis = ctx.analyze_dependencies('df_paired', include_performance=False)
print(analysis.summary())
```

**第三步：可视化（直观展示）**

```python
# 可视化血缘图
ctx.plot_lineage('df_paired', kind='plotly', verbose=2)
```

### 场景 2: 性能优化

**第一步：执行并收集性能数据**

```python
# 启用性能统计
ctx = Context(stats_mode='detailed')

# 执行数据处理
data = ctx.get_data('run_001', 'df_paired')
```

**第二步：依赖分析（找出瓶颈）**

```python
# 分析性能瓶颈
analysis = ctx.analyze_dependencies('df_paired', include_performance=True)

# 查看瓶颈
for bottleneck in analysis.bottlenecks:
    if bottleneck['severity'] == 'high':
        print(f"高严重性瓶颈: {bottleneck['plugin_name']}")
        print(f"  时间占比: {bottleneck['metrics']['time_percentage']:.1f}%")
```

**第三步：可视化高亮（直观展示）**

```python
# 可视化并高亮瓶颈
ctx.plot_lineage(
    'df_paired',
    kind='plotly',
    analysis_result=analysis,
    highlight_critical_path=True,
    highlight_bottlenecks=True
)
```

### 场景 3: 配置调试

**第一步：预览配置**

```python
# 预览执行计划和配置
result = ctx.preview_execution('run_001', 'signal_peaks', show_config=True)

# 检查配置是否正确
for plugin, config in result['configs'].items():
    print(f"{plugin}: {config}")
```

**第二步：修正配置**

```python
# 发现配置错误，修正
ctx.set_config({"filter_type": "BW"}, plugin_name="filtered_waveforms")

# 再次预览确认
ctx.preview_execution('run_001', 'signal_peaks')
```

### 场景 4: 缓存优化

**第一步：检查缓存状态**

```python
# 预览缓存状态
result = ctx.preview_execution('run_001', 'df_paired', show_cache=True)

# 统计缓存情况
cached = sum(1 for s in result['cache_status'].values() if s['on_disk'] or s['in_memory'])
needs_compute = sum(1 for s in result['cache_status'].values() if s['needs_compute'])

print(f"已缓存: {cached} 个，需计算: {needs_compute} 个")

# 可选：查看剪枝与实际执行步骤
pruned = [p for p, s in result['cache_status'].items() if s.get('pruned')]
print(f"缓存剪枝: {len(pruned)} 个")
print(f"实际执行步骤: {len(result['needed_set'])} 个")
```

**第二步：依赖分析（找出缓存问题）**

```python
# 如果缓存命中率低，进行依赖分析
analysis = ctx.analyze_dependencies('df_paired', include_performance=True)

# 查找缓存相关的瓶颈
cache_bottlenecks = [
    b for b in analysis.bottlenecks
    if 'cache_miss' in b['issues']
]

for bottleneck in cache_bottlenecks:
    print(f"缓存问题: {bottleneck['plugin_name']}")
    print(f"  命中率: {bottleneck['metrics'].get('cache_hit_rate', 0):.1%}")
```

---

## 如何结合使用

### 工作流 1: 预览 → 分析 → 优化

```python
# 1. 预览执行计划
print("=== 步骤 1: 预览执行计划 ===")
preview = ctx.preview_execution('run_001', 'df_paired')
print(f"需要计算的插件: {sum(1 for s in preview['cache_status'].values() if s['needs_compute'])} 个")

# 2. 执行并收集性能数据
print("\n=== 步骤 2: 执行数据处理 ===")
data = ctx.get_data('run_001', 'df_paired')

# 3. 依赖分析
print("\n=== 步骤 3: 依赖分析 ===")
analysis = ctx.analyze_dependencies('df_paired', include_performance=True)
print(analysis.summary())

# 4. 可视化
print("\n=== 步骤 4: 可视化 ===")
ctx.plot_lineage(
    'df_paired',
    kind='plotly',
    analysis_result=analysis,
    highlight_critical_path=True,
    highlight_bottlenecks=True
)

# 5. 应用优化建议
print("\n=== 步骤 5: 应用优化 ===")
for rec in analysis.recommendations[:3]:  # 前3条建议
    print(f"  • {rec}")
```




### 工作流 3: 预览 → 确认 → 分析 → 优化

```python
# 1. 预览（确认配置和缓存）
preview = ctx.preview_execution('run_001', 'df_paired', verbose=2)

# 2. 用户确认
user_input = input("\n是否继续执行? (y/n): ").strip().lower()
if user_input != 'y':
    print("取消执行")
    exit(0)

# 3. 执行
data = ctx.get_data('run_001', 'df_paired')

# 4. 分析性能
analysis = ctx.analyze_dependencies('df_paired', include_performance=True)

# 5. 导出报告
analysis.save_markdown('performance_report.md')
print("性能报告已保存")
```

---

## 完整示例

### 示例 1: 完整的优化工作流

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins import *

# 创建 Context（启用性能统计）
ctx = Context(
    storage_dir="./cache",
    stats_mode='detailed'
)

# 注册插件
ctx.register(
    RawFilesPlugin(),
    WaveformsPlugin(),
    BasicFeaturesPlugin(),
    DataFramePlugin(),
    GroupedEventsPlugin(),
    PairedEventsPlugin(),
)

run_name = "my_run"

# === 阶段 1: 预览阶段 ===
print("=" * 60)
print("阶段 1: 执行前预览")
print("=" * 60)

preview = ctx.preview_execution(run_name, 'df_paired', verbose=2)

# 检查缓存状态
needs_compute = sum(1 for s in preview['cache_status'].values() if s['needs_compute'])
print(f"\n需要计算的插件: {needs_compute} 个")

# === 阶段 2: 执行阶段 ===
print("\n" + "=" * 60)
print("阶段 2: 执行数据处理")
print("=" * 60)

data = ctx.get_data(run_name, 'df_paired')
print(f"✓ 数据获取完成，共 {len(data)} 条记录")

# === 阶段 3: 分析阶段 ===
print("\n" + "=" * 60)
print("阶段 3: 依赖分析")
print("=" * 60)

analysis = ctx.analyze_dependencies('df_paired', include_performance=True)
print(analysis.summary())

# 查看瓶颈
print("\n性能瓶颈:")
for bottleneck in analysis.bottlenecks:
    print(f"  {bottleneck['severity']}: {bottleneck['plugin_name']}")
    print(f"    时间占比: {bottleneck['metrics']['time_percentage']:.1f}%")

# === 阶段 4: 可视化阶段 ===
print("\n" + "=" * 60)
print("阶段 4: 可视化")
print("=" * 60)

ctx.plot_lineage(
    'df_paired',
    kind='plotly',
    verbose=2,
    analysis_result=analysis,
    highlight_critical_path=True,
    highlight_bottlenecks=True,
    highlight_parallel_groups=True
)

# === 阶段 5: 优化阶段 ===
print("\n" + "=" * 60)
print("阶段 5: 优化建议")
print("=" * 60)

print("\n优化建议:")
for i, rec in enumerate(analysis.recommendations, 1):
    print(f"  {i}. {rec}")

# 导出报告
analysis.save_markdown('optimization_report.md')
print("\n✓ 优化报告已保存到 optimization_report.md")
```

### 示例 2: 配置调试工作流

```python
# 1. 预览配置
print("=== 当前配置预览 ===")
preview1 = ctx.preview_execution('run_001', 'signal_peaks', show_config=True)

# 2. 发现配置问题，修正
print("\n=== 修正配置 ===")
ctx.set_config({"filter_type": "BW", "lowcut": 0.1, "highcut": 0.5},
               plugin_name="filtered_waveforms")

# 3. 再次预览确认
print("\n=== 修正后配置预览 ===")
preview2 = ctx.preview_execution('run_001', 'signal_peaks', show_config=True)

# 4. 对比配置变化
print("\n=== 配置对比 ===")
for plugin in preview2['configs']:
    if plugin in preview1['configs']:
        old_config = preview1['configs'][plugin]
        new_config = preview2['configs'][plugin]
        if old_config != new_config:
            print(f"{plugin} 配置已更新")
```

### 示例 3: 缓存优化工作流

```python
# 1. 首次执行前预览
print("=== 首次执行前 ===")
preview1 = ctx.preview_execution('run_001', 'df_paired')
needs_compute_1 = sum(1 for s in preview1['cache_status'].values() if s['needs_compute'])
print(f"需要计算: {needs_compute_1} 个插件")

# 2. 执行
data = ctx.get_data('run_001', 'df_paired')

# 3. 第二次预览（检查缓存）
print("\n=== 第二次执行前 ===")
preview2 = ctx.preview_execution('run_001', 'df_paired')
needs_compute_2 = sum(1 for s in preview2['cache_status'].values() if s['needs_compute'])
print(f"需要计算: {needs_compute_2} 个插件")
print(f"缓存效果: {needs_compute_1 - needs_compute_2} 个插件已缓存")

# 4. 如果缓存效果不佳，进行依赖分析
if needs_compute_2 > needs_compute_1 * 0.5:
    print("\n=== 缓存问题分析 ===")
    analysis = ctx.analyze_dependencies('df_paired', include_performance=True)

    cache_issues = [
        b for b in analysis.bottlenecks
        if 'cache_miss' in b['issues']
    ]

    if cache_issues:
        print("发现缓存问题:")
        for issue in cache_issues:
            print(f"  {issue['plugin_name']}: 命中率 {issue['metrics'].get('cache_hit_rate', 0):.1%}")
```

---

## 选择指南

### 什么时候用执行预览？

✅ **适合使用 `preview_execution` 的场景**：

1. **执行前确认**
   - 想快速了解将要执行什么
   - 需要确认配置是否正确
   - 想检查缓存状态

2. **配置调试**
   - 发现配置错误
   - 验证配置修改效果

3. **学习依赖关系**
   - 新用户理解数据流
   - 查看依赖树结构

4. **批处理前检查**
   - 批量处理前先预览一个

### 什么时候用依赖分析？

✅ **适合使用 `analyze_dependencies` 的场景**：

1. **性能优化**
   - 找出性能瓶颈
   - 识别优化机会
   - 规划并行执行

2. **架构理解**
   - 理解复杂数据流
   - 识别关键路径
   - 分析并行机会

3. **报告生成**
   - 生成性能报告
   - 导出分析结果
   - CI/CD 集成

4. **可视化增强**
   - 高亮关键路径
   - 标记瓶颈节点
   - 显示并行组

### 什么时候结合使用？

✅ **建议结合使用的场景**：

1. **完整工作流**
   ```
   预览 → 执行 → 分析 → 优化
   ```

2. **性能调优流程**
   ```
   分析 → 预览 → 执行 → 再分析 → 对比
   ```

3. **配置调试流程**
   ```
   预览 → 修正 → 预览 → 分析 → 执行
   ```

---

## 功能互补性

### 信息互补

| 信息类型 | 执行预览 | 依赖分析 |
|---------|---------|---------|
| 执行顺序 | ✅ | ✅ |
| 缓存状态 | ✅ | ❌ |
| 配置参数 | ✅ | ❌ |
| 关键路径 | ❌ | ✅ |
| 并行机会 | ❌ | ✅ |
| 性能瓶颈 | ❌ | ✅ |
| 优化建议 | ❌ | ✅ |
| 依赖树 | ✅ | ❌ |

### 使用互补

- **执行预览**：快速、轻量，适合日常使用
- **依赖分析**：深入、全面，适合优化和报告

### 时间互补

- **执行预览**：执行前使用
- **依赖分析**：执行后使用（或静态分析）

---

## 完整工作流示例

### 典型工作流：从预览到优化

```python
from waveform_analysis.core.context import Context

# 创建 Context
ctx = Context(
    storage_dir="./cache",
    stats_mode='detailed'
)

# 注册插件...
# ... (注册代码) ...

run_name = "my_run"
target = "df_paired"

# === 1. 预览阶段 ===
print("📋 步骤 1: 预览执行计划")
preview = ctx.preview_execution(run_name, target, verbose=1)

# 检查是否需要大量计算
needs_compute = sum(1 for s in preview['cache_status'].values() if s['needs_compute'])
if needs_compute > 5:
    print(f"⚠️ 需要计算 {needs_compute} 个插件，可能需要较长时间")
    user_input = input("是否继续? (y/n): ")
    if user_input != 'y':
        exit(0)

# === 2. 执行阶段 ===
print("\n⚙️ 步骤 2: 执行数据处理")
data = ctx.get_data(run_name, target)
print(f"✓ 完成，共 {len(data))} 条记录")

# === 3. 分析阶段 ===
print("\n🔍 步骤 3: 依赖分析")
analysis = ctx.analyze_dependencies(target, include_performance=True)

# 查看关键信息
print(f"关键路径: {' → '.join(analysis.critical_path)}")
print(f"关键路径时间: {analysis.critical_path_time:.2f}s")
print(f"并行机会: {len(analysis.parallel_groups)} 组")

# === 4. 可视化阶段 ===
print("\n📊 步骤 4: 可视化")
ctx.plot_lineage(
    target,
    kind='plotly',
    verbose=2,
    analysis_result=analysis,
    highlight_critical_path=True,
    highlight_bottlenecks=True,
    highlight_parallel_groups=True
)

# === 5. 优化阶段 ===
print("\n💡 步骤 5: 优化建议")
for i, rec in enumerate(analysis.recommendations, 1):
    print(f"  {i}. {rec}")

# 导出报告
analysis.save_markdown('analysis_report.md')
print("\n✓ 分析报告已保存")
```

---

## 方法对比表

| 方法 | 用途 | 执行计算 | 输出格式 | 使用时机 |
|------|------|---------|---------|---------|
| `preview_execution()` | 预览执行计划和配置 | ❌ | 文本 + 字典 | 执行前 |
| `analyze_dependencies()` | 依赖分析（结构+性能） | ❌ | 分析报告对象 | 执行后/静态 |
| `get_lineage()` | 获取血缘信息 | ❌ | 字典 | 任何时候 |
| `plot_lineage()` | 可视化血缘图 | ❌ | 图形 | 任何时候 |
| `resolve_dependencies()` | 获取执行顺序 | ❌ | 列表 | 程序化使用 |
| `get_data()` | 获取数据 | ✅ | 数据 | 需要数据时 |

---

## 最佳实践

### 1. 日常使用流程

```python
# 快速预览 → 执行
preview = ctx.preview_execution(run_id, target)
data = ctx.get_data(run_id, target)
```

### 2. 性能优化流程

```python
# 执行 → 分析 → 优化
data = ctx.get_data(run_id, target)
analysis = ctx.analyze_dependencies(target, include_performance=True)
# 应用优化建议...
```

### 3. 配置调试流程

```python
# 预览 → 修正 → 预览 → 执行
ctx.preview_execution(run_id, target, show_config=True)
# 修正配置...
ctx.preview_execution(run_id, target, show_config=True)
data = ctx.get_data(run_id, target)
```

### 4. 完整分析流程

```python
# 预览 → 执行 → 分析 → 可视化 → 报告
preview = ctx.preview_execution(run_id, target)
data = ctx.get_data(run_id, target)
analysis = ctx.analyze_dependencies(target, include_performance=True)
ctx.plot_lineage(target, analysis_result=analysis, ...)
analysis.save_markdown('report.md')
```

---

## 常见问题

### Q1: 两个功能可以同时使用吗？

**A**: 可以，而且建议结合使用。它们关注不同的方面，互补性强。

```python
# 先预览
preview = ctx.preview_execution(run_id, target)

# 再执行
data = ctx.get_data(run_id, target)

# 最后分析
analysis = ctx.analyze_dependencies(target, include_performance=True)
```

### Q2: 哪个功能更重要？

**A**: 取决于你的需求：

- **日常使用**：`preview_execution` 更常用（快速、轻量）
- **性能优化**：`analyze_dependencies` 更重要（深入、全面）

### Q3: 可以只用其中一个吗？

**A**: 可以，但结合使用效果更好：

- **只用预览**：适合简单场景，快速确认
- **只用分析**：适合性能优化，深入理解
- **结合使用**：获得最全面的信息

### Q4: 执行顺序有影响吗？

**A**:

- **预览**：必须在执行前使用（否则无法检查缓存状态）
- **分析**：可以在执行前（静态）或执行后（动态）使用

### Q5: 如何选择使用哪个？

**A**: 参考选择指南：

- **快速确认** → `preview_execution`
- **性能优化** → `analyze_dependencies`
- **全面了解** → 两者结合

---

## 总结

### 核心关系

1. **互补性**：两者关注不同方面，信息互补
2. **时间性**：预览在执行前，分析在执行后（或静态）
3. **层次性**：预览是快速了解，分析是深入理解

### 使用建议

1. **日常使用**：优先使用 `preview_execution`（快速、轻量）
2. **性能优化**：使用 `analyze_dependencies`（深入、全面）
3. **完整工作流**：结合使用两者（获得最全面的信息）

### 典型工作流

```
预览 → 执行 → 分析 → 可视化 → 优化
```

---

## 相关资源

- [依赖分析指南](DEPENDENCY_ANALYSIS_GUIDE.md) - 详细的使用指南
- [执行预览指南](PREVIEW_EXECUTION.md) - 详细的使用指南
- [血缘可视化指南](LINEAGE_VISUALIZATION_GUIDE.md) - 可视化功能
- [API 参考](../../api/README.md) - 完整 API 文档

---

**快速链接**:
[依赖分析](DEPENDENCY_ANALYSIS_GUIDE.md) |
[执行预览](PREVIEW_EXECUTION.md) |
[血缘可视化](LINEAGE_VISUALIZATION_GUIDE.md)
