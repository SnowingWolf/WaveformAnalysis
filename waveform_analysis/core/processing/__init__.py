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

# 数据加载
# 事件分析
# WaveformStruct 从新位置导入（向后兼容）
from waveform_analysis.core.plugins.builtin.cpu.waveforms import (
    WaveformStruct,
    WaveformStructConfig,
    create_channel_mapping,
)

from .analyzer import EventAnalyzer

# Chunk 工具
from .chunk import (
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

# 信号处理
from .dtypes import EVENTS_DTYPE, PEAK_DTYPE, RECORDS_DTYPE, ST_WAVEFORM_DTYPE
from .event_grouping import find_hits, group_multi_channel_hits
from .loader import WaveformLoaderCSV
from .records_builder import (
    EventsBundle,
    RecordsBundle,
    build_records_from_st_waveforms,
    build_records_from_st_waveforms_sharded,
    build_records_from_v1725_files,
    merge_records_parts,
    split_by_channel,
)

__all__ = [
    # 数据加载
    "WaveformLoaderCSV",
    # 信号处理
    "WaveformStruct",
    "WaveformStructConfig",
    "create_channel_mapping",
    "group_multi_channel_hits",
    "find_hits",
    "ST_WAVEFORM_DTYPE",
    "PEAK_DTYPE",
    "RECORDS_DTYPE",
    "EVENTS_DTYPE",
    "RecordsBundle",
    "EventsBundle",
    "build_records_from_st_waveforms",
    "build_records_from_st_waveforms_sharded",
    "build_records_from_v1725_files",
    "merge_records_parts",
    "split_by_channel",
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
