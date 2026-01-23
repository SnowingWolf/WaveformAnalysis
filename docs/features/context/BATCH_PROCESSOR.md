**导航**: [文档中心](../../README.md) > [功能特性](../README.md) > [Context 功能](README.md) > BATCH_PROCESSOR

---

# BatchProcessor - 多运行批量处理

## 概述

`BatchProcessor` 用于批量处理多个 `run_id`，内部复用同一个 `Context`，并提供：

- ✅ 并行处理（线程池）
- ✅ 进度跟踪（终端或 Jupyter）
- ✅ 取消执行（CancellationToken）
- ✅ 统一错误收集

它本质上是对 `ctx.get_data(run_id, data_name)` 的批量调度封装。

---

## 适用场景

- 多个 run 需要同一数据类型（如 `peaks`、`st_waveforms`）批量处理
- 需要批量执行并显示进度
- 在 Jupyter 中批量跑数据并保持响应

---

## 快速开始

### 1. 基础用法

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.data.export import BatchProcessor

ctx = Context(config={"data_root": "DAQ", "n_channels": 2})
# ... 注册插件 ...

processor = BatchProcessor(ctx)
result = processor.process_runs(
    run_ids=["run_001", "run_002"],
    data_name="peaks",
    max_workers=4,
    on_error="continue",
)

data_by_run = result["results"]
errors_by_run = result["errors"]
```

### 2. Jupyter 优化模式

```python
result = processor.process_runs(
    run_ids=["run_001", "run_002"],
    data_name="peaks",
    jupyter_mode=True,   # 或 None 自动检测
)
```

### 3. 自定义函数批量执行

```python
def count_peaks(ctx, run_id):
    peaks = ctx.get_data(run_id, "peaks")
    return len(peaks)

stats = processor.process_with_custom_func(
    run_ids=["run_001", "run_002"],
    func=count_peaks,
    max_workers=2,
)
```

---

## API 参考

### 类初始化

```python
BatchProcessor(context: Context)
```

### process_runs

```python
def process_runs(
    run_ids: List[str],
    data_name: str,
    max_workers: Optional[int] = None,
    show_progress: bool = True,
    on_error: str = "continue",      # continue / stop / raise
    progress_tracker: Optional[Any] = None,
    cancellation_token: Optional[Any] = None,
    jupyter_mode: Optional[bool] = None,
    progress_update_interval: float = 0.5,
) -> Dict[str, Any]
```

返回：

```python
{
    "results": {run_id: data},
    "errors": {run_id: exception}
}
```

### process_with_custom_func

```python
def process_with_custom_func(
    run_ids: List[str],
    func: Callable,  # func(context, run_id) -> result
    max_workers: Optional[int] = None,
    show_progress: bool = True,
    progress_tracker: Optional[Any] = None,
    jupyter_mode: Optional[bool] = None,
    progress_update_interval: float = 0.5,
) -> Dict[str, Any]
```

返回：

```python
{run_id: result}
```

---

## 并行与缓存注意事项

1. **线程模型**  
   `BatchProcessor` 使用 `ThreadPoolExecutor`，适合 I/O 密集型任务。

2. **Context 内存缓存增长**  
   同一个 `Context` 批量跑多个 run，内存缓存可能持续增长。  
   建议在批量运行后按需清理：

   ```python
   ctx.clear_cache_for("run_001")
   ```

3. **线程安全建议**  
   `Context` 内部有多个可变缓存结构，严格并发场景建议：
   - `max_workers=1` 串行执行，或
   - 每个线程使用独立 `Context`

4. **性能统计**  
   `stats_collector` 绑定在 `Context` 上。多个 run 的统计会累计在同一个收集器中。

---

## 错误与取消

- `on_error="continue"`：记录错误并继续
- `on_error="stop"`：遇到错误停止处理
- `on_error="raise"`：直接抛出异常

取消支持（仅 `process_runs`）：

```python
from waveform_analysis.core.cancellation import CancellationToken

token = CancellationToken()
result = processor.process_runs(
    run_ids=["run_001", "run_002"],
    data_name="peaks",
    cancellation_token=token,
)

# 需要时取消
token.cancel()
```

---

## 常见问题

### Q: BatchProcessor 和手动 for 循环有什么区别？

BatchProcessor 只是把多次 `ctx.get_data` 组织成批量执行，并提供并行、进度与取消。

### Q: 为什么推荐 max_workers=1？

Context 不是为多线程强一致场景设计的。  
如果必须并行，建议每个线程使用独立 Context。
