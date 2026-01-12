**导航**: [文档中心](../../README.md) > [功能特性](../README.md) > [数据处理](README.md) > 流式处理

---

# 流式处理框架指南

本文档介绍如何使用流式处理框架，将 Chunk、Plugin 和 ExecutorManager 结合起来，实现类似 strax 的流式数据处理。

---

## 概述

流式处理框架的核心思想：
- **数据以 chunk 形式流动**：数据被分割成时间对齐的 chunk，逐个处理
- **插件处理 chunk 流**：每个插件接收 chunk 流，处理后输出新的 chunk 流
- **自动并行化**：系统自动将 chunk 分发到多个工作线程/进程处理
- **时间边界对齐**：确保 chunk 的时间边界正确，保证处理正确性

## 核心组件

### 1. StreamingPlugin

`StreamingPlugin` 是支持流式处理的插件基类。与普通 `Plugin` 的区别：

- `compute()` 方法返回 chunk 迭代器（而不是静态数据）
- 自动处理时间边界对齐和验证
- 支持并行处理多个 chunk
- `output_kind` 自动设置为 `"stream"`

**基本用法**：

```python
from waveform_analysis.core.streaming import StreamingPlugin
from waveform_analysis.core.chunk_utils import Chunk

class MyStreamingPlugin(StreamingPlugin):
    provides = "my_stream"
    depends_on = ["input_stream"]
    
    def compute_chunk(self, chunk: Chunk, context, run_id, **kwargs) -> Chunk:
        """
        处理单个 chunk。
        
        Args:
            chunk: 输入 chunk
            context: Context 对象
            run_id: 运行 ID
            
        Returns:
            处理后的 chunk
        """
        # 处理逻辑
        processed_data = process_data(chunk.data)
        
        # 返回新 chunk（保持时间边界）
        return Chunk(
            data=processed_data,
            start=chunk.start,
            end=chunk.end,
            run_id=run_id,
            data_type=self.provides,
        )
```

### 2. StreamingContext

`StreamingContext` 是流式处理的上下文管理器，提供：

- 获取数据流：`get_stream()`
- 迭代 chunk：`iter_chunks()`
- 合并多个流：`merge_stream()`
- 时间范围过滤：自动裁剪 chunk 到指定时间范围

**基本用法**：

```python
from waveform_analysis.core.streaming import get_streaming_context

# 创建流式处理上下文
stream_ctx = get_streaming_context(
    context=ctx,  # 原始 Context 对象
    run_id="my_run",
    chunk_size=50000,  # 默认 chunk 大小
    parallel=True,  # 启用并行处理
)

# 获取数据流
for chunk in stream_ctx.get_stream("my_stream"):
    print(f"Processing chunk: {chunk.start} - {chunk.end}, {len(chunk)} records")
    # 处理 chunk...
```

### 3. 并行处理配置

`StreamingPlugin` 支持自动并行处理：

```python
class MyParallelPlugin(StreamingPlugin):
    # 配置并行处理
    parallel = True  # 启用并行
    executor_type = "process"  # 使用进程池（CPU 密集型）或 "thread"（IO 密集型）
    max_workers = 4  # 最大工作线程/进程数
    chunk_size = 50000  # chunk 大小
```

## 完整示例

### 示例 1：流式特征提取

```python
from waveform_analysis.core.streaming import StreamingPlugin, get_streaming_context
from waveform_analysis.core.chunk_utils import Chunk
from waveform_analysis.core.processor import WaveformProcessor
import numpy as np

class StreamingFeaturesPlugin(StreamingPlugin):
    provides = "features_stream"
    depends_on = ["st_waveforms_stream"]
    
    def __init__(self):
        super().__init__()
        self.peaks_range = (40, 90)
        self.charge_range = (60, 400)
    
    def compute_chunk(self, chunk: Chunk, context, run_id, **kwargs) -> Chunk:
        """从结构化波形计算特征"""
        if len(chunk.data) == 0:
            return None
        
        processor = WaveformProcessor(n_channels=1)
        event_length = np.full(len(chunk.data), len(chunk.data))
        peaks, charges = processor.compute_basic_features(
            [chunk.data],
            event_length,
            self.peaks_range,
            self.charge_range,
        )
        
        # 创建特征数组
        feature_dtype = np.dtype([
            ("time", "<i8"),
            ("peak", "<f4"),
            ("charge", "<f4"),
        ])
        
        n = len(peaks[0])
        features = np.zeros(n, dtype=feature_dtype)
        features["time"] = chunk.data["time"][:n]
        features["peak"] = peaks[0]
        features["charge"] = charges[0]
        
        return Chunk(
            data=features,
            start=chunk.start,
            end=chunk.end,
            run_id=run_id,
            data_type=self.provides,
        )

# 使用
ctx.register(StreamingFeaturesPlugin())
stream_ctx = get_streaming_context(ctx, "my_run")

for chunk in stream_ctx.get_stream("features_stream"):
    print(f"Chunk: {chunk.start}-{chunk.end}, {len(chunk)} features")
```

