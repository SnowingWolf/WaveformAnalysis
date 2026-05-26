# 大数据集处理指南

**导航**: [文档中心](../../README.md) > [功能特性](../README.md) > [Context 功能](README.md) > 大数据集处理

本文档介绍如何使用 `RecordsBundleRef` 处理 2TB+ 大数据集。

## 概述

### 什么是 RecordsBundleRef

`RecordsBundleRef` 是一种磁盘引用式的数据结构，用于处理超大规模数据集。与传统的 `RecordsBundle`（将所有数据加载到内存）不同，`RecordsBundleRef` 将数据保留在磁盘上，通过 `memmap` 按需加载，避免内存溢出（OOM）。

### 为什么需要它

Run3 实验产生的原始数据可达 2TB+，传统的内存加载方式会导致：
- **内存不足**：无法将全部数据加载到内存
- **处理缓慢**：频繁的内存交换降低性能
- **系统不稳定**：OOM 导致进程崩溃

`RecordsBundleRef` 通过流式处理解决这些问题。

### 与 RecordsBundle 的区别

| 特性 | RecordsBundle | RecordsBundleRef |
|------|---------------|------------------|
| 数据位置 | 内存 | 磁盘（memmap） |
| 内存占用 | 全部数据 | 仅当前 chunk |
| 访问速度 | 快 | 中等 |
| 数据规模 | < 50GB | 无限制 |
| 使用方式 | 直接访问 | 流式迭代 |

### 适用场景

- ✅ 处理 2TB+ V1725 原始数据
- ✅ 内存受限的环境（< 64GB RAM）
- ✅ 需要流式处理的场景
- ✅ 只需要处理部分数据（时间范围过滤）
- ❌ 小数据集（< 10GB）建议使用 RecordsBundle
- ❌ 需要频繁随机访问的场景

## 快速开始

### 最简单的使用

```python
from waveform_analysis.core.processing import build_records_from_v1725_files

# 强制使用磁盘引用模式
ref = build_records_from_v1725_files(
    file_paths=["file1.bin", "file2.bin", "file3.bin"],
    dt_ns=2,
    keep_on_disk=True
)

# 流式处理
for chunk in ref.iter_chunks(chunk_size=100_000):
    # 每次只加载 100k 条记录到内存
    print(f"Processing {len(chunk.records)} records")
    # 处理 chunk.records 和 chunk.wave_pool

# 清理临时文件
ref.cleanup()
```

### 自动模式（推荐）

```python
# 让系统自动决定使用内存还是磁盘
result = build_records_from_v1725_files(
    file_paths=file_list,
    dt_ns=2,
    keep_on_disk=None,  # 自动模式
    memory_budget_gb=50.0
)

if isinstance(result, RecordsBundle):
    # 小数据集，已加载到内存
    process_all(result.records, result.wave_pool)
else:
    # 大数据集，使用流式处理
    for chunk in result.iter_chunks():
        process_chunk(chunk)
    result.cleanup()
```

## 核心概念

### 内存模式 vs 磁盘模式

系统根据数据量自动选择处理模式：

#### 决策逻辑

```python
# 估算数据大小
total_size_gb = (total_records * 记录大小 + total_samples * 2) / (1024³)

if keep_on_disk is None:
    # 自动模式
    if total_size_gb >= memory_budget_gb:
        使用磁盘模式
    else:
        使用内存模式
elif keep_on_disk is True:
    # 强制磁盘模式
    使用磁盘模式
else:
    # 强制内存模式
    使用内存模式
```

#### 性能权衡

| 维度 | 内存模式 | 磁盘模式 |
|------|---------|---------|
| 速度 | 快（直接内存访问） | 中等（memmap + 磁盘 I/O） |
| 内存占用 | 高（全部数据） | 低（仅当前 chunk） |
| 数据规模限制 | 受内存限制 | 无限制 |
| 临时磁盘占用 | 无 | 约等于数据大小 |

