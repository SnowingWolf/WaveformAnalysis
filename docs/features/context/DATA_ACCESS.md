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
    output: str = "native",       # 返回形态: native/chunk_stream/array
    **kwargs               # 传递给插件的额外参数
) -> Any
```

`output="native"` 保持插件原始返回形态；`output="chunk_stream"` 保留流式/chunk
结果；`output="array"` 会将 chunk stream、generator 中的 `Chunk.data` 或直接产出的
`np.ndarray` item 拼接为完整数组，并把物化结果写回内存缓存。

### 自动依赖解析

`ctx.get_data(run_id, data_name)` 会通过内部插件 domain 解析执行计划。动态依赖在解析时
会接收当前 `run_id`，因此同一插件可针对不同运行选择不同上游；公开接口仍是
`ctx.resolve_dependencies(data_name, run_id=...)`。

```python
# 获取 paired_events 会自动执行整个依赖链
# raw_files → waveforms → st_waveforms → features → dataframe → paired_events
paired = ctx.get_data("run_001", "paired_events")

# 依赖的数据会被缓存，后续访问直接返回
waveforms = ctx.get_data("run_001", "waveforms")  # 直接从缓存返回
```

## records 流式构建路径

`records` 与 `wave_pool` 两个正式插件产物共用内部
`RecordsBundle(records, wave_pool)` 构建缓存。这里的“流式”主要指读取和中间构建
阶段分块处理；默认公开插件产物仍是完整的 `records` 结构化数组和连续
`wave_pool` 数组。

普通适配器从 `raw_files` 增量构建：

```text
raw_files
  -> build_records_from_raw_files_streaming()
  -> per-channel / per-chunk memmap parts
  -> heap merge
  -> RecordsBundle(records, wave_pool)
```

构建过程中，每个通道通过适配器的 `read_files_generator(...)` 分批读取原始文件，
再按 `records_part_size` 切成更小的 records 分片。每个分片先转换为局部
`RecordsBundle`，随后写入临时 memmap 文件，主流程只保留分片路径、记录数、样本数
等 `_RecordsPartRef` 元数据。

`v1725` 使用专用读取路径，但合并语义一致：

```text
raw_files
  -> build_records_from_v1725_files()
  -> iter_waves() + Numba channel-header/records-metadata kernels
  -> per-file streaming memmap parts
  -> heap merge
  -> RecordsBundle(records, wave_pool)
```

V1725 单个 `.bin` 文件内部仍按事件边界串行读取；`n_jobs` 只控制文件级并行，
不对单文件做 I/O 切分。每个文件读取过程中会按 `v1725_part_size`（默认
`100000` 条 wave）批量填充 records metadata 并写入 `_RecordsPartRef`，避免大文件
构建时把完整 `waves` 列表保留在内存中。V1725 channel header 解析与 records 数值
metadata 填充依赖 Numba；若 Numba import 或 JIT 编译失败，会直接暴露环境依赖错误。

最终合并会保持全局 records 顺序，并重写波形引用字段：

- 全局排序键为 `(timestamp, pid, board, channel)`。
- `wave_offset` 会按最终 `wave_pool` 重新计算，保证每条 record 指向正确波形片段。
- `record_id` 在最终输出中重置为连续全局编号。
- 普通适配器中 `channel_workers` 控制通道级并行，`n_jobs` 控制文件读取/解析并行，
  `records_part_size` 控制中间分片大小；V1725 中 `n_jobs` 控制文件级并行，
  `v1725_part_size` 控制单文件内 streaming part 大小。

底层还提供 `RecordsBundleRef` 形式的磁盘引用能力，用于显式的超大数据路径。
它可以按 chunk 读取 records 和 wave_pool，但这不是 `RecordsPlugin` / `WavePoolPlugin`
的默认公开输出契约；现有插件链路仍按内存中的 `RecordsBundle` 暴露 `records` 与
`wave_pool`。

## RecordsView 波形访问

当上游已经产出正式插件结果 `records + wave_pool` 时，可通过
`records_view(ctx, run_id)` 获取 `RecordsView`，用于按稳定 `record_id`
回切波形。`records_view(...)` 不再 fallback 到内部 bundle；缺少正式
`records` 或 `wave_pool` 产物时会直接报错。内部仍保留
`RecordsBundle(records, wave_pool)` 作为共享构建缓存，但不再建议下游直接依赖
这个内部对象。

```python
from waveform_analysis.core.data import records_view

