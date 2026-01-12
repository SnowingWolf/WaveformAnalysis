**导航**: [文档中心](../../README.md) > [功能特性](../README.md) > [高级功能](README.md) > 执行器管理

---

# 全局执行器管理框架使用指南

## 概述

全局执行器管理框架提供统一的接口来管理线程池和进程池，支持资源重用、自动清理和配置管理。

---

## 核心特性

1. **单例模式**：全局唯一的管理器实例
2. **资源重用**：相同配置的执行器可以重用，减少创建开销
3. **自动清理**：程序退出时自动关闭所有执行器
4. **线程安全**：支持多线程环境下的安全访问
5. **引用计数**：自动管理执行器生命周期

## 基本使用

### 1. 使用上下文管理器（推荐）

```python
from waveform_analysis.core.executor_manager import get_executor
from concurrent.futures import as_completed

# 使用线程池
with get_executor("my_task", "thread", max_workers=4) as ex:
    futures = [ex.submit(process_item, item) for item in items]
    results = [f.result() for f in as_completed(futures)]

# 使用进程池
with get_executor("my_task", "process", max_workers=4) as ex:
    futures = [ex.submit(compute_intensive, data) for data in datasets]
    results = [f.result() for f in as_completed(futures)]
```

### 2. 使用便捷函数

```python
from waveform_analysis.core.executor_manager import parallel_map, parallel_apply

# parallel_map: 类似map，但并行执行
results = parallel_map(process_file, file_list, executor_type="process", max_workers=4)

# parallel_apply: 支持多参数
args_list = [(x, y) for x, y in zip(xs, ys)]
results = parallel_apply(process_pair, args_list, executor_type="process", max_workers=4)
```

### 3. 使用预定义配置

```python
from waveform_analysis.core.executor_manager import get_executor
from waveform_analysis.core.executor_config import get_config

# 使用预定义配置
config = get_config("cpu_intensive")  # 或 "io_intensive", "large_data" 等
with get_executor("my_task", **config) as ex:
    futures = [ex.submit(heavy_computation, data) for data in datasets]
    results = [f.result() for f in futures]
```

## 预定义配置

框架提供了以下预定义配置：

| 配置名称 | 执行器类型 | 用途 |
|---------|-----------|------|
| `io_intensive` | thread | IO密集型任务（文件读取、网络请求） |
| `cpu_intensive` | process | CPU密集型任务（计算、数据处理） |
| `large_data` | process | 大数据处理（8个进程） |
| `small_data` | thread | 小数据快速处理（4个线程） |
| `waveform_loading` | thread | 波形文件加载（10个线程） |
| `event_grouping` | process | 事件聚类处理（自动） |
| `feature_computation` | process | 特征计算（自动） |

## 高级用法

### 1. 执行器重用

```python
from waveform_analysis.core.executor_manager import get_executor

# 第一次使用：创建执行器
with get_executor("shared_task", "process", max_workers=4, reuse=True) as ex1:
    futures1 = [ex1.submit(task1, item) for item in items1]
    results1 = [f.result() for f in futures1]

# 第二次使用：重用同一个执行器（如果还在使用中）
with get_executor("shared_task", "process", max_workers=4, reuse=True) as ex2:
    futures2 = [ex2.submit(task2, item) for item in items2]
    results2 = [f.result() for f in futures2]
```

### 2. 手动管理执行器

```python
from waveform_analysis.core.executor_manager import get_executor_manager

manager = get_executor_manager()

# 获取执行器
executor = manager.get_executor("my_task", "process", max_workers=4)

# 使用执行器
futures = [executor.submit(process, item) for item in items]
results = [f.result() for f in futures]

# 释放执行器（引用计数减1）
manager.release_executor("my_task", "process", max_workers=4)

# 或直接关闭
manager.shutdown_executor("my_task", "process", max_workers=4)
```

### 3. 查看执行器状态

```python
from waveform_analysis.core.executor_manager import get_executor_manager

manager = get_executor_manager()

# 列出所有活跃的执行器
executors = manager.list_executors()
print(executors)

# 获取统计信息
stats = manager.get_stats()
print(f"总执行器数: {stats['total_executors']}")
print(f"线程执行器: {stats['thread_executors']}")
print(f"进程执行器: {stats['process_executors']}")
```

### 4. 配置默认工作线程数

```python
from waveform_analysis.core.executor_manager import configure_default_workers

# 设置默认值为8
configure_default_workers(8)

# 或使用CPU核心数（默认）
configure_default_workers()  # 使用 multiprocessing.cpu_count()
```

## 集成到现有代码

### 在 processor.py 中的使用

```python
# 旧代码
with ProcessPoolExecutor(max_workers=n_processes) as executor:
    ...

# 新代码（使用全局管理器）
from waveform_analysis.core.executor_manager import get_executor

with get_executor("event_grouping", "process", max_workers=n_processes, reuse=True) as executor:
    ...
```

### 在 loader.py 中的使用

```python
# 旧代码
ExecutorCls = ProcessPoolExecutor if channel_executor == "process" else ThreadPoolExecutor
with ExecutorCls(max_workers=channel_workers) as ex:
    ...

# 新代码
from waveform_analysis.core.executor_manager import get_executor

with get_executor("channel_loading", channel_executor, max_workers=channel_workers, reuse=True) as ex:
    ...
```

