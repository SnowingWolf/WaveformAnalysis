# -*- coding: utf-8 -*-
"""
流式处理框架 - 整合 Chunk、Plugin 和 ExecutorManager。

受 strax 启发的流式处理系统，主要特性：
- 数据以 Chunk 形式流动，保持低内存占用
- StreamingPlugin 自动处理 Chunk 流并可并行化（批处理、顺序回收）
- 支持时间边界校验、断点分段和 halo 扩展
- 可选动态负载均衡（DynamicLoadBalancer）
- 支持进度条跟踪与 executor_config 统一配置
- 兼容静态数据，自动转换为 chunk 流

关键约定：
- Chunk.metadata 包含 main_start/main_end/segment_id，用于裁剪与状态重置
 - time 字段默认使用 TIMESTAMP_FIELD（ps）

运行逻辑（高层）：
1. StreamingContext.get_stream 选择插件：
   - 流式插件：直接调用 compute()
   - 静态插件：临时包装为 StreamingPlugin 并切分为 chunk
2. StreamingPlugin.compute 获取输入流：
   - 依赖是流式数据则直接迭代
   - 依赖是静态数组则 _data_to_chunks 分段并可扩展 halo
3. compute_chunk 逐块处理，_postprocess_result 负责：
   - 包装非 Chunk 输出
   - 按 main_start/main_end 裁剪输出
4. _validate_chunk 校验时间边界，保障 endtime ≤ chunk.end
5. 并行模式下使用 ExecutorManager 批量提交任务并按顺序产出结果

Examples:
    from waveform_analysis.core.plugins.core.streaming import get_streaming_context

    stream_ctx = get_streaming_context(ctx, run_id="run_001", chunk_size=50000)
    for chunk in stream_ctx.get_stream("st_waveforms_stream"):
        handle_chunk(chunk)
"""

import logging
import pickle
import time
from typing import Any, Dict, Generator, Iterator, List, Optional, Tuple, Union
import warnings

import numpy as np

from waveform_analysis.core.execution.config import get_config
from waveform_analysis.core.foundation.utils import exporter
from waveform_analysis.core.processing.chunk import (
    DEFAULT_BREAK_THRESHOLD_PS,
    DT_FIELD,
    ENDTIME_FIELD,
    LENGTH_FIELD,
    TIME_FIELD,
    TIMESTAMP_FIELD,
    Chunk,
    check_chunk_boundaries,
    get_endtime,
    select_time_range,
    split_by_breaks,
)

from .base import Plugin

logger = logging.getLogger(__name__)
export, __all__ = exporter()

_STREAMING_CONFIG_KEYS = {
    "chunk_size",
    "parallel",
    "executor_type",
    "max_workers",
    "parallel_batch_size",
    "break_threshold_ps",
    "required_halo_ns",
    "required_halo_left_ns",
    "required_halo_right_ns",
    "clip_strict",
    "executor_config",
}


def _is_pickleable(obj: Any) -> bool:
    try:
        pickle.dumps(obj)
    except Exception:
        return False
    return True


def _process_chunk_worker(
    plugin: "StreamingPlugin",
    chunk: Chunk,
    context: Any,
    run_id: str,
    kwargs: Dict[str, Any],
) -> Optional[Chunk]:
    result = plugin.compute_chunk(chunk, context, run_id, **kwargs)
    result = plugin._postprocess_result(result, chunk)
    if result is not None:
        plugin._validate_chunk(result)
    return result


def _pick_time_field(data: np.ndarray, preferred: str) -> Optional[str]:
    """选择可用的时间字段名（优先使用 preferred）。"""
    if not hasattr(data, "dtype") or data.dtype.names is None:
        return None
    if preferred in data.dtype.names:
        return preferred
    if preferred == TIME_FIELD and TIMESTAMP_FIELD in data.dtype.names:
        return TIMESTAMP_FIELD
    if preferred == TIMESTAMP_FIELD and TIME_FIELD in data.dtype.names:
        return TIME_FIELD
    return None


