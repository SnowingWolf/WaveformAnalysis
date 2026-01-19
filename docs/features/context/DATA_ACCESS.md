**导航**: [文档中心](../../README.md) > [功能特性](../README.md) > [Context 功能](README.md) > 数据获取

---

# 数据获取

> **阅读时间**: 10 分钟 | **难度**: ⭐ 入门

本文档介绍如何使用 Context 获取插件产出的数据。

---

## 📋 目录

1. [基本数据获取](#基本数据获取)
2. [缓存机制](#缓存机制)
3. [进度显示](#进度显示)
4. [时间范围查询](#时间范围查询)
5. [批量获取](#批量获取)
6. [常见问题](#常见问题)

---

## 基本数据获取

### get_data() 方法

```python
from waveform_analysis.core.context import Context

ctx = Context(storage_dir="./cache")
# ... 注册插件 ...

# 获取数据
data = ctx.get_data(run_id="run_001", data_name="waveforms")
```

### 参数说明

```python
def get_data(
    run_id: str,           # 运行标识符（必需）
    data_name: str,        # 数据名称（必需）
    show_progress: bool = False,  # 是否显示进度条
    progress_desc: str = None,    # 自定义进度描述
    **kwargs               # 传递给插件的额外参数
) -> Any
```

### 自动依赖解析

```python
# 获取 paired_events 会自动执行整个依赖链
# raw_files → waveforms → st_waveforms → features → dataframe → paired_events
paired = ctx.get_data("run_001", "paired_events")

# 依赖的数据会被缓存，后续访问直接返回
waveforms = ctx.get_data("run_001", "waveforms")  # 直接从缓存返回
```

---

## 缓存机制

### 三级缓存

Context 使用三级缓存加速数据访问：

```
1. 内存缓存 → 最快，当前会话有效
2. 磁盘缓存 → 持久化，跨会话有效
3. 重新计算 → 最慢，缓存失效时执行
```

### 缓存查询顺序

```python
# get_data 的内部流程：
# 1. 检查内存缓存 → 命中则直接返回
# 2. 检查磁盘缓存 → 命中则加载到内存并返回
# 3. 执行插件计算 → 计算并缓存结果
```

### 缓存状态查看

```python
# 预览执行计划和缓存状态
result = ctx.preview_execution("run_001", "paired_events")

# 查看哪些已缓存
for plugin, status in result['cache_status'].items():
    if status['in_memory']:
        print(f"{plugin}: 内存缓存")
    elif status['on_disk']:
        print(f"{plugin}: 磁盘缓存")
    else:
        print(f"{plugin}: 需要计算")
```

### 清除缓存

```python
# 清除特定数据的内存缓存
ctx.clear_data("run_001", "waveforms")

# 清除特定 run 的所有内存缓存
ctx.clear_run("run_001")

# 清除所有内存缓存
ctx.clear_all()
```

---

## 进度显示

### 启用进度条

```python
# 方式 1: get_data 时启用
data = ctx.get_data("run_001", "paired_events", show_progress=True)

# 方式 2: 自定义进度描述
data = ctx.get_data(
    "run_001", "paired_events",
    show_progress=True,
    progress_desc="处理波形数据"
)
```

### 进度条输出示例

```
处理波形数据: 100%|██████████| 6/6 [00:05<00:00, 1.2 plugins/s]
  ✓ raw_files (0.5s)
  ✓ waveforms (2.1s)
  ✓ st_waveforms (0.8s)
  ✓ features (0.6s)
  ✓ dataframe (0.4s)
  ✓ paired_events (0.6s)
```

### 全局进度设置

```python
# 在配置中设置默认进度显示
ctx.set_config({'show_progress': True})

# 之后所有 get_data 调用都会显示进度
data = ctx.get_data("run_001", "paired_events")  # 自动显示进度
```

---

## 时间范围查询

### get_data_time_range() 方法

对于大型数据集，可以只获取特定时间范围的数据：

```python
# 获取指定时间范围的数据
data = ctx.get_data_time_range(
    run_id="run_001",
    data_name="st_waveforms",
    start_time=1000000,   # 起始时间（纳秒）
    end_time=2000000      # 结束时间（纳秒）
)

print(f"获取了 {len(data)} 条记录")
```

### 构建时间索引

对于频繁的时间范围查询，预先构建索引可以提升性能：

```python
# 预先构建时间索引
ctx.build_time_index("run_001", "st_waveforms")

# 之后的查询会更快
data1 = ctx.get_data_time_range("run_001", "st_waveforms", 1000, 2000)
data2 = ctx.get_data_time_range("run_001", "st_waveforms", 3000, 4000)

# 查看索引统计
stats = ctx.get_time_index_stats()
print(stats)
```

### 时间字段配置

```python
# 如果数据使用非标准时间字段
ctx.build_time_index(
    "run_001", "st_waveforms",
    time_field="timestamp",  # 自定义时间字段名
    endtime_field="computed"  # endtime 计算方式
)
```

---

## 批量获取

### 多个数据名称

```python
# 获取多个数据
results = {}
for data_name in ["waveforms", "st_waveforms", "features"]:
    results[data_name] = ctx.get_data("run_001", data_name)
```

### 多个 run_id

```python
# 获取多个 run 的同一数据
run_ids = ["run_001", "run_002", "run_003"]
all_features = {}

for run_id in run_ids:
    all_features[run_id] = ctx.get_data(run_id, "features")
```

### 使用 BatchProcessor

对于大规模批量处理，使用专门的批处理器：

```python
from waveform_analysis.core.data.export import BatchProcessor

processor = BatchProcessor(ctx)

# 并行处理多个 run
results = processor.process_runs(
    run_ids=["run_001", "run_002", "run_003"],
    data_name="paired_events",
    max_workers=4,
    show_progress=True
)

# 访问结果
for run_id, data in results['results'].items():
    print(f"{run_id}: {len(data)} events")
```

---

## 数据类型

### 结构化数组

大多数插件返回 NumPy 结构化数组：

```python
st_waveforms = ctx.get_data("run_001", "st_waveforms")

# 访问字段
times = st_waveforms['time']
waves = st_waveforms['wave']
channels = st_waveforms['channel']

# 查看 dtype
print(st_waveforms.dtype)
# [('time', '<f8'), ('wave', '<f4', (1000,)), ('channel', '<i4')]
```

### DataFrame

某些插件返回 pandas DataFrame：

```python
df = ctx.get_data("run_001", "dataframe")

# 标准 DataFrame 操作
print(df.head())
print(df.columns)
filtered = df[df['charge'] > 100]
```

### 列表和生成器

某些插件返回列表或生成器：

```python
# 列表类型（按通道分组）
waveforms = ctx.get_data("run_001", "waveforms")
for ch_idx, ch_data in enumerate(waveforms):
    print(f"通道 {ch_idx}: {len(ch_data)} 条波形")

# 生成器类型（流式处理）
# 注意：生成器只能消费一次
stream = ctx.get_data("run_001", "waveforms_stream")
for chunk in stream:
    process(chunk)
```

---

## 常见问题

### Q1: 数据获取很慢怎么办？

**A**: 检查以下几点：
```python
# 1. 检查缓存状态
ctx.preview_execution("run_001", "target_data")

# 2. 启用进度条查看瓶颈
ctx.get_data("run_001", "target_data", show_progress=True)

# 3. 考虑使用流式处理
# 4. 检查磁盘缓存是否启用
print(f"Storage dir: {ctx.storage_dir}")
```

### Q2: 如何强制重新计算？

**A**: 清除缓存后重新获取：
```python
# 清除特定数据的缓存
ctx.clear_data("run_001", "waveforms")

# 重新获取（会重新计算）
data = ctx.get_data("run_001", "waveforms")
```

### Q3: 如何检查数据是否已计算？

**A**: 使用 preview_execution：
```python
result = ctx.preview_execution("run_001", "waveforms")
status = result['cache_status']['waveforms']

if status['in_memory'] or status['on_disk']:
    print("数据已缓存")
else:
    print("需要计算")
```

### Q4: get_data 返回 None 怎么办？

**A**: 可能的原因：
- 插件未注册 → 检查 `ctx.list_provided_data()`
- 数据名称拼写错误 → 检查 `plugin.provides`
- 插件计算返回了 None → 检查插件实现

### Q5: 如何获取原始数据的路径？

**A**:
```python
# 获取 raw_files 插件的输出
raw_files = ctx.get_data("run_001", "raw_files")
print(raw_files)  # 通常是文件路径列表
```

---

## 相关文档

- [插件管理](PLUGIN_MANAGEMENT.md) - 注册和管理插件
- [配置管理](CONFIGURATION.md) - 设置插件配置
- [缓存机制](../data-processing/CACHE.md) - 详细缓存说明
- [预览执行](PREVIEW_EXECUTION.md) - 执行前预览
- [依赖分析](DEPENDENCY_ANALYSIS_VS_PREVIEW_EXECUTION.md) 依赖分析


---

**快速链接**: [插件管理](PLUGIN_MANAGEMENT.md) | [配置管理](CONFIGURATION.md) | [预览执行](PREVIEW_EXECUTION.md)
