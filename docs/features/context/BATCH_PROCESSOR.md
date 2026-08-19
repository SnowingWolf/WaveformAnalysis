**导航**: [文档中心](../../README.md) > [功能特性](../README.md) > [Context 功能](README.md) > BATCH_PROCESSOR

---

# BatchProcessor - 多运行批量处理

## 概述

`BatchProcessor` 是 `Context` 的多 run 调度工具。它把多次
`ctx.get_data(run_id, data_name)` 组织成统一的批量执行，并补充：

- 线程或进程并行
- 终端 / Jupyter 进度显示
- 取消执行
- 错误收集、跳过状态与重试信息
- 自定义 per-run 函数和配置网格扫描

`BatchProcessor` 不改变插件 DAG、缓存 lineage 或数据产物语义。单个 run 的真实计算仍然由
`Context` 和插件系统完成；它只负责把多个 run 的执行、进度和结果汇总起来。

并行模式下每个任务应使用独立 `Context`，避免共享可变缓存。当前实现支持自动工厂：

- `executor_type="thread"` 且未传 `context_factory` 时，会尝试使用 `ctx.clone()`
- `executor_type="process"` 且未传 `context_factory` 时，会尝试使用 `ctx.create_context_factory()`
- 如果无法解析出工厂函数，会回退到串行执行并记录 warning

---

## 适用场景

- 多个 `run_id` 需要获取同一种插件产物，例如 `records`、`basic_features`、`hit_threshold`
- 需要保留每个 run 的成功、失败、耗时和重试次数
- 需要在 notebook 或终端中显示批量进度
- 需要对每个 run 执行同一个自定义统计函数
- 需要对同一组 runs 扫描多组插件配置

---

## 推荐用法

### 完整流程（含插件注册）

从注册插件到批量获取结果的完整示例：

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.data import BatchProcessor
from waveform_analysis.core.plugins import profiles

ctx = Context(storage_dir='./strax_data')
ctx.register(*profiles.cpu_default())
ctx.set_config({'data_root': 'DAQ', 'daq_adapter': 'vx2730'})

processor = BatchProcessor(ctx)
results = processor.process_runs(
    run_ids=['run_001', 'run_002', 'run_003'],
    data_name='basic_features',
    max_workers=4,
    show_progress=True,
    on_error='continue',  # 'continue' / 'stop' / 'raise'
)

for run_id, data in results['results'].items():
    print(f"{run_id}: {len(data)} events")
if results['errors']:
    print(f"Errors: {results['errors']}")
```

### 串行批量获取

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.data import BatchProcessor

ctx = Context(config={"data_root": "DAQ", "daq_adapter": "vx2730"})
# ... 注册插件 ...

processor = BatchProcessor(ctx)
result = processor.process_runs(
    run_ids=["run_001", "run_002"],
    data_name="basic_features",
    max_workers=1,
    show_progress=True,
)
```

结果按 run 分组：

```python
for run_id in result["ordered_run_ids"]:
    meta = result["meta"][run_id]
    if meta["status"] == "success":
        data = result["results"][run_id]
        print(run_id, len(data), meta["elapsed"])
    else:
        print(run_id, meta["status"], result["errors"].get(run_id))
```

### Notebook 中运行

```python
result = processor.process_runs(
    run_ids=["run_001", "run_002"],
    data_name="basic_features",
    jupyter_mode=True,
)
```

`jupyter_mode=None` 时会自动检测环境。显式设置为 `True` 会使用轮询等待和简单进度输出，避免
notebook 中的阻塞式 `as_completed` 行为。

### 自定义 per-run 函数

```python
def count_peaks(ctx, run_id):
    peaks = ctx.get_data(run_id, "basic_features")
    return len(peaks)

stats = processor.process_func(
    run_ids=["run_001", "run_002"],
    func=count_peaks,
    max_workers=2,
)
```

`process_func` 的函数签名固定为 `func(context, run_id) -> result`。函数内部可以继续调用
`ctx.get_data()`，也可以做统计、筛选或导出前转换。

### 并行执行

```python
def make_context():
    ctx = Context(config={"data_root": "DAQ", "daq_adapter": "vx2730"})
    # ... 注册插件 ...
    return ctx

result = processor.process_runs(
    run_ids=["run_001", "run_002"],
    data_name="basic_features",
    max_workers=4,
    context_factory=make_context,
    executor_type="thread",
)
```

线程池适合 I/O 密集型任务。进程池适合 CPU 密集型任务，但 `context_factory` 必须可 pickle：

```python
result = processor.process_runs(
    run_ids=["run_001", "run_002"],
    data_name="basic_features",
    max_workers=4,
    context_factory=ctx.create_context_factory(),
    executor_type="process",
)
```

### 配置网格扫描

```python
result = processor.process_runs_with_config_grid(
    run_ids=["run_001", "run_002"],
    data_name="basic_features",
    plugin_name="basic_features",
    configs=[
        {"threshold": 10},
        {"threshold": 20},
    ],
    max_workers=1,
)
```

返回结果按配置分组，每一项都包含配置索引、配置内容和一次完整的 batch 结果：

```python
for item in result["results"]:
    print(item["config_index"], item["config"])
    print(item["batch"]["meta"])
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
    context_factory: Optional[Callable[[], Context]] = None,
    executor_type: str = "thread",
    storage_dir_strategy: str = "shared",
    clean_temp_cache: bool = True,
    show_progress: bool = True,
    on_error: str = "continue",      # continue / stop / raise
    progress_tracker: Optional[Any] = None,
    cancellation_token: Optional[Any] = None,
    jupyter_mode: Optional[bool] = None,
    progress_update_interval: float = 0.5,
    poll_interval: float = 0.1,
    retries: int = 0,
    retry_on: Optional[Tuple[type, ...]] = None,
) -> Dict[str, Any]
```

