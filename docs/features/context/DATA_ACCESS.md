# 数据访问

**导航**: [文档中心](../../README.md) > [功能特性](../README.md) > [Context 功能](README.md) > 数据访问

本文档介绍如何使用 Context 获取插件产出的数据。[^source]

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

## 缓存管理

缓存用于避免重复计算，详细机制见下节。

## 缓存机制

### 三级缓存

Context 使用三级缓存加速数据访问：

1. **内存缓存** - 最快，当前会话有效
2. **磁盘缓存** - 持久化，跨会话有效
3. **重新计算** - 最慢，缓存失效时执行

### Lineage Hashing（血缘追踪）

每个数据对象都有唯一的 Lineage，包含：
- Plugin: 插件类名
- Version: 插件版本号
- Config: 插件及上游插件的配置
- DType: 标准化 dtype
- Dependencies: 上游数据的 Lineage

配置/版本/dtype 任意变化都会导致缓存自动失效并重新计算。

### Memmap 存储（零拷贝访问）

结构化数组使用 `numpy.memmap` 存储：
- **原子写入**: 先写 `.tmp`，成功后重命名为 `.bin`
- **按需加载**: 读取时只映射，不一次性加载全量数据
- **超大数据支持**: 可处理超内存数据集

### 缓存目录结构

```text
strax_data/
├── run_001-hits-abc12345.bin      # 二进制数据 (memmap)
├── run_001-hits-abc12345.json     # 元数据 (dtype, lineage, count)
└── _side_effects/                 # 侧效应插件输出
    └── run_001/
        └── my_plot_plugin/
            └── plot.png
```

### 缓存状态查看

```python
result = ctx.preview_execution("run_001", "paired_events")

for plugin, status in result['cache_status'].items():
    if status['in_memory']:
        print(f"{plugin}: 内存缓存")
    elif status['on_disk']:
        print(f"{plugin}: 磁盘缓存")
    elif status.get('pruned'):
        print(f"{plugin}: 缓存剪枝")
    else:
        print(f"{plugin}: 需要计算")
```

### 清除缓存

```python
# 清除指定 run + 数据的内存/磁盘缓存
ctx.clear_cache_for("run_001", "waveforms")

# 仅清除内存缓存（保留磁盘）
ctx.clear_cache_for("run_001", "waveforms", clear_disk=False)

# 清除 run 的全部缓存
ctx.clear_cache_for("run_001")
```

## 缓存扫描与诊断

Context 提供便捷接口：

```python
analyzer = ctx.analyze_cache()
stats = ctx.cache_stats(detailed=True)
issues = ctx.diagnose_cache(auto_fix=True, dry_run=True)
```

### 扫描与索引

```python
from waveform_analysis.core.storage.cache_analyzer import CacheAnalyzer

analyzer = CacheAnalyzer(ctx)
analyzer.scan()  # 默认增量扫描
analyzer.scan(force_refresh=True)  # 强制刷新

# 按条件过滤
entries = analyzer.get_entries(run_id="run_001", min_size=1024 * 1024)
analyzer.print_summary(detailed=True)
```

### 缓存统计

```python
from waveform_analysis.core.storage.cache_statistics import CacheStatsCollector

collector = CacheStatsCollector(analyzer)
stats = collector.collect()
collector.print_summary(stats, detailed=True)

# 导出统计
collector.export_stats(stats, "cache_stats.json", format="json")
```

### 诊断问题

```python
from waveform_analysis.core.storage.cache_diagnostics import CacheDiagnostics

diag = CacheDiagnostics(analyzer)
issues = diag.diagnose(
    run_id="run_001",
    check_integrity=True,
    check_orphans=True,
    check_versions=True
)
diag.print_report(issues, group_by="severity")
diag.auto_fix(issues, dry_run=True)  # 预演修复
```

### 清理缓存

```python
from waveform_analysis.core.storage.cache_cleaner import CacheCleaner, CleanupStrategy

cleaner = CacheCleaner(analyzer)
cleaner.plan_cleanup(
    strategy=CleanupStrategy.LRU,
    target_size_mb=500
).preview_plan(detailed=True)
cleaner.execute(dry_run=True)
```

可用策略：
- `LRU`: 最近最少使用
- `OLDEST`: 最旧的
- `LARGEST`: 最大文件优先
- `VERSION_MISMATCH`: 插件版本不匹配
- `FAILED_INTEGRITY`: 完整性检查失败
- `BY_RUN`: 按 run 清理
- `BY_DATA_TYPE`: 按数据类型清理

## 进度显示

```python
# 方式 1: get_data 时启用
data = ctx.get_data("run_001", "paired_events", show_progress=True)

# 方式 2: 自定义进度描述
data = ctx.get_data(
    "run_001", "paired_events",
    show_progress=True,
    progress_desc="处理波形数据"
)

# 全局进度设置
ctx.set_config({'show_progress': True})
```

## 时间范围查询

```python
# 获取指定时间范围的数据
data = ctx.get_data_time_range(
    run_id="run_001",
    data_name="st_waveforms",
    start_time=1000000,   # 起始时间（纳秒）
    end_time=2000000      # 结束时间（纳秒）
)

# 预先构建时间索引（提升性能）
ctx.build_time_index("run_001", "st_waveforms")

# 查看索引统计
stats = ctx.get_time_index_stats()
```

## 批量获取

### 多个数据名称

```python
results = {}
for data_name in ["waveforms", "st_waveforms", "features"]:
    results[data_name] = ctx.get_data("run_001", data_name)
```

### 使用 BatchProcessor

```python
from waveform_analysis.core.data.export import BatchProcessor

processor = BatchProcessor(ctx)
results = processor.process_runs(
    run_ids=["run_001", "run_002", "run_003"],
    data_name="paired_events",
    max_workers=4,
    show_progress=True
)

for run_id, data in results['results'].items():
    print(f"{run_id}: {len(data)} events")
```

## 数据类型

### 结构化数组

```python
st_waveforms = ctx.get_data("run_001", "st_waveforms")

# 访问字段
times = st_waveforms['time']
waves = st_waveforms['wave']
channels = st_waveforms['channel']

# 查看 dtype
print(st_waveforms.dtype)
```

### DataFrame

```python
df = ctx.get_data("run_001", "dataframe")
print(df.head())
filtered = df[df['charge'] > 100]
```

## 常见问题

### Q1: 数据获取很慢怎么办？

```python
# 1. 检查缓存状态
ctx.preview_execution("run_001", "target_data")

# 2. 启用进度条查看瓶颈
ctx.get_data("run_001", "target_data", show_progress=True)

# 3. 检查磁盘缓存是否启用
print(f"Storage dir: {ctx.storage_dir}")
```

### Q2: 如何强制重新计算？

```python
ctx.clear_data("run_001", "waveforms")
data = ctx.get_data("run_001", "waveforms")  # 重新计算
```

### Q3: get_data 返回 None 怎么办？

可能的原因：
- 插件未注册 → 检查 `ctx.list_provided_data()`
- 数据名称拼写错误 → 检查 `plugin.provides`
- 插件计算返回了 None → 检查插件实现

## 相关文档

- [插件管理](PLUGIN_MANAGEMENT.md) - 注册和管理插件
- [配置管理](CONFIGURATION.md) - 设置插件配置
- [缓存管理 CLI](../../cli/WAVEFORM_CACHE.md) - 缓存扫描、诊断与清理
- [执行预览](PREVIEW_EXECUTION.md) - 执行前预览

[^source]: 来源：`waveform_analysis/core/context.py`、`waveform_analysis/core/storage/`。
