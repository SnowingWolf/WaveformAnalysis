**导航**: [文档中心](../../README.md) > [功能特性](../README.md) > [Context 功能](README.md) > 数据获取

---

# 数据获取

> **阅读时间**: 10 分钟 | **难度**: ⭐ 入门

本文档介绍如何使用 Context 获取插件产出的数据。

---

## 📋 目录

1. [基本数据获取](#基本数据获取)
2. [缓存机制](#缓存机制)
3. [缓存扫描与诊断](#缓存扫描与诊断)
4. [进度显示](#进度显示)
5. [时间范围查询](#时间范围查询)
6. [批量获取](#批量获取)
7. [常见问题](#常见问题)

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

### 核心机制

#### Lineage Hashing (血缘追踪)

每个数据对象（如 `hits`）都有一个唯一的 Lineage，包含：
- **Plugin**: 插件类名
- **Version**: 插件版本号
- **Config**: 插件及上游插件的配置
- **DType**: 标准化 dtype（`dtype.descr`）
- **Dependencies**: 上游数据的 Lineage

Lineage 会序列化并计算 SHA1 哈希，作为缓存键的一部分。
配置/版本/dtype 任意变化都会导致缓存自动失效并重新计算。
相同配置和代码会指向相同缓存键，保证结果确定性。
加载缓存时会比对元数据中的 lineage，若不一致会提示并强制重算。
如果插件实现了 `get_lineage(context)`，`Context.get_lineage()` 会优先使用该实现覆盖默认血缘生成逻辑。

#### Memmap 存储 (零拷贝访问)

结构化数组使用 `numpy.memmap` 存储：
- **原子写入**: 先写 `.tmp`，成功后重命名为 `.bin`
- **按需加载**: 读取时只映射，不一次性加载全量数据
- **超大数据支持**: 可处理超内存数据集
- **快速启动**: 建立映射几乎是瞬时的

### 缓存目录结构

默认缓存目录为 `storage_dir`（默认 `./strax_data`）：

```text
strax_data/
├── run_001-hits-abc12345.bin      # 二进制数据 (memmap)
├── run_001-hits-abc12345.json     # 元数据 (dtype, lineage, count)
└── _side_effects/                 # 侧效应插件输出 (绘图, 导出等)
    └── run_001/
        └── my_plot_plugin/
            └── plot.png
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

# 清除 run 的全部缓存（内存 + 磁盘）
ctx.clear_cache_for("run_001")
```

> 提示：`clear_cache()` 是旧的步骤级缓存接口，插件数据缓存请使用 `clear_cache_for()`。

### 注意事项

- **DType 一致性**: 插件必须定义 `dtype`，确保 memmap 可解析。
- **并发安全**: 存储使用文件锁协调写入，但不适合跨节点/网络文件系统的强一致写入。

### CI 与实践建议

- CI 中建议使用临时目录存放持久化缓存，避免污染工作区。
- 可缓存依赖/测试数据，但不建议缓存可能导致非确定性的结果文件。
- 推荐覆盖点：
  - 持久化缓存创建与读取
  - `watch_attrs` 导致的缓存失效
  - 内存缓存启用/禁用行为

简化的 GitHub Actions 示例：

```yaml
name: Python tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v4
        with:
          python-version: "3.11"
      - name: Install deps
        run: python -m pip install -r requirements.txt
      - name: Run tests
        run: pytest -q
      - name: Upload test artifacts (optional)
        if: failure()
        uses: actions/upload-artifact@v4
        with:
          name: test-output
          path: .pytest_cache
```

### 实践小贴士

- 网络文件系统可能导致 mtime 精度不足，必要时把 `watch_attrs` 设为更稳定的内容。
- 多进程共享缓存时，确保写入是原子操作（临时文件 + 重命名）。

---

## 缓存扫描与诊断

Context 也提供便捷接口：

```python
analyzer = ctx.analyze_cache()
stats = ctx.cache_stats(detailed=True)
issues = ctx.diagnose_cache(auto_fix=True, dry_run=True)
```

### 扫描与索引（CacheAnalyzer）

`CacheAnalyzer` 用于扫描当前 storage 目录并构建缓存索引，支持增量扫描和过滤查询：

```python
from waveform_analysis.core.storage.cache_analyzer import CacheAnalyzer

analyzer = CacheAnalyzer(ctx)
analyzer.scan()  # 默认增量扫描

# 强制刷新索引
analyzer.scan(force_refresh=True)

# 按条件过滤条目
entries = analyzer.get_entries(run_id="run_001", min_size=1024 * 1024)

# 查看摘要
analyzer.print_summary(detailed=True)
```

### 缓存统计（CacheStatsCollector）

`CacheStatsCollector` 汇总缓存规模、按 run/数据类型统计，并支持导出 JSON/CSV：

```python
from waveform_analysis.core.storage.cache_statistics import CacheStatsCollector

collector = CacheStatsCollector(analyzer)
stats = collector.collect()
collector.print_summary(stats, detailed=True)

# 导出统计
collector.export_stats(stats, "cache_stats.json", format="json")
collector.export_stats(stats, "cache_stats.csv", format="csv")
```

### 缓存分析插件（CacheAnalysisPlugin）

如果需要在 Context 中直接获取缓存分析报告，可注册 `CacheAnalysisPlugin`：

```python
from waveform_analysis.core.plugins.builtin.cpu import CacheAnalysisPlugin

ctx.register(CacheAnalysisPlugin())
report = ctx.get_data("run_001", "cache_analysis", include_entries=False)
print(report["summary"])
```

### 诊断问题（CacheDiagnostics）

`CacheDiagnostics` 用于检查版本不匹配、数据文件缺失、大小不匹配、校验和失败、
孤儿文件等问题，并支持自动修复（建议先 dry-run）：

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

# 预演修复
diag.auto_fix(issues, dry_run=True)
```

### 清理缓存（CacheCleaner）

`CacheCleaner` 支持按 LRU、最大文件、版本不匹配等策略清理缓存。
建议先用 `CacheAnalyzer` 扫描并预览清理计划，再执行实际删除。

可用策略（`CleanupStrategy`）：
- `LRU`: 最近最少使用（按创建时间排序，优先删除最早创建）
- `OLDEST`: 最旧的（同 LRU，但语义更直观）
- `LARGEST`: 最大文件优先
- `VERSION_MISMATCH`: 插件版本不匹配的缓存
- `FAILED_INTEGRITY`: 完整性检查失败或文件异常
- `BY_RUN`: 按 run 清理
- `BY_DATA_TYPE`: 按数据类型清理

常用参数说明：
- `target_size_mb`: 目标释放空间（与 `max_entries` 二选一）
- `max_entries`: 最多删除条目数
- `keep_recent_days`: 保留最近 N 天的数据
- `run_id` / `data_name`: 限定清理范围
- `dry_run`: 演练模式，默认建议 `True`

```python
from waveform_analysis.core.storage.cache_analyzer import CacheAnalyzer
from waveform_analysis.core.storage.cache_cleaner import CacheCleaner, CleanupStrategy

analyzer = CacheAnalyzer(ctx)
analyzer.scan()

cleaner = CacheCleaner(analyzer)
cleaner.plan_cleanup(
    strategy=CleanupStrategy.LRU,
    target_size_mb=500
).preview_plan(detailed=True)
cleaner.execute(dry_run=True)
```

更多用法示例：

```python
# 1) 按目标总大小清理（保留到 2GB）
cleaner.cleanup_to_target_size(target_total_mb=2048, strategy=CleanupStrategy.LRU, dry_run=True)

# 2) 按年龄清理（保留 7 天内数据）
cleaner.cleanup_by_age(max_age_days=7, dry_run=True)

# 3) 只清理某个 run
cleaner.cleanup_run("run_001", dry_run=True)

# 4) 只清理某个数据类型
cleaner.cleanup_data_type("peaks", dry_run=True)

# 5) 仅清理版本不匹配或完整性失败的条目
cleaner.plan_cleanup(strategy=CleanupStrategy.VERSION_MISMATCH)
cleaner.execute(dry_run=True)
```

注意事项：
- `VERSION_MISMATCH` 依赖已注册插件的 `version` 信息
- `FAILED_INTEGRITY` 会检查文件缺失和大小异常
- `dry_run=False` 才会实际删除文件，建议先预览

### 运行时缓存检查（RuntimeCacheManager）

`RuntimeCacheManager` 是 Context 内部的运行时缓存检查器，用于统一检查内存/磁盘缓存。
通常只在调试或高级用法中直接使用：

```python
from waveform_analysis.core.storage.cache_manager import RuntimeCacheManager

cache_manager = RuntimeCacheManager(ctx)
cache_key = ctx.key_for("run_001", "st_waveforms")

data, cache_hit = cache_manager.check_cache("run_001", "st_waveforms", cache_key)
print(f"cache_hit={cache_hit}")
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
# 如果数据使用非标准时间字段（流式默认使用 timestamp）
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

### Q6: 可以把缓存文件提交到仓库用于加速 CI 吗？

**A**: 不建议。缓存可能依赖本地路径、mtime 或环境差异，提交后容易导致不可预期的结果。
如需加速 CI，建议缓存依赖或测试生成的数据，并保持缓存可失效。

---

## 相关文档

- [插件管理](PLUGIN_MANAGEMENT.md) - 注册和管理插件
- [配置管理](CONFIGURATION.md) - 设置插件配置
- [缓存机制](#缓存机制) - 缓存原理与目录结构
- [缓存管理 CLI](../../cli/WAVEFORM_CACHE.md) - 缓存扫描、诊断与清理
- [预览执行](PREVIEW_EXECUTION.md) - 执行前预览
- [依赖分析](DEPENDENCY_ANALYSIS_VS_PREVIEW_EXECUTION.md) - 依赖分析


---

**快速链接**: [插件管理](PLUGIN_MANAGEMENT.md) | [配置管理](CONFIGURATION.md) | [预览执行](PREVIEW_EXECUTION.md)
