# -*- coding: utf-8 -*-
"""
流式处理框架 - 整合 Chunk、Plugin 和 ExecutorManager

受 strax 启发的流式处理系统，支持：
- 数据以 chunk 形式流动
- 插件自动处理 chunk 流
- 自动并行化和资源管理
- 时间边界对齐和验证
"""

from typing import Any, Dict, Generator, Iterator, List, Optional, Tuple, Union

import numpy as np

from ...chunk_utils import (
    Chunk,
    check_chunk_boundaries,
    get_endtime,
)
from ...execution.config import get_config
from .base import Plugin
from ...utils import exporter

export, __all__ = exporter()


class StreamingPlugin(Plugin):
    """
    支持流式处理的插件基类。

    与普通 Plugin 的区别：
    - `compute()` 接收 chunk 迭代器，返回 chunk 迭代器
    - 自动处理时间边界对齐
    - 支持并行处理多个 chunk

    使用方式：
    1. 继承 StreamingPlugin
    2. 重写 `compute_chunk()` 方法处理单个 chunk
    3. 设置 `output_kind = "stream"`（自动设置）
    """

    # 流式处理相关配置
    chunk_size: int = 50000  # 默认 chunk 大小
    parallel: bool = True  # 是否并行处理
    parallel_batch_size: Optional[int] = None  # 并行处理批量大小（None=自动）
    executor_type: str = "thread"  # 执行器类型
    max_workers: Optional[int] = None  # 最大工作线程/进程数
    
    def __init__(self):
        """初始化流式插件，自动设置 output_kind 为 stream"""
        super().__init__()
        self.output_kind = "stream"  # 流式插件总是输出流
    
    def compute_chunk(self, chunk: Chunk, context: Any, run_id: str, **kwargs) -> Chunk:
        """
        处理单个 chunk。
        
        子类应该重写此方法来实现具体的处理逻辑。
        
        Args:
            chunk: 输入 chunk
            context: Context 对象
            run_id: 运行 ID
            **kwargs: 其他参数
            
        Returns:
            处理后的 chunk
        """
        # 默认实现：直接返回（子类应重写）
        return chunk
    
    def compute(
        self, context: Any, run_id: str, show_progress: bool = False, progress_desc: Optional[str] = None, **kwargs
    ) -> Union[Generator[Chunk, None, None], Iterator[Chunk]]:
        """
        流式处理入口：接收 chunk 迭代器，返回 chunk 迭代器。

        默认实现：
        1. 从依赖获取 chunk 流
        2. 对每个 chunk 调用 compute_chunk()
        3. 可选并行处理
        4. 验证时间边界

        Args:
            context: Context 对象
            run_id: 运行 ID
            show_progress: 是否显示进度条
            progress_desc: 进度条描述（默认自动生成）
            **kwargs: 其他参数

        Yields:
            处理后的 chunk
        """
        # 获取依赖的 chunk 流
        input_chunks = self._get_input_chunks(context, run_id, **kwargs)

        # 初始化进度追踪
        tracker = None
        bar_name = None

        if show_progress:
            from waveform_analysis.core.foundation.progress import get_global_tracker
            tracker = get_global_tracker()
            bar_name = f"stream_{self.provides}_{run_id}"
            desc = progress_desc or f"Streaming {self.provides}"
            # 注意：流式处理可能无法预先知道 total，设为 0 表示不确定
            tracker.create_bar(bar_name, total=0, desc=desc, unit="chunk")

        try:
            # 并行处理配置
            if self.parallel and self.max_workers is not None and self.max_workers > 1:
                # 并行处理
                for chunk in self._compute_parallel(input_chunks, context, run_id, **kwargs):
                    if chunk is not None:
                        if tracker and bar_name:
                            tracker.update(bar_name, n=1)
                        yield chunk
            else:
                # 串行处理
                for chunk in input_chunks:
                    result = self.compute_chunk(chunk, context, run_id, **kwargs)
                    if result is not None:
                        # 验证时间边界
                        self._validate_chunk(result)
                        if tracker and bar_name:
                            tracker.update(bar_name, n=1)
                        yield result
        finally:
            # 关闭进度条
            if tracker and bar_name:
                tracker.close(bar_name)
    
    def _get_input_chunks(
        self, context: Any, run_id: str, **kwargs
    ) -> Iterator[Chunk]:
        """
        从依赖获取 chunk 流。
        
        如果依赖是流式插件，直接获取其输出流。
        如果是静态数据，转换为 chunk 流。
        """
        if not self.depends_on:
            # 无依赖，返回空迭代器
            return iter([])
        
        # 获取第一个依赖（简化：只支持单个依赖）
        dep_name = self.depends_on[0]
        dep_data = context.get_data(run_id, dep_name)
        
        # 检查是否是 chunk 流
        if isinstance(dep_data, (Generator, Iterator)):
            # 已经是流，直接返回
            return dep_data
        
        # 静态数据，转换为 chunk 流
        return self._data_to_chunks(dep_data, run_id)
    
    def _data_to_chunks(self, data: Any, run_id: str) -> Iterator[Chunk]:
        """
        将静态数据转换为 chunk 流。
        
        Args:
            data: 静态数据（可以是 numpy 数组、列表等）
            run_id: 运行 ID
            
        Yields:
            Chunk 对象
        """
        if isinstance(data, np.ndarray):
            # NumPy 数组：按 chunk_size 分割
            n = len(data)
            for i in range(0, n, self.chunk_size):
                chunk_data = data[i : i + self.chunk_size]
                if len(chunk_data) == 0:
                    continue
                
                # 计算时间范围
                if "time" in chunk_data.dtype.names:
                    time = chunk_data["time"]
                    endtime = get_endtime(chunk_data)
                    start_time = int(np.min(time))
                    end_time = int(np.max(endtime))
                else:
                    start_time = i
                    end_time = i + len(chunk_data)
                
                yield Chunk(
                    data=chunk_data,
                    start=start_time,
                    end=end_time,
                    run_id=run_id,
                    data_type=self.provides,
                )
        elif isinstance(data, list):
            # 列表：每个元素作为一个 chunk（简化处理）
            for i, item in enumerate(data):
                if isinstance(item, np.ndarray) and len(item) > 0:
                    if "time" in item.dtype.names:
                        time = item["time"]
                        endtime = get_endtime(item)
                        start_time = int(np.min(time))
                        end_time = int(np.max(endtime))
                    else:
                        start_time = i
                        end_time = i + 1
                    
                    yield Chunk(
                        data=item,
                        start=start_time,
                        end=end_time,
                        run_id=run_id,
                        data_type=self.provides,
                    )
        else:
            # 其他类型：包装为单个 chunk
            yield Chunk(
                data=np.array([data]) if not isinstance(data, np.ndarray) else data,
                start=0,
                end=1,
                run_id=run_id,
                data_type=self.provides,
            )
    
    def _compute_parallel(
        self,
        input_chunks: Iterator[Chunk],
        context: Any,
        run_id: str,
        **kwargs
    ) -> Generator[Chunk, None, None]:
        """
        并行处理 chunk 流（优化版：批量处理，避免完全物化）。

        改进：
        - 不再将整个流物化到列表
        - 分批处理：每次处理 batch_size 个 chunk
        - 保持流式处理的内存优势

        Args:
            input_chunks: 输入 chunk 迭代器
            context: Context 对象
            run_id: 运行 ID
            **kwargs: 其他参数

        Yields:
            处理后的 chunk（保持顺序）
        """
        import itertools
        from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed

        # 批量大小：避免完全物化，但保持并行效率
        # 优先使用配置值，否则自动计算（max_workers 的 2-3 倍）
        if self.parallel_batch_size is not None:
            batch_size = self.parallel_batch_size
        else:
            batch_size = max(10, (self.max_workers or 4) * 3)

        # 准备并行处理函数
        def process_chunk(chunk: Chunk) -> Chunk:
            result = self.compute_chunk(chunk, context, run_id, **kwargs)
            if result is not None:
                self._validate_chunk(result)
            return result

        # 选择执行器类型
        executor_cls = ThreadPoolExecutor if self.executor_type == "thread" else ProcessPoolExecutor

        # 分批处理流
        with executor_cls(max_workers=self.max_workers) as executor:
            chunk_iter = iter(input_chunks)

            while True:
                # 取一批 chunk
                batch = list(itertools.islice(chunk_iter, batch_size))
                if not batch:
                    break  # 流已耗尽

                # 提交批量任务
                future_to_idx = {
                    executor.submit(process_chunk, chunk): idx
                    for idx, chunk in enumerate(batch)
                }

                # 收集结果（保持顺序）
                results = [None] * len(batch)
                for future in as_completed(future_to_idx):
                    idx = future_to_idx[future]
                    try:
                        result = future.result()
                        results[idx] = result
                    except Exception as e:
                        # 记录错误但继续处理其他 chunk
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.error(f"Error processing chunk {idx}: {e}")
                        raise  # 重新抛出，让上层处理

                # 按顺序 yield 结果
                for result in results:
                    if result is not None:
                        yield result

    def _validate_chunk(self, chunk: Chunk):
        """
        验证 chunk 的时间边界。
        
        Args:
            chunk: 要验证的 chunk
            
        Raises:
            ValueError: 如果验证失败
        """
        if len(chunk.data) == 0:
            return
        
        # 检查时间边界
        if "time" in chunk.data.dtype.names:
            validation = check_chunk_boundaries(chunk.data, chunk.start, chunk.end)
            if not validation.is_valid:
                raise ValueError(
                    f"Chunk boundary violation in {self.provides}: {validation.errors}"
                )


