"""
BatchProcessingPlugin - 批量流处理插件基类

这是 StreamingPlugin 的语义化别名，专门用于批量流处理场景：
- 输入：有限的大数据集（np.ndarray, RecordsBundle, RecordsBundleRef）
- 输出：完整的结果数组（np.ndarray）
- 处理方式：自动分块 + 并行处理 + 结果合并

与 StreamingPlugin 的区别：
- StreamingPlugin：实时流处理（无限数据流，输入/输出都是 chunk 流）
- BatchProcessingPlugin：批量流处理（有限大数据集，输入是数组，输出是数组）

使用场景：
- 处理大型 waveform 数据集（避免一次性加载到内存）
- 处理 RecordsBundleRef（磁盘支持的流式 records）
- 需要并行处理以提高性能

示例：
    class MyBatchPlugin(BatchProcessingPlugin):
        provides = "my_output"
        depends_on = ["st_waveforms"]
        chunk_size = 10_000  # 每个 chunk 处理 10k 条记录
        parallel = True

        def compute_chunk(self, chunk, context, run_id, **kwargs):
            # 处理单个 chunk
            data = chunk.data
            result = process_data(data)
            return Chunk(data=result, start=chunk.start, end=chunk.end, ...)

        def compute_array(self, context, run_id, **kwargs):
            # 向后兼容接口：返回完整数组
            chunk_stream = super().compute(context, run_id, **kwargs)
            all_results = []
            for chunk in chunk_stream:
                if len(chunk.data) > 0:
                    all_results.append(chunk.data)
            return np.concatenate(all_results) if all_results else np.zeros(0, dtype=self.output_dtype)
"""

from typing import Any

import numpy as np

from waveform_analysis.core.foundation.utils import exporter
from waveform_analysis.core.plugins.core.streaming import StreamingPlugin
from waveform_analysis.core.processing.chunk import Chunk, get_endtime

export, __all__ = exporter()


