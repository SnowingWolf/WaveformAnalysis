# -*- coding: utf-8 -*-
"""
Core 模块 - WaveformAnalysis 框架的核心实现。

包含数据加载 (Loader)、信号处理 (Processor)、事件分析 (Analyzer)、
插件系统 (Plugins/Context) 以及存储管理 (Storage/Cache) 等核心组件。
通过此模块导出公共 API，供用户和 CLI 调用。
"""

# Chunk 处理工具
from waveform_analysis.utils.loader import (
    build_filetime_index,
    get_files_by_filetime,
    get_raw_files,
    get_waveforms,
)

from .processing.chunk import (
    CHANNEL_FIELD,
    DT_FIELD,
    ENDTIME_FIELD,
    LENGTH_FIELD,
    # 常量
    TIME_FIELD,
    # 数据类
    Chunk,
    ChunkInfo,
    ValidationResult,
    add_endtime_field,
    check_chunk_boundaries,
    check_chunk_continuity,
    # 检查函数
    check_monotonic,
    check_no_overlap,
    check_sorted_by_time,
    clip_to_time_range,
    # Endtime 操作
    compute_endtime,
    concat_sorted,
    get_endtime,
    # 时间范围操作
    get_time_range,
    merge_chunks,
    # Rechunk
    rechunk,
    rechunk_to_boundaries,
    select_time_range,
    # 工具函数
    sort_by_time,
    split_by_breaks,
    split_by_count,
    # Chunk 分割
    split_by_time,
    validate_endtime,
)
from .context import Context
from .dataset import WaveformDataset
from .foundation.exceptions import ErrorContext, ErrorSeverity, PluginError
from .plugins.core.base import Option, Plugin
from .processing.processor import (
    WaveformStruct,
    build_waveform_df,
    group_multi_channel_hits,
)
from .plugins.builtin.standard import (
    DataFramePlugin,
    GroupedEventsPlugin,
    PairedEventsPlugin,
    RawFilesPlugin,
    StWaveformsPlugin,
    WaveformsPlugin,
)

# 向后兼容：导出 storage 子模块的主要类
# 用户仍然可以使用 `from waveform_analysis.core import MemmapStorage`
from .storage import (
    MemmapStorage,
    CacheManager,
    StorageBackend,
    CompressionManager,
    IntegrityChecker,
)

# 向后兼容：导出 execution 子模块的主要函数
from .execution import (
    get_executor,
    parallel_map,
    parallel_apply,
    get_timeout_manager,
)

__all__ = [
    # 核心类
    "Context",
    "Plugin",
    "Option",
    "WaveformDataset",
    # 异常处理
    "ErrorSeverity",
    "PluginError",
    "ErrorContext",
    # 存储层（向后兼容）
    "MemmapStorage",
    "CacheManager",
    "StorageBackend",
    "CompressionManager",
    "IntegrityChecker",
    # 执行层（向后兼容）
    "get_executor",
    "parallel_map",
    "parallel_apply",
    "get_timeout_manager",
    # 插件
    "RawFilesPlugin",
    "WaveformsPlugin",
    "StWaveformsPlugin",
    "DataFramePlugin",
    "GroupedEventsPlugin",
    "PairedEventsPlugin",
    # 加载函数
    "get_raw_files",
    "get_waveforms",
    "build_filetime_index",
    "get_files_by_filetime",
    # 处理函数
    "WaveformStruct",
    "build_waveform_df",
    "group_multi_channel_hits",
    # Chunk 常量
    "TIME_FIELD",
    "DT_FIELD",
    "LENGTH_FIELD",
    "ENDTIME_FIELD",
    "CHANNEL_FIELD",
    # Chunk 数据类
    "Chunk",
    "ChunkInfo",
    "ValidationResult",
    # Endtime 操作
    "compute_endtime",
    "add_endtime_field",
    "validate_endtime",
    "get_endtime",
    # 检查函数
    "check_monotonic",
    "check_no_overlap",
    "check_sorted_by_time",
    "check_chunk_boundaries",
    "check_chunk_continuity",
    # 时间范围操作
    "get_time_range",
    "select_time_range",
    "clip_to_time_range",
    # Chunk 分割
    "split_by_time",
    "split_by_count",
    "split_by_breaks",
    "merge_chunks",
    # Rechunk
    "rechunk",
    "rechunk_to_boundaries",
    # 工具函数
    "sort_by_time",
    "concat_sorted",
]
