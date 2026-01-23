**导航**: [文档中心](../../README.md) > [功能特性](../README.md) > [Context 功能](README.md) > 预览执行计划

---

# Preview Execution - 运行前确认 Lineage

## 概述

`preview_execution()` 是 Context 类的新方法，允许你在实际执行数据处理之前预览执行计划。这个功能可以帮助你：

- ✅ 查看将要执行的插件链
- ✅ 了解配置参数
- ✅ 查看依赖关系树
- ✅ 确认缓存状态（哪些已缓存，哪些需要计算）

---

---

## 为什么需要这个功能？

### 问题场景

在复杂的数据处理流程中，你可能会遇到：

1. **不确定执行顺序** - 不知道哪些插件会被执行
2. **配置错误** - 发现执行后配置不对，浪费时间
3. **重复计算** - 不知道哪些数据已经缓存
4. **依赖关系不清** - 不了解插件之间的依赖关系

### 解决方案

使用 `preview_execution()` 可以在执行前：

```python
# 预览执行计划
ctx.preview_execution('run_001', 'signal_peaks')

# 确认无误后再执行
data = ctx.get_data('run_001', 'signal_peaks')
```

---

## API 参考

### 方法签名

```python
def preview_execution(
    self,
    run_id: str,
    data_name: str,
    show_tree: bool = True,
    show_config: bool = True,
    show_cache: bool = True,
    verbose: int = 1,
) -> Dict[str, Any]:
```

### 参数说明

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `run_id` | str | 必需 | 运行标识符 |
| `data_name` | str | 必需 | 要获取的数据名称 |
| `show_tree` | bool | True | 是否显示依赖关系树 |
| `show_config` | bool | True | 是否显示配置参数 |
| `show_cache` | bool | True | 是否显示缓存状态 |
| `verbose` | int | 1 | 显示详细程度 (0=简洁, 1=标准, 2=详细) |

### 返回值

返回一个字典，包含以下内容：

```python
{
    'target': str,                    # 目标数据名称
    'run_id': str,                    # 运行标识符
    'execution_plan': List[str],      # 插件执行顺序列表
    'cache_status': Dict[str, dict],  # 每个插件的缓存状态
    'configs': Dict[str, dict],       # 非默认配置参数
    'needed_set': List[str],          # 实际需要执行的步骤（cache-aware）
}
```

#### cache_status 结构

```python
{
    'plugin_name': {
        'in_memory': bool,     # 是否在内存中
        'on_disk': bool,       # 是否在磁盘上
        'needs_compute': bool, # 是否需要计算
        'pruned': bool         # 是否因缓存剪枝而跳过
    },
    ...
}
```

`pruned=True` 表示该步骤在本次执行中会被跳过（依赖或自身缓存命中）。

#### configs 结构

```python
{
    'plugin_name': {
        'option_name': {
            'value': Any,        # 当前值
            'default': Any,      # 默认值
            'type': str          # 类型名称
        },
        ...
    },
    ...
}
```

---

## 使用示例

### 示例 1: 基本使用

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import *

# 创建 Context 并注册插件
ctx = Context(storage_dir="./strax_data")
ctx.register(RawFilesPlugin())
ctx.register(WaveformsPlugin())
ctx.register(StWaveformsPlugin())
ctx.register(FilteredWaveformsPlugin())
ctx.register(SignalPeaksPlugin())

# 设置配置
ctx.set_config({"data_root": "DAQ", "n_channels": 2})
ctx.set_config({"filter_type": "SG"}, plugin_name="filtered_waveforms")

# 预览执行计划
ctx.preview_execution('run_001', 'signal_peaks')
```

**输出示例：**

```
======================================================================
执行计划预览: signal_peaks (run_id: run_001)
======================================================================

📋 执行计划:
  共 5 个步骤
  ├─→ 1. raw_files ⚙️ [需计算]
  ├─→ 2. waveforms ⚙️ [需计算]
  ├─→ 3. st_waveforms ⚙️ [需计算]
  ├─→ 4. filtered_waveforms ⚙️ [需计算]
  └─→ 5. signal_peaks ⚙️ [需计算]