`context_factory` 可选：thread 模式会自动使用 `ctx.clone()`，process 模式建议使用
`ctx.create_context_factory()`。

返回结构：

```python
{
    "results": {run_id: data},
    "errors": {run_id: {"type": ..., "message": ..., "traceback": ...}},
    "meta": {run_id: {"status": "...", "elapsed": ..., "attempts": ...}},
    "ordered_run_ids": [...]
}
```

`meta[run_id]["status"]` 可能为：

| 状态 | 含义 |
|------|------|
| `success` | 该 run 成功写入 `results` |
| `failed` | 该 run 失败，错误写入 `errors` |
| `cancelled` | 当前任务收到取消异常 |
| `skipped` | 因取消或 `on_error="stop"` 未继续执行 |

### process_func

```python
def process_func(
    run_ids: List[str],
    func: Callable,  # func(context, run_id) -> result
    max_workers: Optional[int] = None,
    context_factory: Optional[Callable[[], Context]] = None,
    executor_type: str = "thread",
    storage_dir_strategy: str = "shared",
    clean_temp_cache: bool = True,
    show_progress: bool = True,
    on_error: str = "continue",
    progress_tracker: Optional[Any] = None,
    jupyter_mode: Optional[bool] = None,
    progress_update_interval: float = 0.5,
    poll_interval: float = 0.1,
    retries: int = 0,
    retry_on: Optional[Tuple[type, ...]] = None,
) -> Dict[str, Any]
```

返回结构与 `process_runs` 一致，但 `results[run_id]` 是 `func(context, run_id)` 的返回值。

注意：取消令牌当前只在 `process_runs` 的公开参数中提供；`process_func` 没有
`cancellation_token` 参数。

---

### process_runs_with_config_grid

```python
def process_runs_with_config_grid(
    run_ids: List[str],
    data_name: str,
    plugin_name: str,
    configs: List[Dict[str, Any]],
    max_workers: Optional[int] = None,
    context_factory: Optional[Callable[[], Context]] = None,
    executor_type: str = "thread",
    storage_dir_strategy: str = "shared",
    clean_temp_cache: bool = True,
    show_progress: bool = True,
    on_error: str = "continue",
    jupyter_mode: Optional[bool] = None,
    progress_update_interval: float = 0.5,
    poll_interval: float = 0.1,
    retries: int = 0,
    retry_on: Optional[Tuple[type, ...]] = None,
    tmp_cache: bool = False,
) -> Dict[str, Any]
```

返回结构：

```python
{
    "results": [
        {
            "config_index": 0,
            "config": {...},
            "batch": {
                "results": {run_id: data},
                "errors": {...},
                "meta": {...},
                "ordered_run_ids": [...],
            },
        },
        ...
    ],
    "configs": [...],
}
```

---

## 并行与缓存注意事项

1. **优先从串行开始**
   `max_workers=1` 最容易排查问题，也不会共享 `Context` 的可变状态。

2. **并行时使用独立 Context**
   `Context` 内部包含运行时缓存和统计状态。并行执行时应提供 `context_factory`，或依赖
   `ctx.clone()` / `ctx.create_context_factory()` 的自动解析。

3. **执行器选择**
   `executor_type="thread"` 适合 I/O 密集型任务；`executor_type="process"` 适合 CPU 密集型任务，
   但要求工厂函数和任务参数可 pickle。

4. **缓存目录策略**
   `storage_dir_strategy="shared"` 使用共享缓存目录。`"per_worker"` 和 `"readonly"` 会为 worker
   准备临时缓存目录；串行模式下这些策略会被忽略并回到 `"shared"`。

5. **Context 内存缓存增长**
   同一个 `Context` 批量跑多个 run，内存缓存可能持续增长。
   建议在批量运行后按需清理：

   ```python
   ctx.clear_cache_for("run_001")
   ```

6. **性能统计**
   `stats_collector` 绑定在 `Context` 上。多个 run 的统计会累计在同一个收集器中。

---

## 错误与取消

- `on_error="continue"`：记录错误并继续
- `on_error="stop"`：遇到错误停止处理
- `on_error="raise"`：直接抛出异常
- `retries` / `retry_on`：只对匹配 `retry_on` 的异常类型重试

失败信息会写入 `errors[run_id]`，包含异常类型、消息和 traceback。每个 run 的尝试次数写入
`meta[run_id]["attempts"]`。

取消支持仅适用于 `process_runs`：

```python
from waveform_analysis.core.cancellation import CancellationToken

token = CancellationToken()
result = processor.process_runs(
    run_ids=["run_001", "run_002"],
    data_name='basic_features',
    cancellation_token=token,
)

# 需要时取消
token.cancel()
```

取消后，尚未执行的 run 会在 `meta` 中标记为 `skipped`。

---

## 常见问题

### Q: BatchProcessor 和手动 for 循环有什么区别？

BatchProcessor 只是把多次 `ctx.get_data` 组织成批量执行，并提供并行、进度与取消。

### Q: 为什么推荐 max_workers=1？

Context 不是为多线程强一致场景设计的。
如果必须并行，建议每个线程使用独立 Context。

### Q: 什么时候用 process_func？

当每个 run 的结果不是单个插件产物，而是需要先读取多个产物再计算统计量、摘要或导出前数据时，使用
`process_func`。

### Q: errors 里有失败时，results 是否还能使用？

可以。`results` 只包含成功的 run，失败详情在 `errors`，完整执行状态看 `meta`。