#### 何时使用哪种模式

**使用内存模式**：
- 数据量 < 50GB
- 有足够的内存（数据量 × 1.5）
- 需要频繁随机访问
- 追求最快处理速度

**使用磁盘模式**：
- 数据量 > 50GB
- 内存受限
- 流式处理场景
- 只需要处理部分数据

**使用自动模式**（推荐）：
```python
result = build_records_from_v1725_files(
    ...,
    keep_on_disk=None,  # 自动选择
    memory_budget_gb=50.0  # 设置阈值
)
```

### 临时目录管理

#### 自动创建和清理

磁盘模式会在 `/tmp` 下创建临时目录：

```
/tmp/v1725_parts_xxxxx/          ← 顶层临时目录
├── records_0.dat                ← 原始分片
├── wave_pool_0.dat
├── records_1.dat
├── wave_pool_1.dat
└── merged/                      ← 最终合并输出
    ├── records_merged_0.dat     ← 全局排序的最终文件
    └── wave_pool_merged_0.dat
```

#### temp_dir 的生命周期

```python
ref = build_records_from_v1725_files(..., keep_on_disk=True)

# ref.temp_dir 指向临时目录
print(f"Temp dir: {ref.temp_dir}")

# 使用完毕后清理
ref.cleanup()  # 删除整个 temp_dir

# 或者依赖 Python 垃圾回收（不推荐）
del ref  # __del__ 会自动调用 cleanup()
```

#### 手动清理方法

```python
# 方法 1: 显式调用 cleanup()
ref = build_records_from_v1725_files(..., keep_on_disk=True)
try:
    for chunk in ref.iter_chunks():
        process(chunk)
finally:
    ref.cleanup()  # 确保清理

# 方法 2: 手动删除（不推荐）
import shutil
if ref.temp_dir and ref.temp_dir.exists():
    shutil.rmtree(ref.temp_dir)
```

### 全局排序保证

#### 排序契约

无论内存模式还是磁盘模式，都保证 records 按以下键全局排序：

```python
(timestamp, pid, board, channel)
```

这意味着：
1. 首先按 `timestamp` 升序
2. 相同 `timestamp` 按 `pid` 升序
3. 相同 `pid` 按 `board` 升序
4. 相同 `board` 按 `channel` 升序

#### 堆合并算法

系统使用堆合并（heap merge）算法保证全局排序：

```python
# 伪代码
heap = []
for part in parts:
    heapq.heappush(heap, (part[0].timestamp, part[0].pid, ...))

while heap:
    key, part_idx, row_idx = heapq.heappop(heap)
    output[out_idx] = parts[part_idx][row_idx]
    if row_idx + 1 < len(parts[part_idx]):
        heapq.heappush(heap, next_key)
```

#### 验证排序

```python
ref = build_records_from_v1725_files(..., keep_on_disk=True)
records = ref.load_full().records

# 验证全局排序
for i in range(1, len(records)):
    prev = records[i-1]
    curr = records[i]
    assert (prev['timestamp'], prev['pid'], prev['board'], prev['channel']) <= \
           (curr['timestamp'], curr['pid'], curr['board'], curr['channel'])
```

## API 参考

### build_records_from_v1725_files()

```python
def build_records_from_v1725_files(
    file_paths: list[str],
    dt_ns: int,
    n_jobs: int | None = None,
    executor_type: str = "thread",
    memory_budget_gb: float = 50.0,
    batch_size: int = 50,
    keep_on_disk: bool | None = None,
) -> RecordsBundle | RecordsBundleRef
```

#### 参数说明

- **file_paths** (`list[str]`): V1725 文件路径列表
- **dt_ns** (`int`): 采样间隔（纳秒）
- **n_jobs** (`int | None`): 并行 worker 数量
  - `None`: 自动选择（通常为 CPU 核心数）
  - `1`: 串行处理
  - `> 1`: 并行处理