@export
class BatchProcessingPlugin(StreamingPlugin):
    """
    批量流处理插件基类

    这是 StreamingPlugin 的语义化封装，专门用于批量流处理场景。

    核心特性：
    1. **自动分块**：将大数据集自动分割成 chunks
    2. **并行处理**：每个 chunk 可以并行处理
    3. **内存友好**：避免一次性加载所有数据到内存
    4. **向后兼容**：提供 compute_array() 接口返回完整数组

    配置选项（继承自 StreamingPlugin）：
    - chunk_size: 每个 chunk 的大小（默认 50000）
    - parallel: 是否并行处理（默认 True）
    - executor_type: 执行器类型 "thread" 或 "process"（默认 "thread"）
    - max_workers: 最大工作线程数（默认 None = CPU 核心数）

    子类需要实现：
    - compute_chunk(chunk, context, run_id, **kwargs) -> Chunk
      处理单个 chunk 并返回结果 chunk

    可选实现：
    - compute_array(context, run_id, **kwargs) -> np.ndarray
      返回完整数组（默认实现会自动合并所有 chunks）

    使用模式：

    模式 1：简单批处理（无状态）
    ```python
    class SimplePlugin(BatchProcessingPlugin):
        provides = "output"
        depends_on = ["input"]
        chunk_size = 10_000

        def compute_chunk(self, chunk, context, run_id, **kwargs):
            result = process(chunk.data)
            return Chunk(data=result, start=chunk.start, end=chunk.end, ...)
    ```

    模式 2：通道分组批处理
    ```python
    class ChannelPlugin(BatchProcessingPlugin):
        provides = "output"
        depends_on = ["st_waveforms"]
        chunk_size = 10_000

        def compute_chunk(self, chunk, context, run_id, **kwargs):
            # 在 chunk 内按通道分组
            data = chunk.data
            boards = data["board"]
            channels = data["channel"]

            # 按通道批处理
            results = []
            for (board, channel) in unique_channels(boards, channels):
                mask = (boards == board) & (channels == channel)
                channel_data = data[mask]
                channel_result = process_channel(channel_data, board, channel)
                results.append(channel_result)

            merged = merge_results(results)
            return Chunk(data=merged, start=chunk.start, end=chunk.end, ...)
    ```

    模式 3：动态依赖
    ```python
    class DynamicPlugin(BatchProcessingPlugin):
        provides = "output"
        depends_on = []  # 动态解析

        def resolve_depends_on(self, context, run_id=None):
            # 根据配置动态决定依赖
            use_filtered = context.get_config(self, "use_filtered")
            return ["filtered_waveforms"] if use_filtered else ["st_waveforms"]

        def compute_chunk(self, chunk, context, run_id, **kwargs):
            ...
    ```
    """

    # 默认配置：适合批量处理
    chunk_size = 50_000  # 较大的 chunk size，减少开销
    parallel = True  # 默认并行
    executor_type = "thread"  # 线程池（适合 I/O 密集型）
    max_workers = None  # 自动检测 CPU 核心数

    # 批量处理通常是无状态的
    is_stateful = False

    # 输出类型：静态数组
    output_kind = "static"

    def __init__(self):
        super().__init__()
        self.output_kind = "static"

    def compute_array(self, context: Any, run_id: str, **kwargs) -> np.ndarray:
        """
        向后兼容的数组接口 - 返回 np.ndarray 而不是生成器

        这个方法保持与旧版本 Plugin 的兼容性，调用流式 compute() 并合并结果。

        Args:
            context: Context 对象
            run_id: 运行 ID
            **kwargs: 其他参数

        Returns:
            合并后的完整数组
        """
        depends_on = (
            self.resolve_depends_on(context, run_id)
            if hasattr(self, "resolve_depends_on")
            else self.depends_on
        )
        if len(depends_on) != 1:
            raise ValueError(
                "BatchProcessingPlugin.compute_array requires exactly one input dependency"
            )
        data_name = depends_on[0]
        data = context.get_data(run_id, data_name)
        if not isinstance(data, np.ndarray):
            raise ValueError(f"{self.provides} expects {data_name} as a structured numpy array")
        if len(data) == 0:
            if self.output_dtype is not None:
                return np.zeros(0, dtype=self.output_dtype)
            return np.array([])

        all_results = []
        chunk_size = max(1, int(getattr(self, "chunk_size", len(data))))
        for start_idx in range(0, len(data), chunk_size):
            chunk_data = data[start_idx : start_idx + chunk_size]
            chunk = self._make_chunk(chunk_data, run_id, data_name)
            result = self.compute_chunk(chunk, context, run_id, **kwargs)
            result_data = result.data if isinstance(result, Chunk) else result
            if len(result_data) > 0:
                all_results.append(result_data)

        if not all_results:
            # 返回空数组
            if self.output_dtype is not None:
                return np.zeros(0, dtype=self.output_dtype)
            else:
                return np.array([])

        # 合并所有结果
        return np.concatenate(all_results)

    def _make_chunk(self, data: np.ndarray, run_id: str, data_name: str) -> Chunk:
        names = data.dtype.names or ()
        time_field = self.time_field if self.time_field in names else "timestamp"
        start = int(np.min(data[time_field]))
        end = int(
            get_endtime(
                data,
                time_field=time_field,
                endtime_field=self.endtime_field,
                dt_field=self.dt_field,
                length_field=self.length_field,
                dt=self.dt,
            ).max()
        )
        return Chunk(
            data=data,
            start=start,
            end=end,
            run_id=run_id,
            data_type=data_name,
            time_field=time_field,
            dt_field=self.dt_field,
            length_field=self.length_field,
            endtime_field=self.endtime_field,
            dt=self.dt,
        )

    # compute() 方法继承自 StreamingPlugin，不需要重写
    # 默认行为：
    # 1. 从依赖获取数据（自动处理 np.ndarray / RecordsBundleRef）
    # 2. 分割成 chunks
    # 3. 并行调用 compute_chunk()
    # 4. 返回 chunk 流


# 导出别名，方便使用
__all__.extend(["BatchProcessingPlugin"])
