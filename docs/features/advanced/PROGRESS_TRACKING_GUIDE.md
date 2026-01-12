**导航**: [文档中心](../../README.md) > [功能特性](../README.md) > [高级功能](README.md) > 进度追踪

---

# 统一进度追踪系统使用指南

## 概述

WaveformAnalysis 框架提供了统一的进度追踪系统，基于 `tqdm` 实现，支持：

- **装饰器模式** - 使用 `@with_progress` 自动为函数添加进度追踪
- **函数式接口** - 使用 `progress_iter` 和 `progress_map` 包装可迭代对象
- **手动控制** - 使用 `ProgressTracker` 类精确控制进度显示
- **嵌套进度条** - 支持多级嵌套显示

---
- **线程安全** - 每个线程独立的进度追踪器

## 快速开始

### 1. 装饰器模式（推荐）

最简单的使用方式是使用 `@with_progress` 装饰器：

```python
from waveform_analysis.core.foundation.progress import with_progress

# 装饰生成器函数
@with_progress(total=100, desc="Processing items", unit="item")
def process_items():
    for i in range(100):
        # 处理逻辑
        yield i * 2

# 自动显示进度
results = list(process_items())
```

### 2. 函数式接口

对于现有代码，可以使用 `progress_iter` 包装可迭代对象：

```python
from waveform_analysis.core.foundation.progress import progress_iter

data = range(1000)

for item in progress_iter(data, desc="Processing", unit="item"):
    # 处理每个项目
    process(item)
```

### 3. 手动控制

需要精确控制时，使用 `ProgressTracker` 类：

```python
from waveform_analysis.core.foundation.progress import ProgressTracker

with ProgressTracker() as tracker:
    tracker.create_bar("task1", total=100, desc="Task 1", unit="item")

    for i in range(100):
        # 处理逻辑
        process(i)

        # 更新进度
        tracker.update("task1", n=1)

    # 自动关闭（或手动 tracker.close("task1")）
```

## 详细功能

### @with_progress 装饰器

#### 基本用法

```python
@with_progress(total=100, desc="Processing", unit="item")
def process_data():
    for i in range(100):
        yield i
```

#### 参数说明

- `total` (int, optional): 总任务数，可自动推断
- `desc` (str, optional): 进度条描述，默认使用函数名
- `unit` (str): 进度单位，默认 "it"
- `disable` (bool): 是否禁用进度条，默认 False
- `tracker` (ProgressTracker, optional): 自定义追踪器
- `bar_name` (str, optional): 进度条名称，默认使用函数名
- `show_result` (bool): 是否显示完成统计，默认 False
- `**tqdm_kwargs`: 传递给 tqdm 的其他参数

#### 适用场景

**1. 生成器函数**

```python
@with_progress(total=1000, desc="Generating data")
def generate_data():
    for i in range(1000):
        yield process(i)

# 自动显示生成进度
data = list(generate_data())
```

**2. 返回可迭代对象的函数**

```python
@with_progress(desc="Loading files")
def load_files(file_list):
    results = []
    for file in file_list:
        results.append(load_file(file))
    return results

# 自动包装返回值为进度迭代器
files = ["a.csv", "b.csv", "c.csv"]
data = list(load_files(files))
```

**3. 普通函数（显示执行时间）**

```python
@with_progress(desc="Computing", show_result=True)
def expensive_computation(n):
    time.sleep(2)
    return sum(range(n))

# 显示执行时间
result = expensive_computation(1000000)
```

### progress_iter - 包装可迭代对象

为现有的可迭代对象添加进度条，无需修改原有代码：

```python
from waveform_analysis.core.foundation.progress import progress_iter

# 基本用法
data = range(1000)
for item in progress_iter(data, desc="Processing"):
    process(item)

# 自定义参数
for item in progress_iter(
    data,
    total=1000,
    desc="Custom processing",
    unit="items",
    leave=True,  # tqdm 参数
):
    process(item)
```

### progress_map - 带进度的 map 函数

类似内置 `map`，但显示进度：

```python
from waveform_analysis.core.foundation.progress import progress_map

def square(x):
    return x ** 2

data = range(100)
results = progress_map(square, data, desc="Squaring numbers")
```

### ProgressTracker - 手动控制

需要精确控制或嵌套进度条时使用：

#### 创建进度条

```python
tracker = ProgressTracker()
tracker.create_bar(
    "task1",
    total=100,
    desc="Processing",
    unit="item",
    nested=False,  # 是否嵌套
    parent=None,   # 父进度条名称
)
```

#### 更新进度

```python
tracker.update("task1", n=1)  # 增加1
tracker.update("task1", n=10)  # 增加10
```

#### 设置后缀信息

```python
tracker.set_postfix("task1", speed="100 it/s", eta="00:05")
```

#### 更新描述

```python
tracker.set_description("task1", "Processing batch 2")
```

#### 关闭进度条

```python
tracker.close("task1")        # 关闭特定进度条
tracker.close_all()           # 关闭所有进度条
```

### 嵌套进度条

处理批次任务时，可以创建嵌套进度条：