- **executor_type** (`str`): 执行器类型
  - `"thread"`: 线程池（默认，适合 I/O 密集）
  - `"process"`: 进程池（适合 CPU 密集）
- **memory_budget_gb** (`float`): 内存预算阈值（GB）
  - 默认 `50.0`
  - 数据量超过此值时自动切换到磁盘模式
- **batch_size** (`int`): 批处理大小
  - 默认 `50`
  - 控制分批合并时每批的分片数量
  - 越大合并次数越少，但单次合并内存占用越高
- **keep_on_disk** (`bool | None`): 强制选择模式
  - `None`: 自动模式（推荐）
  - `True`: 强制磁盘引用模式
  - `False`: 强制内存模式

#### 返回值

- **RecordsBundle**: 内存模式，数据已加载到内存
- **RecordsBundleRef**: 磁盘模式，数据保留在磁盘上

### RecordsBundleRef 类

```python
@dataclass
class RecordsBundleRef:
    part_refs: list[_RecordsPartRef]
    total_records: int
    total_samples: int
    temp_dir: Path | None
```

#### 方法

##### iter_chunks()

流式迭代分块数据。

```python
def iter_chunks(
    self,
    chunk_size: int = 100_000,
    time_range: tuple[int, int] | None = None,
) -> Iterator[RecordsBundle]
```

**参数**：
- `chunk_size`: 每块的记录数（默认 100k）
- `time_range`: 可选的时间范围过滤 `(start_time, end_time)`

**返回**：`RecordsBundle` 迭代器

**内存占用**：单个 chunk 约 200MB（100k events × 1k samples × 2 bytes）

**示例**：
```python
for chunk in ref.iter_chunks(chunk_size=50_000):
    print(f"Chunk: {len(chunk.records)} records")
    process(chunk.records, chunk.wave_pool)
```

##### load_full()

完整加载到内存。

```python
def load_full(self) -> RecordsBundle
```

⚠️ **警告**：大数据集会导致 OOM

**示例**：
```python
bundle = ref.load_full()
print(f"Total: {len(bundle.records)} records")
```

##### get_records_view()

只读取元数据（不加载波形）。

```python
def get_records_view(self) -> np.ndarray
```

**返回**：records 结构化数组（只读 memmap）

**示例**：
```python
records_view = ref.get_records_view()
print(f"Total: {len(records_view)} records")
print(f"Time range: {records_view['timestamp'].min()} - {records_view['timestamp'].max()}")
```

##### cleanup()

手动清理临时目录。

```python
def cleanup(self) -> None
```

**示例**：
```python
ref.cleanup()
assert not ref.temp_dir.exists()
```

## 使用场景

### 场景 1: 处理 2TB+ V1725 数据集

```python
from waveform_analysis.core.processing import build_records_from_v1725_files

# 强制使用磁盘引用模式
ref = build_records_from_v1725_files(
    file_paths=large_file_list,  # 2000+ 文件
    dt_ns=2,
    keep_on_disk=True,
    memory_budget_gb=50.0,
    batch_size=50,
    n_jobs=8  # 8 个并行 worker
)

# 流式处理，每次只加载 100k 条记录
total_processed = 0
for chunk in ref.iter_chunks(chunk_size=100_000):
    # 处理 chunk.records 和 chunk.wave_pool
    result = process_chunk(chunk)
    total_processed += len(chunk.records)
    print(f"Processed: {total_processed} / {ref.total_records}")

# 清理临时文件
ref.cleanup()
print(f"Total processed: {total_processed} records")
```

### 场景 2: 自动模式（推荐）

```python
# 让系统自动决定使用内存还是磁盘
result = build_records_from_v1725_files(
    file_paths=file_list,
    dt_ns=2,
    keep_on_disk=None,  # 自动模式
    memory_budget_gb=50.0
)

if isinstance(result, RecordsBundle):
    # 小数据集，已加载到内存
    print(f"Loaded {len(result.records)} records to memory")
    process_all(result.records, result.wave_pool)
else:
    # 大数据集，使用流式处理
    print(f"Using disk mode for {result.total_records} records")
    for chunk in result.iter_chunks():
        process_chunk(chunk)
    result.cleanup()
```

