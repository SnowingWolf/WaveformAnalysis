"""数据处理模块 - 数据加载、处理、I/O和数据结构。"""

from .io import load_csv, parse_csv_files
from .loader import get_raw_files, get_waveforms
from .processor import WaveformStruct, find_hits, process_waveforms
from .wavestruct import get_peaks_dtype, get_waveform_dtype

__all__ = [
    # I/O
    "load_csv",
    "parse_csv_files",
    # Loader
    "get_raw_files",
    "get_waveforms",
    # Processor
    "WaveformStruct",
    "find_hits",
    "process_waveforms",
    # WaveStruct
    "get_peaks_dtype",
    "get_waveform_dtype",
]
