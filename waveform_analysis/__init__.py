"""
Waveform Analysis - 波形数据分析工具包

一个用于处理和分析数据采集(DAQ)系统波形数据的Python包。
提供数据加载、处理、配对、特征提取和可视化功能。
"""

__version__ = "0.1.0"
__author__ = "Your Name"

from .core.dataset import WaveformDataset
from .core.loader import get_raw_files, get_waveforms
from .core.processor import (
    WaveformStruct,
    build_waveform_df,
    group_multi_channel_hits,
)
from .utils.daq import DAQAnalyzer, DAQRun

__all__ = [
    "WaveformDataset",
    "get_raw_files",
    "get_waveforms",
    "WaveformStruct",
    "build_waveform_df",
    "group_multi_channel_hits",
    "DAQRun",
    "DAQAnalyzer",
]