### 场景 3: 时间范围过滤

```python
ref = build_records_from_v1725_files(
    file_paths=file_list,
    dt_ns=2,
    keep_on_disk=True
)

# 只处理特定时间范围的数据
start_time = 1_000_000_000  # ps
end_time = 2_000_000_000    # ps

print(f"Processing time range: {start_time} - {end_time}")
for chunk in ref.iter_chunks(time_range=(start_time, end_time)):
    # 只会加载时间范围内的数据
    print(f"Chunk time range: {chunk.records['timestamp'].min()} - {chunk.records['timestamp'].max()}")
    process_chunk(chunk)

ref.cleanup()
```

### 场景 4: 只读取元数据

```python
ref = build_records_from_v1725_files(
    file_paths=file_list,
    dt_ns=2,
    keep_on_disk=True
)

# 只读取 records 元数据，不加载波形
records_view = ref.get_records_view()

# 统计信息
print(f"Total records: {len(records_view)}")
print(f"Time range: {records_view['timestamp'].min()} - {records_view['timestamp'].max()}")
print(f"Channels: {np.unique(records_view['channel'])}")
print(f"Boards: {np.unique(records_view['board'])}")

# 清理
ref.cleanup()
```

## 性能优化

### 并行处理

#### 文件级并行

```python
# 使用多个 worker 并行处理文件
ref = build_records_from_v1725_files(
    file_paths=file_list,
    dt_ns=2,
    n_jobs=8,  # 8 个并行 worker
    executor_type="thread"  # 线程池
)
```

**建议**：
- I/O 密集：使用 `executor_type="thread"`
- CPU 密集：使用 `executor_type="process"`
- `n_jobs` 设置为 CPU 核心数的 1-2 倍

#### 批处理大小

```python
# 调整批处理大小
ref = build_records_from_v1725_files(
    file_paths=file_list,
    dt_ns=2,
    batch_size=100,  # 增大批处理大小
    keep_on_disk=True
)
```

**权衡**：
- 越大：合并次数越少，速度越快
- 越小：单次合并内存占用越低

**建议**：
- 内存充足：`batch_size=100`
- 内存受限：`batch_size=20`

### 内存管理

#### 设置合理的内存预算

```python
import psutil

# 获取可用内存
available_gb = psutil.virtual_memory().available / (1024**3)

# 设置为可用内存的 70%
memory_budget = available_gb * 0.7

ref = build_records_from_v1725_files(
    file_paths=file_list,
    dt_ns=2,
    memory_budget_gb=memory_budget,
    keep_on_disk=None  # 自动模式
)
```

#### 控制 chunk 大小

```python
# 降低 chunk_size 减少内存占用
for chunk in ref.iter_chunks(chunk_size=50_000):  # 默认 100k
    process(chunk)
```

**内存占用估算**：
```
chunk_memory = chunk_size × (记录大小 + 平均波形长度 × 2)
            ≈ 50_000 × (128 + 1000 × 2)
            ≈ 100 MB
```

### 磁盘 I/O 优化

#### 使用 SSD 存储临时文件

```python
import os
import tempfile

# 设置临时目录到 SSD
os.environ['TMPDIR'] = '/path/to/ssd/tmp'

ref = build_records_from_v1725_files(
    file_paths=file_list,
    dt_ns=2,
    keep_on_disk=True
)
```

#### 避免频繁的小块读取

```python
# 不推荐：chunk_size 太小
for chunk in ref.iter_chunks(chunk_size=1_000):  # 频繁 I/O
    process(chunk)

# 推荐：合理的 chunk_size
for chunk in ref.iter_chunks(chunk_size=100_000):  # 减少 I/O 次数
    process(chunk)
```

## 最佳实践

### 1. 优先使用自动模式

