# 全局执行器管理框架 - 设计总结

## 架构设计

### 核心组件

1. **ExecutorManager** (单例模式)
   - 统一管理所有线程池和进程池
   - 支持执行器重用和引用计数
   - 自动资源清理

2. **ExecutorConfig** (配置模块)
   - 预定义常用配置模板
   - 支持自定义配置注册

3. **便捷函数**
   - `get_executor()`: 上下文管理器
   - `parallel_map()`: 并行map操作
   - `parallel_apply()`: 并行apply操作

## 设计原则

### 1. 单例模式
- 全局唯一的管理器实例
- 确保资源统一管理

### 2. 引用计数
- 自动跟踪执行器使用次数
- 引用计数为0时自动清理

### 3. 资源重用
- 相同配置的执行器可以重用
- 减少创建和销毁开销

### 4. 自动清理
- 程序退出时自动关闭所有执行器
- 使用 `atexit` 注册清理函数

### 5. 线程安全
- 使用锁保护共享资源
- 支持多线程环境

## 使用场景

### 场景1: 文件IO（线程池）

```python
from waveform_analysis.core.executor_manager import get_executor

with get_executor("file_io", "thread", max_workers=10) as ex:
    futures = [ex.submit(load_file, f) for f in files]
    data = [f.result() for f in futures]
```

### 场景2: CPU计算（进程池）

```python
with get_executor("computation", "process", max_workers=8) as ex:
    futures = [ex.submit(heavy_compute, data) for data in datasets]
    results = [f.result() for f in futures]
```

### 场景3: 使用预定义配置

```python
from waveform_analysis.core.executor_manager import get_executor
from waveform_analysis.core.executor_config import get_config

config = get_config("cpu_intensive")
with get_executor("my_task", **config) as ex:
    ...
```

### 场景4: 并行map

```python
from waveform_analysis.core.executor_manager import parallel_map

results = parallel_map(process_item, items, executor_type="process", max_workers=4)
```

## 集成点

### 已集成的模块

1. **processor.py**
   - `group_multi_channel_hits()` 使用执行器管理器进行多进程处理

2. **loader.py**
   - `load_waveforms()` 使用执行器管理器进行通道级并行

3. **io.py**
   - `parse_and_stack_files()` 使用执行器管理器进行文件解析并行

## 性能优势

1. **减少创建开销**
   - 重用执行器避免重复创建
   - 引用计数确保及时清理

2. **统一管理**
   - 集中管理所有执行器
   - 便于监控和调试

3. **自动优化**
   - 根据任务类型自动选择执行器
   - 预定义配置优化常见场景

## 扩展性

### 添加新配置

```python
from waveform_analysis.core.executor_config import register_config

register_config("my_custom", {
    "executor_type": "process",
    "max_workers": 16,
    "reuse": True,
})
```

### 自定义执行器

```python
from waveform_analysis.core.executor_manager import get_executor_manager

manager = get_executor_manager()
executor = manager.get_executor("custom", "process", max_workers=4, custom_param=value)
```

## 监控和调试

### 查看执行器状态

```python
from waveform_analysis.core.executor_manager import get_executor_manager, get_stats

# 获取统计信息
stats = get_stats()
print(f"活跃执行器: {stats['total_executors']}")

# 列出所有执行器
manager = get_executor_manager()
executors = manager.list_executors()
for name, info in executors.items():
    print(f"{name}: {info}")
```

## 最佳实践

1. **使用上下文管理器**
   - 始终使用 `with` 语句
   - 确保资源正确释放

2. **合理选择执行器类型**
   - IO密集型 → thread
   - CPU密集型 → process

3. **重用执行器**
   - 频繁使用的执行器设置 `reuse=True`
   - 减少创建开销

4. **监控资源使用**
   - 定期检查执行器状态
   - 及时清理不用的执行器

## 故障排除

### 问题1: 执行器未关闭

**原因**: 没有使用上下文管理器或忘记释放

**解决**: 使用 `with` 语句或手动调用 `release_executor()`

### 问题2: 内存泄漏

**原因**: 执行器引用计数未正确减少

**解决**: 检查是否正确使用上下文管理器

### 问题3: 性能不佳

**原因**: 执行器类型选择不当

**解决**: 
- IO任务使用 thread
- CPU任务使用 process
- 调整 max_workers 参数

