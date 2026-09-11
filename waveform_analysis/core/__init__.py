"""
Core 模块 - WaveformAnalysis 框架的核心实现。

包含数据加载 (Loader)、信号处理 (Processor)、事件分析 (Analyzer)、
插件系统 (Plugins/Context) 以及存储管理 (Storage/Cache) 等核心组件。
通过此模块导出公共 API，供用户和 CLI 调用。
"""

from waveform_analysis._lazy_exports import LazyExport as _LazyExport
from waveform_analysis._lazy_exports import lazy_dir as _lazy_dir
from waveform_analysis._lazy_exports import (
    resolve_lazy_attribute as _resolve_lazy_attribute,
)

_LAZY_EXPORTS: dict[str, _LazyExport] = {
    # 核心类
    "Context": (".context", "Context"),
    "RecordsView": (".data.records_view", "RecordsView"),
    "records_view": (".data.records_view", "records_view"),
    "Plugin": (".plugins.core.base", "Plugin"),
    "Option": (".plugins.core.base", "Option"),
    # 异常处理
    "ErrorSeverity": (".foundation.exceptions", "ErrorSeverity"),
    "PluginError": (".foundation.exceptions", "PluginError"),
    "ErrorContext": (".foundation.exceptions", "ErrorContext"),
    # 存储层（向后兼容）
    "MemmapStorage": (".storage.memmap", "MemmapStorage"),
    "CacheManager": (".storage.cache", "CacheManager"),
    "StorageBackend": (".storage.backends", "StorageBackend"),
    "CompressionManager": (".storage.compression", "CompressionManager"),
    "IntegrityChecker": (".storage.integrity", "IntegrityChecker"),
    # 执行层（向后兼容）
    "get_executor": (".execution.manager", "get_executor"),
    "parallel_map": (".execution.manager", "parallel_map"),
    "parallel_apply": (".execution.manager", "parallel_apply"),
    "get_timeout_manager": (".execution.timeout", "get_timeout_manager"),
    # 处理函数
    "WaveformStruct": (
        ".plugins.builtin.st_waveforms.plugin",
        "WaveformStruct",
    ),
    "group_multi_channel_hits": (
        ".processing.event_grouping",
        "group_multi_channel_hits",
    ),
    # Chunk 常量
    "TIME_FIELD": (".processing.chunk", "TIME_FIELD"),
    "DT_FIELD": (".processing.chunk", "DT_FIELD"),
    "LENGTH_FIELD": (".processing.chunk", "LENGTH_FIELD"),
    "ENDTIME_FIELD": (".processing.chunk", "ENDTIME_FIELD"),
    "CHANNEL_FIELD": (".processing.chunk", "CHANNEL_FIELD"),
    # Chunk 数据类
    "Chunk": (".processing.chunk", "Chunk"),
    "ChunkInfo": (".processing.chunk", "ChunkInfo"),
    "ValidationResult": (".processing.chunk", "ValidationResult"),
    # Endtime 操作
    "compute_endtime": (".processing.chunk", "compute_endtime"),
    "add_endtime_field": (".processing.chunk", "add_endtime_field"),
    "validate_endtime": (".processing.chunk", "validate_endtime"),
    "get_endtime": (".processing.chunk", "get_endtime"),
    # 检查函数
    "check_monotonic": (".processing.chunk", "check_monotonic"),
    "check_no_overlap": (".processing.chunk", "check_no_overlap"),
    "check_sorted_by_time": (".processing.chunk", "check_sorted_by_time"),
    "check_chunk_boundaries": (".processing.chunk", "check_chunk_boundaries"),
    "check_chunk_continuity": (".processing.chunk", "check_chunk_continuity"),
    # 时间范围操作
    "get_time_range": (".processing.chunk", "get_time_range"),
    "select_time_range": (".processing.chunk", "select_time_range"),
    "clip_to_time_range": (".processing.chunk", "clip_to_time_range"),
    # Chunk 分割
    "split_by_time": (".processing.chunk", "split_by_time"),
    "split_by_count": (".processing.chunk", "split_by_count"),
    "split_by_breaks": (".processing.chunk", "split_by_breaks"),
    "merge_chunks": (".processing.chunk", "merge_chunks"),
    # Rechunk
    "rechunk": (".processing.chunk", "rechunk"),
    "rechunk_to_boundaries": (".processing.chunk", "rechunk_to_boundaries"),
    # 工具函数
    "sort_by_time": (".processing.chunk", "sort_by_time"),
    "concat_sorted": (".processing.chunk", "concat_sorted"),
}

# These child-module names were visible after the historical eager
# initializer.  Keep them in ``dir(core)`` without importing those modules.
_PUBLIC_SUBMODULES = (
    "cancellation",
    "config",
    "context",
    "context_cache",
    "context_config",
    "context_execution",
    "context_plugins",
    "context_time",
    "data",
    "execution",
    "foundation",
    "hardware",
    "plugins",
    "processing",
    "storage",
    "utils",
)

__all__ = [
    # 核心类
    "Context",
    "RecordsView",
    "records_view",
    "Plugin",
    "Option",
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
    # 处理函数
    "WaveformStruct",
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


def __getattr__(name: str) -> object:
    return _resolve_lazy_attribute(name, _LAZY_EXPORTS, globals())


def __dir__() -> list[str]:
    return _lazy_dir(globals(), _LAZY_EXPORTS, (*__all__, *_PUBLIC_SUBMODULES))