```python
# ✅ 推荐：让系统自动选择
result = build_records_from_v1725_files(
    ...,
    keep_on_disk=None,
    memory_budget_gb=50.0
)

# ❌ 不推荐：盲目强制磁盘模式
result = build_records_from_v1725_files(
    ...,
    keep_on_disk=True  # 小数据集也用磁盘模式，浪费性能
)
```

### 2. 始终清理临时文件

```python
# ✅ 推荐：使用 try-finally
ref = build_records_from_v1725_files(..., keep_on_disk=True)
try:
    for chunk in ref.iter_chunks():
        process(chunk)
finally:
    ref.cleanup()

# ❌ 不推荐：忘记清理
ref = build_records_from_v1725_files(..., keep_on_disk=True)
for chunk in ref.iter_chunks():
    process(chunk)
# 临时文件残留在 /tmp
```

### 3. 监控内存使用

```python
import psutil

process = psutil.Process()

ref = build_records_from_v1725_files(..., keep_on_disk=True)

for i, chunk in enumerate(ref.iter_chunks()):
    process_chunk(chunk)

    # 每 10 个 chunk 检查一次内存
    if i % 10 == 0:
        memory_gb = process.memory_info().rss / (1024**3)
        print(f"Memory usage: {memory_gb:.2f} GB")

ref.cleanup()
```

### 4. 处理异常

```python
ref = None
try:
    ref = build_records_from_v1725_files(..., keep_on_disk=True)

    for chunk in ref.iter_chunks():
        try:
            process_chunk(chunk)
        except Exception as e:
            print(f"Error processing chunk: {e}")
            # 继续处理下一个 chunk
            continue

except Exception as e:
    print(f"Error building records: {e}")
    raise
finally:
    if ref is not None:
        ref.cleanup()
```

### 5. 记录处理进度

```python
from tqdm import tqdm

ref = build_records_from_v1725_files(..., keep_on_disk=True)

# 计算总 chunk 数
total_chunks = (ref.total_records + chunk_size - 1) // chunk_size

with tqdm(total=ref.total_records, desc="Processing records") as pbar:
    for chunk in ref.iter_chunks(chunk_size=100_000):
        process_chunk(chunk)
        pbar.update(len(chunk.records))

ref.cleanup()
```

## 故障排查

### Q1: 临时文件占用大量磁盘空间

**症状**：
```bash
$ df -h /tmp
Filesystem      Size  Used Avail Use% Mounted on
tmpfs           32G   28G  4.0G  88% /tmp
```

**原因**：
- 忘记调用 `cleanup()`
- 程序异常退出，临时文件未清理

**解决方案**：
```bash
# 查找残留的临时目录
ls -lh /tmp | grep -E "v1725_parts_|records_bundle_ref_"

# 手动清理
rm -rf /tmp/v1725_parts_*
rm -rf /tmp/records_bundle_ref_*
```

**预防**：
```python
# 使用 try-finally 确保清理
try:
    ref = build_records_from_v1725_files(..., keep_on_disk=True)
    process(ref)
finally:
    if ref is not None:
        ref.cleanup()
```

### Q2: 内存不足错误

**症状**：
```
MemoryError: Unable to allocate array
```

**原因**：
- `chunk_size` 太大
- 未使用磁盘模式
- `memory_budget_gb` 设置过高

**解决方案**：
```python
# 1. 降低 chunk_size
for chunk in ref.iter_chunks(chunk_size=50_000):  # 从 100k 降到 50k
    process(chunk)

# 2. 强制使用磁盘模式
ref = build_records_from_v1725_files(
    ...,
    keep_on_disk=True  # 强制磁盘模式
)

# 3. 降低 memory_budget_gb
ref = build_records_from_v1725_files(
    ...,
    memory_budget_gb=20.0  # 从 50GB 降到 20GB
)
```

### Q3: 处理速度慢

**症状**：
- 处理 1TB 数据需要数小时