🌳 依赖关系树:
  └─ signal_peaks
     ├─ filtered_waveforms
     │  └─ st_waveforms
     │     └─ waveforms
     │        └─ raw_files
     └─ st_waveforms
        └─ waveforms
           └─ raw_files

⚙️ 自定义配置:
  • filtered_waveforms:
      filter_type = SG

💾 缓存状态汇总:
  • 内存缓存: 0 个
  • 磁盘缓存: 0 个
  • 需要计算: 5 个

======================================================================
```

### 示例 2: 不同详细程度

```python
# 简洁模式
ctx.preview_execution('run_001', 'signal_peaks', verbose=0)

# 标准模式（默认）
ctx.preview_execution('run_001', 'signal_peaks', verbose=1)

# 详细模式（显示默认值）
ctx.preview_execution('run_001', 'signal_peaks', verbose=2)
```

### 示例 3: 选择性显示

```python
# 只显示执行计划和缓存状态
ctx.preview_execution(
    'run_001', 'signal_peaks',
    show_tree=False,
    show_config=False,
    show_cache=True
)

# 只显示依赖树
ctx.preview_execution(
    'run_001', 'signal_peaks',
    show_tree=True,
    show_config=False,
    show_cache=False
)
```

### 示例 4: 程序化使用

```python
# 获取预览结果
result = ctx.preview_execution('run_001', 'signal_peaks')

# 检查需要计算的插件数量
needs_compute = [
    plugin for plugin, status in result['cache_status'].items()
    if status['needs_compute']
]

print(f"需要计算的插件: {len(needs_compute)} 个")

# 基于结果做决策
if len(needs_compute) > 3:
    print("⚠️ 需要计算多个插件，可能需要较长时间")
    # 可以选择不执行或请求用户确认
else:
    print("✓ 大部分数据已缓存，执行会很快")
    data = ctx.get_data('run_001', 'signal_peaks')
```

### 示例 5: 完整工作流（带确认）

```python
# 步骤 1: 预览
print("步骤 1: 预览执行计划")
result = ctx.preview_execution('run_001', 'signal_peaks')

# 步骤 2: 用户确认
user_input = input("\n是否继续执行? (y/n): ").strip().lower()
if user_input != 'y':
    print("✗ 用户取消执行")
    sys.exit(0)

# 步骤 3: 执行
print("步骤 3: 执行数据处理")
data = ctx.get_data('run_001', 'signal_peaks')
print(f"✓ 成功获取数据")
```

### 示例 6: 检查缓存状态

```python
# 第一次执行前预览（所有数据都需要计算）
result1 = ctx.preview_execution('run_001', 'signal_peaks')
print(f"首次执行需要计算: {sum(1 for s in result1['cache_status'].values() if s['needs_compute'])} 个插件")

# 执行
data = ctx.get_data('run_001', 'signal_peaks')

# 第二次预览（部分数据已缓存）
result2 = ctx.preview_execution('run_001', 'signal_peaks')
print(f"第二次执行需要计算: {sum(1 for s in result2['cache_status'].values() if s['needs_compute'])} 个插件")
```

---

## 输出详解

### 执行计划

显示插件的执行顺序，每个插件后面标记缓存状态：

- ✓ [内存] - 数据在内存中
- ✓ [磁盘] - 数据在磁盘缓存中
- ⚙️ [需计算] - 需要重新计算

### 依赖关系树

以树状结构显示插件之间的依赖关系，帮助理解数据流向。

```
└─ signal_peaks
   ├─ filtered_waveforms
   │  └─ st_waveforms
   │     └─ waveforms
   └─ st_waveforms
      └─ waveforms
```

### 自定义配置

只显示用户修改过的配置项（非默认值），避免信息过载。

```
• filtered_waveforms:
    filter_type = SG (默认: SG)  # verbose=2 时显示
    sg_window_size = 15 (默认: 11)
```

### 缓存状态汇总

统计各类缓存的数量：

```
💾 缓存状态汇总:
  • 内存缓存: 2 个
  • 磁盘缓存: 1 个
  • 需要计算: 2 个
```

---

## 使用场景

### 1. 调试配置问题

```python
# 预览配置，确认参数正确
ctx.set_config({"filter_type": "SG"}, plugin_name="filtered_waveforms")
ctx.preview_execution('run_001', 'signal_peaks')

