"""数据处理模块 - 数据加载、处理、I/O和数据结构。"""

from .io import parse_and_stack_files, parse_files_generator
from .loader import build_filetime_index, get_files_by_filetime, get_raw_files, get_waveforms
from .processor import build_waveform_df, find_hits, group_multi_channel_hits
from .wavestruct import PEAK_DTYPE, RECORD_DTYPE, WaveformStruct

__all__ = [
    # I/O
    "parse_files_generator",
    "parse_and_stack_files",
    # Loader
    "get_raw_files",
    "get_waveforms",
    "build_filetime_index",
    "get_files_by_filetime",
    # Processor
    "find_hits",
    "build_waveform_df",
    "group_multi_channel_hits",
    # WaveStruct
    "WaveformStruct",
    "RECORD_DTYPE",
    "PEAK_DTYPE",
]