class StreamingPlugin(Plugin):
    """
    支持流式处理的插件基类。

    与普通 Plugin 的区别：
    - `compute()` 接收 chunk 迭代器，返回 chunk 迭代器
    - 自动处理时间边界对齐
    - 支持并行处理多个 chunk
    - 可选的动态负载均衡

    使用方式：
    1. 继承 StreamingPlugin
    2. 重写 `compute_chunk()` 方法处理单个 chunk
    3. 设置 `output_kind = "stream"`（自动设置）
    4. 可选：启用负载均衡 `use_load_balancer = True`

    Chunk 处理约定：
    - 输入 chunk 可能带 halo，核心时间区间保存在 metadata 的 main_start/main_end
    - `_postprocess_result()` 会将非 Chunk 输出包装成 Chunk，并裁剪到 main_* 范围
    - `clip_strict=True` 时会进行严格边界裁剪（见 select_time_range）

    关键配置（常用）：
    - chunk_size: 静态数据切分大小
    - break_threshold_ps: 断点阈值（单位与 time_field 一致，默认 ps）
    - required_halo_ns/left/right: halo 扩展范围
    - parallel/executor_type/max_workers: 并行策略
    - parallel_batch_size: 并行批处理大小（None=自动）
    - executor_config: 统一执行器配置，覆盖类属性
    - load_balancer_config.worker_buckets: discrete worker buckets (e.g. [2, 4, 8])
    - is_stateful/reset_on_break: 状态插件在分段切换时的处理策略
    - time_field/dt_field/length_field/endtime_field: 时间字段名配置
    """

    # 流式处理相关配置
    chunk_size: int = 50000  # 默认 chunk 大小
    parallel: bool = True  # 是否并行处理
    parallel_batch_size: Optional[int] = None  # 并行处理批量大小（None=自动）
    executor_type: str = "thread"  # 执行器类型
    max_workers: Optional[int] = None  # 最大工作线程/进程数
    time_field: str = TIMESTAMP_FIELD  # 时间字段名（默认 timestamp）
    dt_field: str = DT_FIELD  # 采样间隔字段名
    length_field: str = LENGTH_FIELD  # 长度字段名
    endtime_field: str = ENDTIME_FIELD  # 结束时间字段名
    dt: Optional[float] = None  # 可选的固定采样间隔（覆盖 dt_field）
    output_time_field: str = TIMESTAMP_FIELD  # 输出时间字段名
    output_endtime_field: str = ENDTIME_FIELD  # 输出结束时间字段名
    output_data_kind: str = "stream"  # 输出数据类型标签
    required_halo_ns: int = 0  # 对称 halo
    required_halo_left_ns: int = 0  # 左侧 halo
    required_halo_right_ns: int = 0  # 右侧 halo
    clip_strict: bool = False  # 输出裁剪策略
    is_stateful: bool = False  # 是否有状态
    reset_on_break: bool = True  # break 时是否重置状态
    break_threshold_ps: int = DEFAULT_BREAK_THRESHOLD_PS  # break 阈值（默认 ps）

    # 负载均衡配置
    use_load_balancer: bool = False  # 是否使用独立的负载均衡器
    load_balancer_config: Optional[Dict[str, Any]] = None  # 负载均衡器配置

    def __init__(self):
        """初始化流式插件，自动设置 output_kind 为 stream"""
        super().__init__()
        self.output_kind = "stream"  # 流式插件总是输出流
        self._load_balancer: Optional[Any] = None  # DynamicLoadBalancer实例
        self._warned_legacy_streaming_config = False

        # 如果启用负载均衡,创建实例
        if self.use_load_balancer:
            self._init_load_balancer()

    def _init_load_balancer(self):
        """初始化负载均衡器"""
        from waveform_analysis.core.load_balancer import DynamicLoadBalancer

        config = self.load_balancer_config or {}
        self._load_balancer = DynamicLoadBalancer(
            min_workers=config.get("min_workers", 1),
            max_workers=config.get("max_workers", self.max_workers),
            cpu_threshold=config.get("cpu_threshold", 0.8),
            memory_threshold=config.get("memory_threshold", 0.85),
            check_interval=config.get("check_interval", 5.0),
        )

    def get_load_balancer_stats(self) -> Optional[Dict]:
        """
        获取插件的负载均衡统计信息

        Returns:
            统计信息字典，如果未启用则返回None
        """
        if self._load_balancer:
            return self._load_balancer.get_statistics()
        return None

    def _resolve_worker_buckets(self, max_workers: Optional[int]) -> List[int]:
        config = self.load_balancer_config or {}
        buckets: List[int] = []
        raw_buckets = config.get("worker_buckets")

        if raw_buckets:
            for value in raw_buckets:
                try:
                    bucket = int(value)
                except (TypeError, ValueError):
                    continue
                if bucket > 0:
                    buckets.append(bucket)
        else:
            bucket_max = max_workers
            if bucket_max is None and self._load_balancer:
                bucket_max = self._load_balancer.max_workers
            if bucket_max is None:
                bucket_max = 1
            bucket_max = max(1, int(bucket_max))
            bucket = 1
            while bucket < bucket_max:
                buckets.append(bucket)
                bucket *= 2
            buckets.append(bucket_max)

        bucket_min = 1
        if self._load_balancer:
            bucket_min = max(1, int(self._load_balancer.min_workers))
        buckets.append(bucket_min)

        if max_workers is not None:
            buckets.append(max(1, int(max_workers)))

        buckets = sorted(set(buckets))
        if not buckets:
            return [max(1, int(max_workers or 1))]
        return buckets

    def _quantize_workers(self, suggested: int, max_workers: Optional[int]) -> int:
        if suggested < 1:
            suggested = 1
        buckets = self._resolve_worker_buckets(max_workers)
        for bucket in buckets:
            if bucket >= suggested:
                return bucket
        return buckets[-1]

    def reset_state(self) -> None:
        """Reset internal state for stateful plugins."""
        return None

    def _filter_streaming_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        filtered: Dict[str, Any] = {}
        unknown: List[str] = []
        for key, value in config.items():
            if key in _STREAMING_CONFIG_KEYS:
                filtered[key] = value
            else:
                unknown.append(key)
        if unknown:
            warnings.warn(
                f"Unknown streaming_config keys for {self.provides}: {sorted(unknown)}",
                UserWarning,
                stacklevel=2,
            )
        return filtered

    def _get_default_streaming_config(self) -> Dict[str, Any]:
        defaults: Dict[str, Any] = {"executor_config": None}
        for key in _STREAMING_CONFIG_KEYS:
            if key == "executor_config":
                continue
            defaults[key] = getattr(type(self), key, getattr(self, key, None))
        return defaults

    def _get_legacy_streaming_config(self, context: Any) -> Dict[str, Any]:
        config = getattr(context, "config", {})
        if not isinstance(config, dict):
            return {}

        provides = self.provides
        legacy: Dict[str, Any] = {}
        for key in _STREAMING_CONFIG_KEYS:
            if provides in config and isinstance(config[provides], dict) and key in config[provides]:
                legacy[key] = config[provides][key]
                continue
            dotted_key = f"{provides}.{key}"
            if dotted_key in config:
                legacy[key] = config[dotted_key]
                continue
            if key in config:
                legacy[key] = config[key]
        return legacy

    def _collect_streaming_config(
        self,
        context: Any,
        streaming_config: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        merged = self._get_default_streaming_config()
        legacy = self._get_legacy_streaming_config(context)
        if legacy:
            if not self._warned_legacy_streaming_config:
                warnings.warn(
                    "Streaming config should be passed via streaming_config; "
                    f"legacy keys detected for {self.provides}: {sorted(legacy)}",
                    DeprecationWarning,
                    stacklevel=2,
                )
                self._warned_legacy_streaming_config = True
            merged.update(legacy)
        if streaming_config:
            if not isinstance(streaming_config, dict):
                raise TypeError("streaming_config must be a dict")
            merged.update(self._filter_streaming_config(streaming_config))
        return merged

    def _apply_streaming_config(self, config: Dict[str, Any]) -> None:
        for key in _STREAMING_CONFIG_KEYS:
            if key == "executor_config":
                continue
            if key in config:
                setattr(self, key, config[key])

    def _get_required_halo(self) -> Tuple[int, int]:
        left = self.required_halo_left_ns or 0
        right = self.required_halo_right_ns or 0
        if self.required_halo_ns:
            left = max(left, self.required_halo_ns)
            right = max(right, self.required_halo_ns)
        return int(left), int(right)

    def _iter_segments(
        self,
        data: np.ndarray,
        time_field: str,
    ) -> Iterator[Tuple[np.ndarray, int, int, int]]:
        if self.break_threshold_ps and self.break_threshold_ps > 0:
            segment_id = 0
            for segment_data, info in split_by_breaks(
                data,
                break_threshold_ps=self.break_threshold_ps,
                min_chunk_size=1,
                time_field=time_field,
                endtime_field=self.endtime_field,
                dt_field=self.dt_field,
                length_field=self.length_field,
                dt=self.dt,
            ):
                yield segment_data, int(info.start_time), int(info.end_time), segment_id
                segment_id += 1
            return

        if len(data) == 0:
            return

        endtime = get_endtime(
            data,
            time_field=time_field,
            endtime_field=self.endtime_field,
            dt_field=self.dt_field,
            length_field=self.length_field,
            dt=self.dt,
        )
        start_time = int(np.min(data[time_field]))
        end_time = int(np.max(endtime))
        yield data, start_time, end_time, 0

    def compute_chunk(self, chunk: Chunk, context: Any, run_id: str, **kwargs) -> Chunk:
        """
        处理单个 chunk。

        子类应该重写此方法来实现具体的处理逻辑。

        Args:
            chunk: 输入 chunk（可能带 halo）
            context: Context 对象
            run_id: 运行 ID
            **kwargs: 其他参数

        Returns:
            处理后的 chunk、可转换的数据，或 None（表示丢弃该 chunk）
        """
        # 默认实现：直接返回（子类应重写）
        return chunk

    def _postprocess_result(self, result: Any, input_chunk: Chunk) -> Optional[Chunk]:
        if result is None:
            return None
        if not isinstance(result, Chunk):
            result = Chunk(
                data=np.asarray(result),
                start=input_chunk.metadata.get("main_start", input_chunk.start),
                end=input_chunk.metadata.get("main_end", input_chunk.end),
                run_id=input_chunk.run_id,
                data_type=self.provides,
                data_kind=self.output_data_kind,
                time_field=self.output_time_field,
                dt_field=self.dt_field,
                length_field=self.length_field,
                endtime_field=self.output_endtime_field,
                dt=self.dt,
                metadata={"segment_id": input_chunk.metadata.get("segment_id")},
            )

        main_start = input_chunk.metadata.get("main_start")
        main_end = input_chunk.metadata.get("main_end")
        if main_start is None or main_end is None:
            return result

        if not hasattr(result.data, "dtype") or result.data.dtype.names is None:
            return result

        time_field = result.time_field
        clipped_data = select_time_range(
            result.data,
            start=main_start,
            end=main_end,
            strict=self.clip_strict,
            time_field=time_field,
            endtime_field=result.endtime_field,
            dt_field=result.dt_field,
            length_field=result.length_field,
            dt=result.dt,
        )

        if len(clipped_data) == 0:
            return None

        metadata = dict(result.metadata)
        metadata.update({
            "main_start": main_start,
            "main_end": main_end,
            "segment_id": input_chunk.metadata.get("segment_id"),
        })

        return Chunk(
            data=clipped_data,
            start=int(main_start),
            end=int(main_end),
            run_id=result.run_id,
            data_type=result.data_type,
            data_kind=result.data_kind,
            time_field=time_field,
            dt_field=result.dt_field,
            length_field=result.length_field,
            endtime_field=result.endtime_field,
            dt=result.dt,
            metadata=metadata,
        )

    def compute(
        self,
        context: Any,
        run_id: str,
        show_progress: bool = False,
        progress_desc: Optional[str] = None,
        **kwargs,
    ) -> Union[Generator[Chunk, None, None], Iterator[Chunk]]:
        """
        流式处理入口：接收 chunk 迭代器，返回 chunk 迭代器。

        默认实现：
        1. 从依赖获取 chunk 流
        2. 对每个 chunk 调用 compute_chunk()
        3. 可选并行处理（状态插件会自动退回串行）
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
        # 解析 streaming_config 并应用
        streaming_config = kwargs.pop("streaming_config", None)
        resolved_streaming_config = self._collect_streaming_config(context, streaming_config)
        self._apply_streaming_config(resolved_streaming_config)

        # 获取依赖的 chunk 流
        input_chunks = self._get_input_chunks(context, run_id, **kwargs)
        executor_config = kwargs.pop("executor_config", None)
        if executor_config is None:
            executor_config = resolved_streaming_config.get("executor_config")
        resolved_executor_config = self._normalize_executor_config(executor_config)
        effective_max_workers = resolved_executor_config.get("max_workers", self.max_workers)

        if self.is_stateful and self.parallel:
            import logging

            logging.getLogger(__name__).warning(
                "Stateful plugin %s running sequentially to preserve order.", self.provides
            )
            self.parallel = False

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

        last_segment_id = None

        try:
            # 并行处理配置
            can_parallel = self.parallel and (effective_max_workers is None or effective_max_workers > 1)
            if can_parallel:
                # 并行处理
                for chunk in self._compute_parallel(
                    input_chunks,
                    context,
                    run_id,
                    executor_config=resolved_executor_config,
                    **kwargs,
                ):
                    if chunk is not None:
                        if tracker and bar_name:
                            tracker.update(bar_name, n=1)
                        yield chunk
            else:
                # 串行处理
                for chunk in input_chunks:
                    if self.is_stateful and self.reset_on_break:
                        segment_id = chunk.metadata.get("segment_id")
                        if segment_id is not None and segment_id != last_segment_id:
                            self.reset_state()
                            last_segment_id = segment_id
                    result = self.compute_chunk(chunk, context, run_id, **kwargs)
                    result = self._postprocess_result(result, chunk)
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

    def _normalize_executor_config(self, executor_config: Optional[Union[str, Dict[str, Any]]]) -> Dict[str, Any]:
        if executor_config is None:
            return {}
        if isinstance(executor_config, str):
            return get_config(executor_config)
        if isinstance(executor_config, dict):
            return executor_config.copy()
        raise TypeError("executor_config must be a dict or a known config name")

    def _get_input_chunks(self, context: Any, run_id: str, **kwargs) -> Iterator[Chunk]:
        """
        从依赖获取 chunk 流。

        如果依赖是流式插件，直接获取其输出流。
        如果是静态数据，转换为 chunk 流（按时间或固定长度切分）。
        当前实现只使用 depends_on 的第一个依赖。
        """
        deps = self.resolve_depends_on(context, run_id=run_id) if hasattr(self, "resolve_depends_on") else self.depends_on
        if not deps:
            # 无依赖，返回空迭代器
            return iter([])

        # 获取第一个依赖（简化：只支持单个依赖）
        dep_name = deps[0]
        dep_name = self.get_dependency_name(dep_name) if hasattr(self, "get_dependency_name") else dep_name
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

        Notes:
            - 若数据包含时间字段，会按 break_threshold_ps 分段，并支持 halo 扩展
            - 若无时间字段，则按 chunk_size 固定切分
        """
        if isinstance(data, np.ndarray):
            # NumPy 数组：按 chunk_size 分割
            n = len(data)
            resolved_time_field = _pick_time_field(data, self.time_field)
            if resolved_time_field:
                halo_left, halo_right = self._get_required_halo()
                for segment_data, segment_start, segment_end, segment_id in self._iter_segments(
                    data, resolved_time_field
                ):
                    seg_len = len(segment_data)
                    for i in range(0, seg_len, self.chunk_size):
                        main_data = segment_data[i : i + self.chunk_size]
                        if len(main_data) == 0:
                            continue

                        time = main_data[resolved_time_field]
                        endtime = get_endtime(
                            main_data,
                            time_field=resolved_time_field,
                            endtime_field=self.endtime_field,
                            dt_field=self.dt_field,
                            length_field=self.length_field,
                            dt=self.dt,
                        )
                        main_start = int(np.min(time))
                        main_end = int(np.max(endtime))
                        extended_start = max(segment_start, main_start - halo_left)
                        extended_end = min(segment_end, main_end + halo_right)

                        extended_data = select_time_range(
                            segment_data,
                            start=extended_start,
                            end=extended_end,
                            strict=False,
                            time_field=resolved_time_field,
                            endtime_field=self.endtime_field,
                            dt_field=self.dt_field,
                            length_field=self.length_field,
                            dt=self.dt,
                        )

                        yield Chunk(
                            data=extended_data,
                            start=extended_start,
                            end=extended_end,
                            run_id=run_id,
                            data_type=self.provides,
                            time_field=resolved_time_field,
                            dt_field=self.dt_field,
                            length_field=self.length_field,
                            endtime_field=self.endtime_field,
                            dt=self.dt,
                            metadata={
                                "main_start": main_start,
                                "main_end": main_end,
                                "segment_id": segment_id,
                            },
                        )
                return

            for i in range(0, n, self.chunk_size):
                chunk_data = data[i : i + self.chunk_size]
                if len(chunk_data) == 0:
                    continue

                start_time = i
                end_time = i + len(chunk_data)

                yield Chunk(
                    data=chunk_data,
                    start=start_time,
                    end=end_time,
                    run_id=run_id,
                    data_type=self.provides,
                    time_field=self.time_field,
                    dt_field=self.dt_field,
                    length_field=self.length_field,
                    endtime_field=self.endtime_field,
                    dt=self.dt,
                    metadata={
                        "main_start": start_time,
                        "main_end": end_time,
                        "segment_id": 0,
                    },
                )
        elif isinstance(data, list):
            # 列表：每个元素作为一个 chunk（简化处理）
            for i, item in enumerate(data):
                if isinstance(item, np.ndarray) and len(item) > 0:
                    resolved_time_field = _pick_time_field(item, self.time_field)
                    if resolved_time_field:
                        time = item[resolved_time_field]
                        endtime = get_endtime(
                            item,
                            time_field=resolved_time_field,
                            endtime_field=self.endtime_field,
                            dt_field=self.dt_field,
                            length_field=self.length_field,
                            dt=self.dt,
                        )
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
                        time_field=resolved_time_field or self.time_field,
                        dt_field=self.dt_field,
                        length_field=self.length_field,
                        endtime_field=self.endtime_field,
                        dt=self.dt,
                        metadata={
                            "main_start": start_time,
                            "main_end": end_time,
                            "segment_id": i,
                        },
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
        executor_config: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> Generator[Chunk, None, None]:
        """
        并行处理 chunk 流（优化版：批量处理，避免完全物化，支持负载均衡）。

        改进：
        - 不再将整个流物化到列表
        - 分批处理：每次处理 batch_size 个 chunk
        - 保持流式处理的内存优势
        - 可选的动态负载均衡

        Args:
            input_chunks: 输入 chunk 迭代器
            context: Context 对象
            run_id: 运行 ID
            **kwargs: 其他参数

        Yields:
            处理后的 chunk（保持顺序；异常会重新抛出并取消未完成任务）
        """
        from concurrent.futures import as_completed
        import itertools

        from waveform_analysis.core.execution.manager import ExecutorManager

        resolved_executor_config = self._normalize_executor_config(executor_config)
        executor_type = resolved_executor_config.get("executor_type", self.executor_type)
        max_workers = resolved_executor_config.get("max_workers", self.max_workers)
        reuse = resolved_executor_config.get("reuse", True)
        max_workers_cap = max_workers

        # 动态计算 max_workers (如果启用负载均衡)
        if self._load_balancer:
            # 估算chunk数量(基于历史统计或默认值)
            stats = self._load_balancer.get_statistics()
            estimated_n_chunks = stats.get("total_tasks", 100) if stats["total_tasks"] > 0 else 100
            suggested_workers = self._load_balancer.get_optimal_workers(
                n_tasks=estimated_n_chunks,
                estimated_task_size=None,  # chunk大小难以预估
            )
            max_workers = self._quantize_workers(suggested_workers, max_workers_cap)

        if executor_type == "process":
            if not _is_pickleable(self) or not _is_pickleable(context) or not _is_pickleable(kwargs):
                logger.warning(
                    "Streaming plugin %s is not pickleable with process executor; "
                    "falling back to thread executor.",
                    self.provides,
                )
                executor_type = "thread"

        # 批量大小：优先使用配置值，否则根据worker数量自动计算
        if self.parallel_batch_size is not None:
            batch_size = self.parallel_batch_size
        else:
            batch_size = max(10, (max_workers or 4) * 3)

        # 记录开始时间(用于统计)
        start_time = time.time() if self._load_balancer else None
        processed_chunks = 0
        success = True

        # 分批处理流
        shutdown_wait = True
        manager = ExecutorManager()
        executor_name = f"stream_{self.provides}"
        executor = manager.get_executor(
            executor_name,
            executor_type=executor_type,
            max_workers=max_workers,
            reuse=reuse,
        )
        try:
            chunk_iter = iter(input_chunks)

            while True:
                # 取一批 chunk
                batch = list(itertools.islice(chunk_iter, batch_size))
                if not batch:
                    break  # 流已耗尽

                # 提交批量任务
                future_to_idx = {
                    executor.submit(_process_chunk_worker, self, chunk, context, run_id, kwargs): idx
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
                        import logging

                        success = False
                        shutdown_wait = False
                        logger = logging.getLogger(__name__)
                        logger.error(f"Error processing chunk {idx}: {e}")
                        for pending in future_to_idx:
                            if pending is future:
                                continue
                            if not pending.done():
                                pending.cancel()
                        raise  # 失败即停：异常向上抛出

                # 按顺序 yield 结果
                for result in results:
                    if result is not None:
                        processed_chunks += 1
                        yield result
        except Exception:
            success = False
            shutdown_wait = False
            raise
        finally:
            manager.release_executor(
                executor_name,
                executor_type=executor_type,
                max_workers=max_workers,
                wait=shutdown_wait,
            )
            # 记录统计信息
            if self._load_balancer and start_time:
                duration = time.time() - start_time
                self._load_balancer.record_task_completion(
                    duration=duration,
                    success=success,
                )

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
        if hasattr(chunk.data, "dtype") and chunk.data.dtype.names is not None:
            validation = check_chunk_boundaries(
                chunk.data,
                chunk.start,
                chunk.end,
                time_field=chunk.time_field,
                endtime_field=chunk.endtime_field,
                dt_field=chunk.dt_field,
                length_field=chunk.length_field,
                dt=chunk.dt,
            )
            if not validation.is_valid:
                raise ValueError(f"Chunk boundary violation in {self.provides}: {validation.errors}")


class StreamingContext:
    """
    流式处理上下文管理器。

    整合 chunk、插件和执行器管理器，提供类似 strax 的流式处理体验。

    运行逻辑：
    - 对流式插件：直接获取输出流并支持 time_range 裁剪
    - 对静态插件：读取静态数据，临时包装为 StreamingPlugin 再切分为 chunk
    """

    def __init__(
        self,
        context: Any,  # 原始 Context 对象
        run_id: str,
        chunk_size: int = 50000,
        parallel: bool = True,
        executor_config: Optional[Dict[str, Any]] = None,
        streaming_config: Optional[Dict[str, Any]] = None,
    ):
        """
        初始化流式处理上下文。

        Args:
            context: 原始 Context 对象
            run_id: 运行 ID
            chunk_size: 默认 chunk 大小
            parallel: 是否启用并行处理
            executor_config: 执行器配置
            streaming_config: 统一流式配置（覆盖 chunk_size/parallel 等）
        """
        self.context = context
        self.run_id = run_id
        self.streaming_config = self._normalize_streaming_config(
            chunk_size,
            parallel,
            executor_config,
            streaming_config,
        )
        self.chunk_size = self.streaming_config.get("chunk_size", chunk_size)
        self.parallel = self.streaming_config.get("parallel", parallel)
        self.executor_config = self.streaming_config.get("executor_config", get_config("io_intensive"))

    def _normalize_streaming_config(
        self,
        chunk_size: int,
        parallel: bool,
        executor_config: Optional[Dict[str, Any]],
        streaming_config: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        normalized = {
            "chunk_size": chunk_size,
            "parallel": parallel,
        }
        if executor_config is not None:
            normalized["executor_config"] = executor_config
        if streaming_config:
            if not isinstance(streaming_config, dict):
                raise TypeError("streaming_config must be a dict")
            normalized.update(streaming_config)
        return normalized

    def get_stream(self, data_name: str, time_range: Optional[Tuple[int, int]] = None, **kwargs) -> Iterator[Chunk]:
        """
        获取数据流。

        Args:
            data_name: 数据名称
            time_range: 时间范围 (start, end)，可选
            **kwargs: 其他参数

        Yields:
            Chunk 对象

        Notes:
            - 对流式插件，直接调用 plugin.compute()
            - 对静态插件，内部使用临时 StreamingPlugin 将数据切成 chunk
            - time_range 会先按重叠过滤，再对 chunk 做裁剪
        """
        # 获取插件
        if data_name not in self.context._plugins:
            raise ValueError(f"No plugin registered for '{data_name}'")

        plugin = self.context._plugins[data_name]

        streaming_config = kwargs.get("streaming_config", self.streaming_config)
        if streaming_config is None:
            streaming_config = {}
        if not isinstance(streaming_config, dict):
            raise TypeError("streaming_config must be a dict")
        if "streaming_config" not in kwargs:
            kwargs["streaming_config"] = streaming_config
        if "executor_config" not in kwargs:
            if streaming_config.get("executor_config") is not None:
                kwargs["executor_config"] = streaming_config["executor_config"]
            else:
                kwargs["executor_config"] = self.executor_config

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
                def __init__(self, run_id, data_name):
                    """
                    初始化临时流式插件包装器

                    用于将静态数据转换为流式 chunks。

                    Args:
                        run_id: 运行标识符
                        data_name: 数据名称（用于 provides）
                    """
                    super().__init__()
                    self.provides = data_name
                    self.depends_on = []

            wrapper = TempWrapper(self.run_id, data_name)
            resolved_config = wrapper._collect_streaming_config(self.context, streaming_config)
            wrapper._apply_streaming_config(resolved_config)

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
        from waveform_analysis.core.processing.chunk import select_time_range

        if len(chunk.data) == 0:
            return chunk

        # 选择时间范围内的数据
        clipped_data = select_time_range(
            chunk.data,
            start,
            end,
            strict=False,
            time_field=chunk.time_field,
            endtime_field=chunk.endtime_field,
            dt_field=chunk.dt_field,
            length_field=chunk.length_field,
            dt=chunk.dt,
        )

        # 计算新的时间范围
        resolved_time_field = _pick_time_field(clipped_data, chunk.time_field)
        if len(clipped_data) > 0 and resolved_time_field:
            time = clipped_data[resolved_time_field]
            endtime = get_endtime(
                clipped_data,
                time_field=resolved_time_field,
                endtime_field=chunk.endtime_field,
                dt_field=chunk.dt_field,
                length_field=chunk.length_field,
                dt=chunk.dt,
            )
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
            time_field=chunk.time_field,
            dt_field=chunk.dt_field,
            length_field=chunk.length_field,
            endtime_field=chunk.endtime_field,
            dt=chunk.dt,
            metadata=dict(chunk.metadata),
        )

    def iter_chunks(self, data_name: str, time_range: Optional[Tuple[int, int]] = None, **kwargs) -> Iterator[Chunk]:
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

    def merge_stream(self, streams: List[Iterator[Chunk]], sort: bool = True) -> Iterator[Chunk]:
        """
        合并多个数据流。

        Args:
            streams: 数据流列表
            sort: 是否按时间排序

        Yields:
            合并后的 chunk
        """
        from waveform_analysis.core.processing.chunk import (
            merge_chunks,  # sort_by_time is handled by merge_chunks, sort_by_time
        )

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
        resolved_time_field = _pick_time_field(merged_data, TIME_FIELD)
        if len(merged_data) > 0 and resolved_time_field:
            time = merged_data[resolved_time_field]
            endtime = get_endtime(merged_data, time_field=resolved_time_field)
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
            time_field=resolved_time_field or TIME_FIELD,
        )


# 便捷函数
@export
def get_streaming_context(
    context: Any,
    run_id: str,
    chunk_size: int = 50000,
    parallel: bool = True,
    executor_config: Optional[Dict[str, Any]] = None,
    streaming_config: Optional[Dict[str, Any]] = None,
) -> StreamingContext:
    """
    创建流式处理上下文。

    Args:
        context: Context 对象
        run_id: 运行 ID
        chunk_size: 默认 chunk 大小
        parallel: 是否启用并行处理
        executor_config: 执行器配置
        streaming_config: 统一流式配置（覆盖 chunk_size/parallel 等）

    Returns:
        StreamingContext 对象
    """
    return StreamingContext(
        context,
        run_id,
        chunk_size,
        parallel,
        executor_config,
        streaming_config,
    )