# 发现配置错误，及时修正
ctx.set_config({"filter_type": "BW"}, plugin_name="filtered_waveforms")
ctx.preview_execution('run_001', 'signal_peaks')  # 再次确认
```

### 2. 性能优化

```python
# 查看哪些数据已缓存
result = ctx.preview_execution('run_001', 'signal_peaks')

# 如果大部分已缓存，直接执行
if sum(1 for s in result['cache_status'].values() if s['on_disk']) > 3:
    data = ctx.get_data('run_001', 'signal_peaks')  # 会很快
```

### 3. 学习依赖关系

```python
# 对于新用户，预览可以帮助理解插件依赖
ctx.preview_execution('run_001', 'signal_peaks', show_tree=True)
```

### 4. 批处理前确认

```python
# 在批量处理多个 run 之前，先预览一个
ctx.preview_execution('run_001', 'signal_peaks')

# 确认无误后批处理
for run_id in ['run_001', 'run_002', 'run_003']:
    data = ctx.get_data(run_id, 'signal_peaks')
```

---

## 与其他方法的比较

| 方法 | 用途 | 是否执行计算 | 输出格式 |
|------|------|--------------|----------|
| `preview_execution()` | 预览执行计划和配置 | ✗ 否 | 文本 + 字典 |
| `get_lineage()` | 获取血缘信息 | ✗ 否 | 字典 |
| `resolve_dependencies()` | 获取执行顺序 | ✗ 否 | 列表 |
| `plot_lineage()` | 可视化血缘图 | ✗ 否 | 图形 |
| `analyze_dependencies()` | 依赖分析（结构+性能） | ✗ 否 | 分析报告 |
| `get_data()` | 获取数据 | ✓ 是 | 数据 |

**选择建议：**

- **想快速了解执行情况** → `preview_execution()`
- **需要详细血缘字典** → `get_lineage()`
- **想要可视化** → `plot_lineage()`
- **需要性能分析** → `analyze_dependencies()`

---

## 常见问题

### Q1: preview_execution() 会触发实际计算吗？

**A**: 不会。`preview_execution()` 只分析元数据，不会执行任何插件或加载数据。

### Q2: 如何让 get_data() 自动显示预览？

**A**: 目前需要手动调用 `preview_execution()`。未来可能添加配置项支持自动预览。

### Q3: 预览结果和实际执行有差异吗？

**A**: 不会。`preview_execution()` 使用与 `get_data()` 相同的依赖解析逻辑。

### Q4: 可以在脚本中静默使用吗？

**A**: 可以。返回的字典可以程序化使用，不一定要查看打印输出。

```python
result = ctx.preview_execution('run_001', 'signal_peaks')
# 直接使用 result 字典，不看打印输出
if result['cache_status']['signal_peaks']['needs_compute']:
    # do something
```

### Q5: 如何只获取执行计划而不打印？

**A**: 使用 `resolve_dependencies()` 方法：

```python
plan = ctx.resolve_dependencies('signal_peaks')
print(plan)  # ['raw_files', 'waveforms', 'st_waveforms', ...]
```

---

## 完整示例程序

参考 `examples/demo_preview_execution.py`，包含：

1. 基本预览功能
2. 不同详细程度的预览
3. 选择性显示内容
4. 程序化使用预览结果
5. 完整工作流（预览 → 确认 → 执行）
6. 比较不同目标的执行计划

运行示例：

```bash
python examples/demo_preview_execution.py
```

---

## 开发计划

未来可能添加的功能：

- [ ] 自动确认模式（通过配置项 `confirm_before_run=True`）
- [ ] 执行时间预估（基于历史统计）
- [ ] 内存需求预估
- [ ] 导出预览结果为 JSON/YAML
- [ ] Web UI 支持

---

## 参考文档

- [Context API 文档](../docs/ARCHITECTURE.md#context-layer)
- [依赖分析](../docs/DEPENDENCY_ANALYSIS_GUIDE.md)
- [Lineage 可视化](../CLAUDE.md#lineage-visualization)
- [配置管理](../CLAUDE.md#configuration-management)
