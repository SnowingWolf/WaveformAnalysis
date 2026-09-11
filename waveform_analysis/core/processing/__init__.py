"""
Processing 子模块 - 数据处理流水线

提供数据加载、信号处理、事件分析和 Chunk 管理功能。

主要组件：
- WaveformLoaderCSV: 波形数据加载器
- WaveformStruct: 波形结构化处理（从 plugins.builtin.cpu.waveforms 导入）
- EventAnalyzer: 事件分析器
- Chunk: 时间对齐的数据块管理

向后兼容：
所有导出的类和函数可以通过以下方式导入：
    from waveform_analysis.core.processing import WaveformStruct
    from waveform_analysis.core import WaveformStruct  # 通过 core.__init__.py 兼容
"""

from waveform_analysis._lazy_exports import LazyExport as _LazyExport
from waveform_analysis._lazy_exports import lazy_dir as _lazy_dir
from waveform_analysis._lazy_exports import (
    resolve_lazy_attribute as _resolve_lazy_attribute,
)

_LAZY_EXPORTS: dict[str, _LazyExport] = {
    # 数据加载
    "WaveformLoaderCSV": (".loader", "WaveformLoaderCSV"),
    # 信号处理
    "WaveformStruct": (
        "..plugins.builtin.st_waveforms.plugin",
        "WaveformStruct",
    ),
    "WaveformStructConfig": (
        "..plugins.builtin.st_waveforms.plugin",
        "WaveformStructConfig",
    ),
    "group_multi_channel_hits": (
        ".event_grouping",
        "group_multi_channel_hits",
    ),
    "find_hits": (".event_grouping", "find_hits"),
    "ST_WAVEFORM_DTYPE": (".dtypes", "ST_WAVEFORM_DTYPE"),
    "PEAK_DTYPE": (".dtypes", "PEAK_DTYPE"),
    "RECORDS_DTYPE": (".dtypes", "RECORDS_DTYPE"),
    "EVENTS_DTYPE": (".dtypes", "EVENTS_DTYPE"),
    "RecordsBundle": (".records_builder", "RecordsBundle"),
    "RecordsBundleRef": (".records_builder", "RecordsBundleRef"),
    "EventsBundle": (".records_builder", "EventsBundle"),
    "build_records_from_st_waveforms": (
        ".records_builder",
        "build_records_from_st_waveforms",
    ),
    "build_records_from_st_waveforms_sharded": (
        ".records_builder",
        "build_records_from_st_waveforms_sharded",
    ),
    "build_records_from_v1725_files": (
        ".records_builder",
        "build_records_from_v1725_files",
    ),
    "merge_records_parts": (".records_builder", "merge_records_parts"),
    "split_by_channel": (".records_builder", "split_by_channel"),
    "split_by_hardware_channel": (".records_builder", "split_by_hardware_channel"),
    # 事件分析
    "EventAnalyzer": (".analyzer", "EventAnalyzer"),
    # Chunk 常量
    "TIME_FIELD": (".chunk", "TIME_FIELD"),
    "DT_FIELD": (".chunk", "DT_FIELD"),
    "LENGTH_FIELD": (".chunk", "LENGTH_FIELD"),
    "ENDTIME_FIELD": (".chunk", "ENDTIME_FIELD"),
    "CHANNEL_FIELD": (".chunk", "CHANNEL_FIELD"),
    # Chunk 数据类
    "Chunk": (".chunk", "Chunk"),
    "ChunkInfo": (".chunk", "ChunkInfo"),
    "ValidationResult": (".chunk", "ValidationResult"),
    # Endtime 操作
    "compute_endtime": (".chunk", "compute_endtime"),
    "add_endtime_field": (".chunk", "add_endtime_field"),
    "validate_endtime": (".chunk", "validate_endtime"),
    "get_endtime": (".chunk", "get_endtime"),
    # 检查函数
    "check_monotonic": (".chunk", "check_monotonic"),
    "check_no_overlap": (".chunk", "check_no_overlap"),
    "check_sorted_by_time": (".chunk", "check_sorted_by_time"),
    "check_chunk_boundaries": (".chunk", "check_chunk_boundaries"),
    "check_chunk_continuity": (".chunk", "check_chunk_continuity"),
    # 时间范围操作
    "get_time_range": (".chunk", "get_time_range"),
    "select_time_range": (".chunk", "select_time_range"),
    "clip_to_time_range": (".chunk", "clip_to_time_range"),
    # Chunk 分割
    "split_by_time": (".chunk", "split_by_time"),
    "split_by_count": (".chunk", "split_by_count"),
    "split_by_breaks": (".chunk", "split_by_breaks"),
    "merge_chunks": (".chunk", "merge_chunks"),
    # Rechunk
    "rechunk": (".chunk", "rechunk"),
    "rechunk_to_boundaries": (".chunk", "rechunk_to_boundaries"),
    # 工具函数
    "sort_by_time": (".chunk", "sort_by_time"),
    "concat_sorted": (".chunk", "concat_sorted"),
}

__all__ = [
    # 数据加载
    "WaveformLoaderCSV",
    # 信号处理
    "WaveformStruct",
    "WaveformStructConfig",
    "group_multi_channel_hits",
    "find_hits",
    "ST_WAVEFORM_DTYPE",
    "PEAK_DTYPE",
    "RECORDS_DTYPE",
    "EVENTS_DTYPE",
    "RecordsBundle",
    "RecordsBundleRef",
    "EventsBundle",
    "build_records_from_st_waveforms",
    "build_records_from_st_waveforms_sharded",
    "build_records_from_v1725_files",
    "merge_records_parts",
    "split_by_channel",
    "split_by_hardware_channel",
    # 事件分析
    "EventAnalyzer",
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
    return _lazy_dir(globals(), _LAZY_EXPORTS, __all__)