## 最佳实践

### 1. 选择合适的执行器类型

- **IO密集型**（文件读取、网络请求）：使用 `thread`
- **CPU密集型**（计算、数据处理）：使用 `process`

### 2. 合理设置工作线程/进程数

```python
import multiprocessing

# IO密集型：可以设置较多线程（如2-4倍CPU核心数）
max_workers = multiprocessing.cpu_count() * 2

# CPU密集型：通常等于CPU核心数
max_workers = multiprocessing.cpu_count()
```

### 3. 使用上下文管理器

始终使用 `with` 语句确保资源正确释放：

```python
# ✅ 推荐
with get_executor("task", "process", max_workers=4) as ex:
    results = [ex.submit(func, arg).result() for arg in args]

# ❌ 不推荐（需要手动管理）
executor = manager.get_executor("task", "process", max_workers=4)
# ... 使用执行器 ...
manager.release_executor("task", "process", max_workers=4)
```

### 4. 重用执行器

对于频繁使用的执行器，设置 `reuse=True` 以减少创建开销：

```python
# 重用执行器（适合多次调用）
with get_executor("frequent_task", "process", max_workers=4, reuse=True) as ex:
    ...
```

### 5. 错误处理

```python
from concurrent.futures import as_completed

with get_executor("task", "process", max_workers=4) as ex:
    futures = {ex.submit(process, item): item for item in items}
    results = {}
    
    for future in as_completed(futures):
        item = futures[future]
        try:
            results[item] = future.result()
        except Exception as e:
            print(f"处理 {item} 时出错: {e}")
            results[item] = None
```

## 性能优化

### 1. 执行器重用

重用执行器可以避免重复创建的开销：

```python
# 第一次：创建执行器（较慢）
with get_executor("task", "process", max_workers=4, reuse=True) as ex:
    ...

# 后续：重用执行器（较快）
with get_executor("task", "process", max_workers=4, reuse=True) as ex:
    ...
```

### 2. 批量处理

对于大量小任务，使用批量提交：

```python
with get_executor("task", "process", max_workers=4) as ex:
    # 批量提交所有任务
    futures = [ex.submit(process, item) for item in items]
    
    # 批量收集结果
    results = [f.result() for f in futures]
```

### 3. 异步处理

使用 `as_completed` 处理完成的任务，而不是等待所有任务：

```python
with get_executor("task", "process", max_workers=4) as ex:
    futures = {ex.submit(process, item): item for item in items}
    
    # 处理完成的任务（不等待所有任务）
    for future in as_completed(futures):
        item = futures[future]
        result = future.result()
        # 立即处理结果
        process_result(result)
```

## 故障排除

### 1. 执行器未关闭

如果执行器没有正确关闭，程序退出时会有警告。确保使用上下文管理器：

```python
# ✅ 正确
with get_executor("task", "process", max_workers=4) as ex:
    ...

# ❌ 错误
ex = manager.get_executor("task", "process", max_workers=4)
# 忘记释放
```

### 2. 内存泄漏

如果长时间运行的程序出现内存问题：

```python
# 定期清理不用的执行器
manager = get_executor_manager()
for name in list(manager.list_executors().keys()):
    if manager._executor_refs[name] == 0:
        manager.shutdown_executor(name)
```

### 3. 进程池创建失败

在某些系统上，进程池创建可能失败：

```python
try:
    with get_executor("task", "process", max_workers=4) as ex:
        ...
except Exception as e:
    # 回退到线程池
    with get_executor("task", "thread", max_workers=4) as ex:
        ...
```

## 示例：完整工作流

```python
from waveform_analysis.core.executor_manager import get_executor, parallel_map
from waveform_analysis.core.executor_config import get_config
from concurrent.futures import as_completed

# 1. 使用预定义配置加载文件（IO密集型）
io_config = get_config("waveform_loading")
with get_executor("file_loading", **io_config) as ex:
    futures = {ex.submit(load_file, f): f for f in files}
    data = {f: fut.result() for f, fut in futures.items()}

# 2. 使用并行map处理数据（CPU密集型）
cpu_config = get_config("cpu_intensive")
results = parallel_map(
    process_data,
    list(data.values()),
    **cpu_config
)

# 3. 使用自定义配置进行特征计算
with get_executor("feature_compute", "process", max_workers=8, reuse=True) as ex:
    futures = [ex.submit(compute_features, item) for item in results]
    features = [f.result() for f in as_completed(futures)]
```

## API 参考

### ExecutorManager

- `get_executor(name, executor_type, max_workers, reuse, **kwargs)` - 获取执行器
- `release_executor(name, executor_type, max_workers)` - 释放执行器
- `shutdown_executor(name, executor_type, max_workers, wait)` - 关闭执行器
- `shutdown_all(wait)` - 关闭所有执行器
- `list_executors()` - 列出所有执行器
- `get_stats()` - 获取统计信息

### 便捷函数

- `get_executor(...)` - 上下文管理器形式的执行器获取
- `parallel_map(func, iterable, ...)` - 并行map
- `parallel_apply(func, args_list, ...)` - 并行apply
- `configure_default_workers(max_workers)` - 配置默认工作线程数

