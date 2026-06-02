# BatchProcessingPlugin 使用指南

## 概述

`BatchProcessingPlugin` 是专门为**批量流处理**场景设计的插件基类。它是 `StreamingPlugin` 的语义化封装，提供了：

- ✅ **自动分块**：将大数据集自动分割成可管理的 chunks
- ✅ **并行处理**：每个 chunk 可以并行处理，充分利用多核 CPU
- ✅ **内存友好**：避免一次性加载所有数据到内存
- ✅ **向后兼容**：提供 `compute_array()` 接口返回完整数组

## 何时使用

### 适用场景

使用 `BatchProcessingPlugin` 当你需要：

1. **处理大型数据集**（> 100k 条记录）
   - 避免内存溢出
   - 提高处理速度

2. **处理 RecordsBundleRef**（磁盘支持的流式 records）
   - 自动流式加载
   - 无需手动管理分块

3. **并行处理以提高性能**
   - 自动多线程/多进程
   - 无需手动管理线程池

### 不适用场景

**不要**使用 `BatchProcessingPlugin` 当：

1. **数据集很小**（< 10k 条记录）
   - 使用普通 `Plugin` 更简单
   - 分块开销大于收益

2. **需要实时流处理**（无限数据流）
   - 使用 `StreamingPlugin` 更合适
   - 输入/输出都是 chunk 流

3. **处理逻辑有状态依赖**
   - 需要跨 chunk 的状态管理
   - 考虑使用 `StreamingPlugin` 的 `is_stateful = True`

---

## 基本用法

### 最简单的例子

```python
from waveform_analysis.core.plugins.core import BatchProcessingPlugin, Option
from waveform_analysis.core.processing.chunk import Chunk
import numpy as np

class SimpleThresholdPlugin(BatchProcessingPlugin):
    """简单的阈值检测插件"""

    provides = "simple_hits"
    depends_on = ["st_waveforms"]

    # 配置
    chunk_size = 10_000  # 每个 chunk 处理 10k 条记录
    parallel = True      # 并行处理

    options = {
        "threshold": Option(default=10.0, type=float, help="检测阈值"),
    }

    def compute_chunk(self, chunk, context, run_id, **kwargs):
        """处理单个 chunk"""
        # 1. 获取配置
        threshold = float(context.get_config(self, "threshold"))

        # 2. 处理数据
        data = chunk.data
        waves = data["wave"]
        baselines = data["baseline"]

        # 3. 检测超过阈值的点
        hits = []
        for i, (wave, baseline) in enumerate(zip(waves, baselines)):
            signal = np.abs(wave - baseline)
            if np.max(signal) > threshold:
                hits.append({
                    "record_id": data["record_id"][i],
                    "max_signal": np.max(signal),
                })

        # 4. 返回结果
        result = np.array(hits, dtype=[("record_id", np.int64), ("max_signal", np.float32)])
        return Chunk(data=result, start=chunk.start, end=chunk.end,
                    run_id=run_id, data_type=self.provides)
```

### 使用插件

```python
from waveform_analysis.core import Context

# 创建 context 并注册插件
ctx = Context()
ctx.register_plugin(SimpleThresholdPlugin())

# 调用插件（自动批处理）
hits = ctx.get_data("run_001", "simple_hits")
print(f"Found {len(hits)} hits")
```

---

## 高级用法

### 1. 通道分组批处理

在 chunk 内按硬件通道分组处理：

```python
class ChannelAwarePlugin(BatchProcessingPlugin):
    """按通道分组处理的插件"""

    provides = "channel_features"
    depends_on = ["st_waveforms"]
    chunk_size = 10_000

    def compute_chunk(self, chunk, context, run_id, **kwargs):
        data = chunk.data
        boards = data["board"]
        channels = data["channel"]

        # 找到所有唯一的 (board, channel) 组合
        unique_channels = np.unique(np.column_stack([boards, channels]), axis=0)

        results = []
        for board, channel in unique_channels:
            # 选择该通道的数据
            mask = (boards == board) & (channels == channel)
            channel_data = data[mask]

            # 处理该通道
            channel_result = self._process_channel(channel_data, board, channel)
            results.append(channel_result)

        # 合并结果
        merged = np.concatenate(results) if results else np.zeros(0, dtype=self.output_dtype)
        return Chunk(data=merged, start=chunk.start, end=chunk.end,
                    run_id=run_id, data_type=self.provides)

    def _process_channel(self, data, board, channel):
        """处理单个通道的数据"""
        # 通道特定的处理逻辑
        ...
```

### 2. 动态依赖解析

根据配置动态决定依赖：

```python
class FlexiblePlugin(BatchProcessingPlugin):
    """支持动态依赖的插件"""

    provides = "flexible_output"
    depends_on = []  # 动态解析

    options = {
        "use_filtered": Option(default=False, type=bool,
                              help="是否使用滤波后的波形"),
    }

    def resolve_depends_on(self, context, run_id=None):
        """动态解析依赖"""
        use_filtered = context.get_config(self, "use_filtered")
        if use_filtered:
            return ["filtered_waveforms"]
        else:
            return ["st_waveforms"]

    def compute_chunk(self, chunk, context, run_id, **kwargs):
        # 处理逻辑
        ...
```