### 示例 2：时间范围过滤

```python
# 只处理特定时间范围的数据
time_range = (1000000, 2000000)  # 纳秒

for chunk in stream_ctx.get_stream("features_stream", time_range=time_range):
    # chunk 已自动裁剪到时间范围
    process_chunk(chunk)
```

### 示例 3：合并多个流

```python
# 获取多个数据流
stream1 = stream_ctx.get_stream("stream1")
stream2 = stream_ctx.get_stream("stream2")

# 合并流
merged = stream_ctx.merge_stream([stream1, stream2], sort=True)

for chunk in merged:
    # 处理合并后的数据
    process_chunk(chunk)
```

## 与现有系统的集成

### 将普通插件转换为流式插件

普通插件返回静态数据，流式插件返回 chunk 流。转换步骤：

1. **继承 `StreamingPlugin`**：
   ```python
   class MyStreamingPlugin(StreamingPlugin):
       provides = "my_stream"
       depends_on = ["input_data"]
   ```

2. **重写 `compute_chunk()`**：
   ```python
   def compute_chunk(self, chunk: Chunk, context, run_id, **kwargs) -> Chunk:
       # 处理单个 chunk
       processed = process(chunk.data)
       return Chunk(data=processed, start=chunk.start, end=chunk.end, ...)
   ```

3. **注册插件**：
   ```python
   ctx.register(MyStreamingPlugin())
   ```

### 混合使用静态和流式插件

系统支持混合使用：
- 流式插件可以依赖静态数据（自动转换为 chunk 流）
- 静态插件可以依赖流式数据（需要先合并流）

```python
# 流式插件依赖静态数据
class StreamFromStatic(StreamingPlugin):
    depends_on = ["static_data"]  # 静态数据会自动转换为流

# 静态插件依赖流式数据（需要先获取完整数据）
class StaticFromStream(Plugin):
    depends_on = ["stream_data"]  # 需要先合并流
```

## 性能优化

### 1. 选择合适的 chunk 大小

- **小 chunk**：内存占用低，但并行开销大
- **大 chunk**：并行效率高，但内存占用大
- **推荐**：根据数据特征调整，通常 10K-100K 记录

```python
plugin.chunk_size = 50000  # 根据实际情况调整
```

### 2. 并行处理配置

- **IO 密集型**：使用 `executor_type="thread"`
- **CPU 密集型**：使用 `executor_type="process"`
- **工作线程数**：通常设置为 CPU 核心数

```python
plugin.executor_type = "process"  # CPU 密集型
plugin.max_workers = 8  # 8 个进程
```

### 3. 时间范围过滤

在处理大数据集时，使用时间范围过滤可以显著减少处理量：

```python
# 只处理感兴趣的时间范围
time_range = (start_time, end_time)
for chunk in stream_ctx.get_stream("data", time_range=time_range):
    process(chunk)
```

## 最佳实践

1. **保持时间边界**：处理 chunk 时，确保输出 chunk 的时间边界正确
2. **验证数据**：使用 `_validate_chunk()` 自动验证时间边界
3. **错误处理**：在 `compute_chunk()` 中处理异常，返回 `None` 跳过无效 chunk
4. **内存管理**：及时释放不需要的数据，避免内存泄漏
5. **日志记录**：在处理大量 chunk 时，记录处理进度

## 与 strax 的对比

| 特性 | strax | WaveformAnalysis Streaming |
|------|-------|----------------------------|
| 数据流 | Chunk 流 | Chunk 流 |
| 插件系统 | Plugin | StreamingPlugin |
| 并行处理 | 自动 | 自动（可配置） |
| 时间对齐 | 自动 | 自动 |
| 缓存 | 支持 | 支持（通过 Context） |
| 执行器管理 | 内置 | ExecutorManager |

## 总结

流式处理框架提供了：
- ✅ 类似 strax 的流式处理体验
- ✅ 自动并行化和资源管理
- ✅ 时间边界对齐和验证
- ✅ 与现有插件系统无缝集成
- ✅ 灵活的执行器配置

通过使用流式处理框架，可以：
- 降低内存占用（数据以 chunk 形式流动）
- 提高处理效率（自动并行化）
- 简化代码（自动处理时间边界）
- 提高可维护性（清晰的插件接口）