**原因**：
- 并行度不足
- 临时文件在机械硬盘上
- `batch_size` 太小导致频繁合并

**解决方案**：
```python
# 1. 增加并行度
ref = build_records_from_v1725_files(
    ...,
    n_jobs=16,  # 增加 worker 数量
    executor_type="thread"
)

# 2. 使用 SSD 存储临时文件
import os
os.environ['TMPDIR'] = '/path/to/ssd/tmp'

# 3. 增加 batch_size
ref = build_records_from_v1725_files(
    ...,
    batch_size=100  # 从 50 增加到 100
)
```

### Q4: 排序不正确

**症状**：
```python
# 验证排序失败
for i in range(1, len(records)):
    if records[i-1]['timestamp'] > records[i]['timestamp']:
        print(f"Sorting error at index {i}")
```

**原因**：
- 这不应该发生，系统保证全局排序

**解决方案**：
```python
# 1. 检查是否使用了正确的函数
ref = build_records_from_v1725_files(...)  # ✅ 正确
# 而不是直接操作 _RecordsPartRef

# 2. 报告 bug
# 如果确实出现排序问题，请报告到 GitHub Issues
```

## 内部实现说明

### 三层合并架构

```
输入分片 → 批处理合并 → 全局堆合并 → 输出
  (parts)   (batched)      (to_disk)     (BundleRef)
```

#### 第一层：批处理合并

将大量小分片（如 1000 个）分批合并成中等分片（如 20 个）：

```python
# 每 batch_size 个分片合并成一个
for batch_idx in range(0, len(parts), batch_size):
    batch = parts[batch_idx : batch_idx + batch_size]
    merged = _merge_records_part_refs_to_memory(batch)
    merged_parts.append(_write_records_part(merged, output_dir))
```

#### 第二层：全局堆合并

使用堆合并算法将所有分片全局排序：

```python
import heapq

heap = []
for source_idx, records in enumerate(records_parts):
    if len(records) > 0:
        rec = records[0]
        key = (rec['timestamp'], rec['pid'], rec['board'], rec['channel'], source_idx, 0)
        heapq.heappush(heap, key)

out_idx = 0
while heap:
    _, _, _, _, source_idx, row_idx = heapq.heappop(heap)
    records_out[out_idx] = records_parts[source_idx][row_idx]
    out_idx += 1

    # 推入下一条记录
    if row_idx + 1 < len(records_parts[source_idx]):
        next_rec = records_parts[source_idx][row_idx + 1]
        next_key = (next_rec['timestamp'], ...)
        heapq.heappush(heap, next_key)
```

### 目录结构

```
/tmp/v1725_parts_xxxxx/          ← part_dir (由 RecordsBundleRef.temp_dir 管理)
├── records_0.dat                ← 原始分片（文件级）
├── wave_pool_0.dat
├── records_1.dat
├── wave_pool_1.dat
├── ...
└── merged/                      ← ref_dir (最终输出目录)
    ├── records_merged_0.dat     ← 全局排序的最终文件
    └── wave_pool_merged_0.dat
```

### 数据流

```
V1725 文件
  ↓ iter_waves()
原始波形
  ↓ _build_records_from_wave_list()
RecordsBundle (内存)
  ↓ _write_records_part()
分片文件 (memmap)
  ↓ _merge_records_part_refs_batched()
中间分片 (memmap)
  ↓ _merge_records_part_refs_to_disk()
最终分片 (memmap, 全局排序)
  ↓
RecordsBundleRef
```

## 相关文档

- [数据访问](DATA_ACCESS.md) - Context 数据获取基础
- [插件管理](PLUGIN_MANAGEMENT.md) - 注册和管理插件
- [Agent 入口](../../../AGENTS.md) - 任务导航与约束
- [Agent 文档索引](../../agents/INDEX.md) - agent 专题说明

## 参考

- 源码：`waveform_analysis/core/processing/records_builder.py`
- 测试：`tests/test_records_sorting.py`