### 3. 自定义 chunk_size

根据数据特征动态调整 chunk_size：

```python
class AdaptivePlugin(BatchProcessingPlugin):
    """自适应 chunk_size 的插件"""

    provides = "adaptive_output"
    depends_on = ["st_waveforms"]

    options = {
        "target_memory_mb": Option(default=100, type=int,
                                   help="目标内存使用（MB）"),
    }

    def __init__(self):
        super().__init__()
        # 根据配置动态设置 chunk_size
        # 假设每条记录约 1KB
        target_mb = 100  # 可以从配置读取
        self.chunk_size = (target_mb * 1024 * 1024) // 1024

    def compute_chunk(self, chunk, context, run_id, **kwargs):
        # 处理逻辑
        ...
```

### 4. 使用辅助函数

利用现有的辅助函数简化代码：

```python
from waveform_analysis.core.plugins.builtin.cpu._wave_source import (
    load_wave_input,
    resolve_wave_input_spec,
)

class WaveSourcePlugin(BatchProcessingPlugin):
    """使用 wave_source 辅助函数的插件"""

    provides = "wave_output"
    depends_on = []  # 动态解析

    options = {
        "wave_source": Option(default="auto", type=str,
                             choices=["auto", "records", "st_waveforms", "filtered_waveforms"]),
        "use_filtered": Option(default=False, type=bool),
    }

    def resolve_depends_on(self, context, run_id=None):
        """使用辅助函数解析依赖"""
        spec = resolve_wave_input_spec(context, self)
        return list(spec.depends_on)

    def compute_chunk(self, chunk, context, run_id, **kwargs):
        # 使用辅助函数加载波形数据
        wave_input = load_wave_input(
            context, self, run_id,
            needs_wave_samples=True,
            allow_records_bundle_ref=True
        )

        # 处理逻辑
        ...
```

---

## 配置选项

### 继承自 StreamingPlugin 的配置

`BatchProcessingPlugin` 继承了 `StreamingPlugin` 的所有配置选项：

| 选项 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `chunk_size` | int | 50000 | 每个 chunk 的大小（记录数） |
| `parallel` | bool | True | 是否并行处理 |
| `executor_type` | str | "thread" | 执行器类型（"thread" 或 "process"） |
| `max_workers` | int | None | 最大工作线程数（None = CPU 核心数） |
| `parallel_batch_size` | int | None | 并行批次大小 |

### 推荐配置

**小数据集**（< 50k 条记录）：
```python
chunk_size = 10_000
parallel = False  # 开销大于收益
```

**中等数据集**（50k - 500k 条记录）：
```python
chunk_size = 50_000
parallel = True
executor_type = "thread"
max_workers = 4
```

**大数据集**（> 500k 条记录）：
```python
chunk_size = 100_000
parallel = True
executor_type = "process"  # CPU 密集型
max_workers = None  # 自动检测
```

**I/O 密集型**（读取磁盘文件）：
```python
chunk_size = 20_000
parallel = True
executor_type = "thread"  # 线程更适合 I/O
max_workers = 8
```

---

## 性能优化

### 1. 选择合适的 chunk_size

**太小**：
- ❌ 分块开销大
- ❌ 并行效率低
- ❌ 内存碎片多

**太大**：
- ❌ 内存占用高
- ❌ 并行度低
- ❌ 响应延迟高

**推荐**：
- ✅ 根据数据大小调整
- ✅ 目标：每个 chunk 处理时间 0.1-1 秒
- ✅ 经验值：10k - 100k 条记录

### 2. 选择合适的 executor_type

**thread（线程池）**：
- ✅ 适合 I/O 密集型（读取文件、网络请求）
- ✅ 启动快，开销小
- ❌ 受 GIL 限制，CPU 密集型性能差

**process（进程池）**：
- ✅ 适合 CPU 密集型（数值计算、信号处理）
- ✅ 绕过 GIL，充分利用多核
- ❌ 启动慢，开销大
- ❌ 需要数据序列化（pickle）

### 3. 减少内存拷贝

```python
def compute_chunk(self, chunk, context, run_id, **kwargs):
    # ❌ 避免不必要的拷贝
    data_copy = chunk.data.copy()

    # ✅ 直接使用原始数据
    data = chunk.data

    # ✅ 使用 copy=False 避免拷贝
    waves = np.asarray(data["wave"], dtype=np.float32, copy=False)
```

### 4. 使用 NumPy 向量化

```python
# ❌ 慢：Python 循环
results = []
for wave in waves:
    result = process_wave(wave)
    results.append(result)

# ✅ 快：NumPy 向量化
results = np.apply_along_axis(process_wave, axis=1, arr=waves)

# ✅ 更快：纯 NumPy 操作
results = (waves - baselines[:, np.newaxis]).max(axis=1)
```

---

## 测试

### 单元测试