```python
tracker = ProgressTracker()

# 主进度条
tracker.create_bar("batches", total=5, desc="Processing batches")

for batch_id in range(5):
    # 嵌套进度条
    bar_name = f"batch_{batch_id}"
    tracker.create_bar(
        bar_name,
        total=100,
        desc=f"Batch {batch_id}",
        nested=True,
        parent="batches"
    )

    # 处理批次项目
    for i in range(100):
        tracker.update(bar_name, n=1)

    # 关闭嵌套进度条
    tracker.close(bar_name)

    # 更新主进度条
    tracker.update("batches", n=1)

tracker.close("batches")
```

### 全局追踪器

框架提供全局进度追踪器，每个线程独立：

```python
from waveform_analysis.core.foundation.progress import (
    get_global_tracker,
    reset_global_tracker
)

# 获取全局追踪器
tracker = get_global_tracker()

# 使用全局追踪器
tracker.create_bar("task", total=100, desc="Task")

# 重置全局追踪器（清理所有进度条）
reset_global_tracker()
```

## 高级用法

### 自定义追踪器

可以创建独立的追踪器实例：

```python
# 创建禁用显示的追踪器（用于非交互环境）
silent_tracker = ProgressTracker(disable=True)

# 在装饰器中使用自定义追踪器
@with_progress(tracker=silent_tracker, desc="Processing")
def process_items(items):
    for item in items:
        yield item
```

### 计算性能指标

```python
tracker = ProgressTracker()
tracker.create_bar("task", total=1000, desc="Processing")

# ... 执行任务 ...

# 获取已运行时间
elapsed = tracker.get_elapsed_time("task")

# 计算吞吐量
throughput = tracker.calculate_throughput("task")

# 计算预计剩余时间
eta = tracker.calculate_eta("task")
```

### 格式化工具函数

```python
from waveform_analysis.core.foundation.progress import (
    format_time,
    format_throughput
)

# 格式化时间
print(format_time(3665))  # "01:01:05"

# 格式化吞吐量
print(format_throughput(123.456, "items"))  # "123 items/s"
```

## 最佳实践

### 1. 选择合适的接口

- **简单场景** → 使用 `@with_progress` 装饰器
- **现有代码** → 使用 `progress_iter` 包装
- **复杂控制** → 使用 `ProgressTracker` 类

### 2. 设置有意义的描述

```python
# 好的做法
@with_progress(desc="Loading CSV files", unit="file")

# 避免
@with_progress(desc="Processing", unit="it")
```

### 3. 合理使用嵌套

嵌套层级不要超过 3 层，避免显示混乱。

### 4. 线程安全

多线程环境下，每个线程自动获得独立的全局追踪器：

```python
from concurrent.futures import ThreadPoolExecutor

def process_in_thread(data):
    tracker = get_global_tracker()  # 线程独立
    # ... 使用追踪器 ...

with ThreadPoolExecutor(max_workers=4) as executor:
    executor.map(process_in_thread, data_list)
```

### 5. 非交互环境

在日志文件或自动化脚本中，禁用进度显示：

```python
@with_progress(desc="Processing", disable=True)
def process_items():
    # ...
```

或设置环境变量：

```bash
export TQDM_DISABLE=1
```

## 与现有代码集成

### 在批量处理中使用

```python
from waveform_analysis.core.data.export import BatchProcessor
from waveform_analysis.core.foundation.progress import with_progress

class MyBatchProcessor(BatchProcessor):
    @with_progress(desc="Processing runs", unit="run")
    def process_runs(self, run_ids, data_name, **kwargs):
        for run_id in run_ids:
            yield self.process_single_run(run_id, data_name, **kwargs)
```

### 在插件中使用

```python
from waveform_analysis.core.plugins import Plugin
from waveform_analysis.core.foundation.progress import progress_iter

class MyPlugin(Plugin):
    def compute(self, raw_data, run_id):
        results = []
        for record in progress_iter(raw_data, desc=f"Computing {self.provides}"):
            results.append(self.process_record(record))
        return np.array(results)
```

## 故障排除

### 问题1: 进度条不显示

**原因**: 可能在非交互环境（如 Jupyter Notebook 或重定向输出）

**解决**:
```python
# 检查是否被禁用
tracker = ProgressTracker(disable=False)

# 或在 Jupyter 中使用
from tqdm.notebook import tqdm
```

### 问题2: 嵌套进度条显示混乱

**原因**: 嵌套层级过多或父子关系不正确

**解决**:
- 限制嵌套层级在 2-3 层
- 确保正确设置 `parent` 参数
- 按顺序关闭嵌套进度条

### 问题3: 多线程冲突

**原因**: 多个线程使用同一个追踪器实例

**解决**:
- 使用全局追踪器（自动线程隔离）
- 或为每个线程创建独立追踪器

## 示例集合

完整示例请参考：
- `examples/progress_tracking_demo.py` - 完整使用示例
- `tests/test_progress_decorator.py` - 单元测试示例

## API 参考

详细 API 文档请查看源代码注释：
- `waveform_analysis/core/foundation/progress.py`