class StreamingContext:
    """
    流式处理上下文管理器。
    
    整合 chunk、插件和执行器管理器，提供类似 strax 的流式处理体验。
    """
    
    def __init__(
        self,
        context: Any,  # 原始 Context 对象
        run_id: str,
        chunk_size: int = 50000,
        parallel: bool = True,
        executor_config: Optional[Dict[str, Any]] = None,
    ):
        """
        初始化流式处理上下文。
        
        Args:
            context: 原始 Context 对象
            run_id: 运行 ID
            chunk_size: 默认 chunk 大小
            parallel: 是否启用并行处理
            executor_config: 执行器配置
        """
        self.context = context
        self.run_id = run_id
        self.chunk_size = chunk_size
        self.parallel = parallel
        self.executor_config = executor_config or get_config("io_intensive")
    
    def get_stream(
        self,
        data_name: str,
        time_range: Optional[Tuple[int, int]] = None,
        **kwargs
    ) -> Iterator[Chunk]:
        """
        获取数据流。
        
        Args:
            data_name: 数据名称
            time_range: 时间范围 (start, end)，可选
            **kwargs: 其他参数
            
        Yields:
            Chunk 对象
        """
        # 获取插件
        if data_name not in self.context._plugins:
            raise ValueError(f"No plugin registered for '{data_name}'")
        
        plugin = self.context._plugins[data_name]
        
        # 检查是否是流式插件
        if isinstance(plugin, StreamingPlugin):
            # 流式插件：直接获取流
            stream = plugin.compute(self.context, self.run_id, **kwargs)
            
            # 应用时间范围过滤
            if time_range is not None:
                start, end = time_range
                for chunk in stream:
                    # 检查 chunk 是否在时间范围内
                    if chunk.end > start and chunk.start < end:
                        # 裁剪 chunk 到时间范围
                        if chunk.start < start or chunk.end > end:
                            chunk = self._clip_chunk(chunk, start, end)
                        yield chunk
            else:
                yield from stream
        else:
            # 普通插件：获取静态数据并转换为流
            data = self.context.get_data(self.run_id, data_name, **kwargs)
            
            # 创建临时流式插件包装来转换数据
            class TempWrapper(StreamingPlugin):
                def __init__(self, chunk_size, run_id, data_name):
                    super().__init__()
                    self.provides = data_name
                    self.depends_on = []
                    self.chunk_size = chunk_size
            
            wrapper = TempWrapper(self.chunk_size, self.run_id, data_name)
            
            # 转换为流
            stream = wrapper._data_to_chunks(data, self.run_id)
            
            # 应用时间范围过滤
            if time_range is not None:
                start, end = time_range
                for chunk in stream:
                    if chunk.end > start and chunk.start < end:
                        if chunk.start < start or chunk.end > end:
                            chunk = self._clip_chunk(chunk, start, end)
                        yield chunk
            else:
                yield from stream
    
    def _clip_chunk(self, chunk: Chunk, start: int, end: int) -> Chunk:
        """
        裁剪 chunk 到指定时间范围。
        
        Args:
            chunk: 输入 chunk
            start: 起始时间
            end: 结束时间
            
        Returns:
            裁剪后的 chunk
        """
        from ...chunk_utils import select_time_range
        
        if len(chunk.data) == 0:
            return chunk
        
        # 选择时间范围内的数据
        clipped_data = select_time_range(chunk.data, start, end, strict=False)
        
        # 计算新的时间范围
        if len(clipped_data) > 0 and "time" in clipped_data.dtype.names:
            time = clipped_data["time"]
            endtime = get_endtime(clipped_data)
            new_start = max(int(np.min(time)), start)
            new_end = min(int(np.max(endtime)), end)
        else:
            new_start = max(chunk.start, start)
            new_end = min(chunk.end, end)
        
        return Chunk(
            data=clipped_data,
            start=new_start,
            end=new_end,
            run_id=chunk.run_id,
            data_type=chunk.data_type,
            data_kind=chunk.data_kind,
        )
    
    def iter_chunks(
        self,
        data_name: str,
        time_range: Optional[Tuple[int, int]] = None,
        **kwargs
    ) -> Iterator[Chunk]:
        """
        迭代数据流的便捷方法。
        
        Args:
            data_name: 数据名称
            time_range: 时间范围，可选
            **kwargs: 其他参数
            
        Yields:
            Chunk 对象
        """
        yield from self.get_stream(data_name, time_range, **kwargs)
    
    def merge_stream(
        self,
        streams: List[Iterator[Chunk]],
        sort: bool = True
    ) -> Iterator[Chunk]:
        """
        合并多个数据流。
        
        Args:
            streams: 数据流列表
            sort: 是否按时间排序
            
        Yields:
            合并后的 chunk
        """
        from ...chunk_utils import merge_chunks  # sort_by_time is handled by merge_chunks, sort_by_time
        
        # 收集所有 chunk
        all_chunks = []
        for stream in streams:
            for chunk in stream:
                all_chunks.append(chunk.data)
        
        if len(all_chunks) == 0:
            return
        
        # 合并
        merged_data = merge_chunks(iter(all_chunks), sort=sort)
        
        # 计算时间范围
        if len(merged_data) > 0 and "time" in merged_data.dtype.names:
            time = merged_data["time"]
            endtime = get_endtime(merged_data)
            start_time = int(np.min(time))
            end_time = int(np.max(endtime))
        else:
            start_time = 0
            end_time = len(merged_data)
        
        # 返回单个 chunk
        yield Chunk(
            data=merged_data,
            start=start_time,
            end=end_time,
            run_id=self.run_id,
            data_type="merged",
        )


# 便捷函数
@export
def get_streaming_context(
    context: Any,
    run_id: str,
    chunk_size: int = 50000,
    parallel: bool = True,
    executor_config: Optional[Dict[str, Any]] = None,
) -> StreamingContext:
    """
    创建流式处理上下文。
    
    Args:
        context: Context 对象
        run_id: 运行 ID
        chunk_size: 默认 chunk 大小
        parallel: 是否启用并行处理
        executor_config: 执行器配置
        
    Returns:
        StreamingContext 对象
    """
    return StreamingContext(context, run_id, chunk_size, parallel, executor_config)