```python
import pytest
import numpy as np
from tests.utils import DummyContext

def test_simple_threshold_plugin():
    plugin = SimpleThresholdPlugin()

    # 创建测试数据
    n_events = 100
    wave_len = 64
    dtype = [
        ("record_id", np.int64),
        ("baseline", np.float32),
        ("wave", np.int16, (wave_len,)),
    ]
    data = np.zeros(n_events, dtype=dtype)
    data["record_id"] = np.arange(n_events)
    data["baseline"] = 100.0
    data["wave"] = 100

    # 添加一些超过阈值的信号
    data["wave"][10, 20:30] = 120  # 超过阈值 10

    # 创建 context
    ctx = DummyContext(
        config={"threshold": 10.0},
        data={"st_waveforms": data}
    )

    # 调用插件
    result = plugin.compute_array(ctx, "run_001")

    # 验证结果
    assert len(result) == 1
    assert result[0]["record_id"] == 10
    assert result[0]["max_signal"] > 10.0
```

### 性能测试

```python
import time

def test_batch_processing_performance():
    plugin = SimpleThresholdPlugin()

    # 创建大数据集
    n_events = 100_000
    data = create_test_data(n_events)

    ctx = DummyContext(
        config={"threshold": 10.0},
        data={"st_waveforms": data}
    )

    # 测试不同配置
    configs = [
        {"chunk_size": 10_000, "parallel": False},
        {"chunk_size": 10_000, "parallel": True},
        {"chunk_size": 50_000, "parallel": True},
    ]

    for config in configs:
        plugin.chunk_size = config["chunk_size"]
        plugin.parallel = config["parallel"]

        start = time.time()
        result = plugin.compute_array(ctx, "run_001")
        elapsed = time.time() - start

        print(f"Config {config}: {elapsed:.2f}s, {len(result)} hits")
```

---

## 常见问题

### Q1: BatchProcessingPlugin vs StreamingPlugin？

**BatchProcessingPlugin**：
- 输入：有限数据集（数组）
- 输出：完整数组
- 场景：离线批量处理

**StreamingPlugin**：
- 输入：chunk 流（可能无限）
- 输出：chunk 流
- 场景：实时流处理

### Q2: 如何处理 RecordsBundleRef？

`BatchProcessingPlugin` 自动处理 `RecordsBundleRef`：

```python
# 不需要手动检测和处理
def compute_chunk(self, chunk, context, run_id, **kwargs):
    # chunk.data 已经是加载好的数据
    data = chunk.data
    # 直接处理即可
    ...
```

### Q3: 如何调试 chunk 边界问题？

```python
def compute_chunk(self, chunk, context, run_id, **kwargs):
    import logging
    logger = logging.getLogger(__name__)

    logger.debug(f"Processing chunk: start={chunk.start}, end={chunk.end}, "
                f"n_records={len(chunk.data)}")

    # 处理逻辑
    ...
```

### Q4: 如何处理空 chunk？

```python
def compute_chunk(self, chunk, context, run_id, **kwargs):
    if len(chunk.data) == 0:
        # 返回空结果
        return Chunk(
            data=np.zeros(0, dtype=self.output_dtype),
            start=chunk.start,
            end=chunk.end,
            run_id=run_id,
            data_type=self.provides
        )

    # 正常处理
    ...
```

---

## 迁移指南

### 从 Plugin 迁移到 BatchProcessingPlugin

**旧代码**（Plugin）：
```python
class OldPlugin(Plugin):
    provides = "output"
    depends_on = ["st_waveforms"]

    def compute(self, context, run_id, **kwargs):
        data = context.get_data(run_id, "st_waveforms")

        # 手动批处理
        chunk_size = 10_000
        results = []
        for i in range(0, len(data), chunk_size):
            chunk = data[i:i+chunk_size]
            result = process_chunk(chunk)
            results.append(result)

        return np.concatenate(results)
```

**新代码**（BatchProcessingPlugin）：
```python
class NewPlugin(BatchProcessingPlugin):
    provides = "output"
    depends_on = ["st_waveforms"]
    chunk_size = 10_000
    parallel = True

    def compute_chunk(self, chunk, context, run_id, **kwargs):
        # 自动批处理
        result = process_chunk(chunk.data)
        return Chunk(data=result, start=chunk.start, end=chunk.end,
                    run_id=run_id, data_type=self.provides)

    def compute_array(self, context, run_id, **kwargs):
        # 向后兼容
        return super().compute_array(context, run_id, **kwargs)
```

**优势**：
- ✅ 自动分块，无需手动管理
- ✅ 自动并行，提高性能
- ✅ 自动处理 RecordsBundleRef
- ✅ 更少的代码，更清晰的逻辑

---

## 总结

`BatchProcessingPlugin` 提供了一个简单而强大的方式来处理大数据集：

1. **继承 `BatchProcessingPlugin`**
2. **实现 `compute_chunk()`** - 处理单个 chunk
3. **配置 `chunk_size` 和 `parallel`** - 优化性能
4. **可选实现 `compute_array()`** - 向后兼容

这样你就可以专注于业务逻辑，而不用担心分块、并行和内存管理的细节。