rv = records_view(ctx, "run_001")
first_record_id = int(rv.records[0]["record_id"])

wave = rv.waves(first_record_id)
signal = rv.signals(first_record_id, sample_start=40, sample_end=120)

waves, mask = rv.waves([first_record_id], pad_to=256, mask=True)
```

约定如下：
- `rv.waves(...)` 返回原始波形；`baseline_correct=True` 时返回 baseline 校正后的波形。
- `rv.signals(...)` 返回按 `records.polarity` 统一为负极性的信号。
- 公开接口只使用 `record_id`，不再按 records 行号索引。
- 窗口切片统一使用 `sample_start` / `sample_end`。

### 访问滤波后的 records-backed 波形

当上游已经产出 `wave_pool_filtered` 时，可显式切换到滤波后的波形池：

```python
from waveform_analysis.core.data import records_view

rv = records_view(ctx, "run_001", wave_pool_name="wave_pool_filtered")
wave = rv.waves(int(rv.records[0]["record_id"]))
```

语义约定：
- `records` 始终保持不变，滤波只替换波形池，不修改 `record_id` / `timestamp` /
  `board` / `channel` / `event_length` 等 records 元数据。
- `wave_pool_filtered` 由 `records + wave_pool` 构建，特别适合 `v1725` 这类直接从
  records 路径开始的适配器。
- 对于支持 records 路径的计算插件，若配置 `wave_source="records"` 且
  `use_filtered=True`，应自动选择 `wave_pool_filtered`。

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
├── run_001-hit-abc12345.bin       # 二进制数据 (memmap)
├── run_001-hit-abc12345.json      # 元数据 (dtype, lineage, count)
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

> **注意**：所有 API 调用统一使用 `run_id` 作为运行标识符。`run_name` 参数已弃用，请使用 `run_id` 代替。

### 清除缓存

```python
# 清除指定 run + 数据的内存/磁盘缓存
ctx.clear_cache_for("run_001", "waveforms")

# 清除指定数据及其下游缓存
ctx.clear_cache_for("run_001", "waveforms", downstream=True)

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
data = ctx.time_range(
    run_id="run_001",
    data_name="st_waveforms",
    start_time=1000000,   # 起始时间（纳秒）
    end_time=2000000      # 结束时间（纳秒）
)

# 首次查询会自动构建时间索引（提升性能）
# 查看索引统计
stats = ctx.get_time_index_stats()
```

按通道筛选时有两种模式：

- **legacy list-of-arrays 数据**：`channel` 仍然是整数索引
- **flat structured array 数据**：必须显式给出硬件通道，例如 `"0:3"`、`(0, 3)` 或 `HardwareChannel(0, 3)`

```python
# 对 flat array（如 st_waveforms/basic_features/hit）按硬件通道筛选
ch03 = ctx.time_range(
    run_id="run_001",
    data_name="st_waveforms",
    start_time=1_000_000,
    end_time=2_000_000,
    channel="0:3",
)
```

注意：

- `channel` 字段现在只表示板内通道号，不再保证全局唯一
- 多板卡数据上如果只传裸 `channel=3`，`time_range()` 会拒绝执行，避免把不同 `board` 的同号通道混在一起

## 批量获取

### 多个数据名称

```python
results = {}
for data_name in ["waveforms", "st_waveforms", "features"]:
    results[data_name] = ctx.get_data("run_001", data_name)
```

### 使用 BatchProcessor

```python
from waveform_analysis.core.data import BatchProcessor

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

`BatchProcessor` 适合把同一个插件产物批量应用到多个 run，并集中收集 `results`、`errors` 和
`meta`。并行执行、错误策略、取消和配置网格扫描见
[BatchProcessor - 多运行批量处理](BATCH_PROCESSOR.md)。

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

### 查询已注册插件但不读取数据

`ctx.help("plugins")` 只列出当前 Context 已注册的插件；`ctx.help("<provides>")` 和
`ctx.help("plugin:<provides>", run_id=...)` 返回插件契约说明。只有显式提供 `run_id` 时才尝试
解析动态依赖，失败会回退到声明依赖。该帮助路径不调用 `get_data()`，也不会创建缓存。

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
- [Agent 入口](../../../AGENTS.md) - 任务导航与约束
- [Agent 文档索引](../../agents/INDEX.md) - agent 专题说明

[^source]: 来源：`waveform_analysis/core/context.py`、`waveform_analysis/core/storage/`。
