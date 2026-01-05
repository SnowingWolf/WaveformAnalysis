"""
Waveform Analysis - 波形数据分析工具包

一个用于处理和分析数据采集(DAQ)系统波形数据的Python包。
提供数据加载、处理、配对、特征提取和可视化功能。
"""

__version__ = "0.1.0"
__author__ = "Your Name"

from .core.dataset import WaveformDataset
from .core.executor_config import EXECUTOR_CONFIGS, get_config, register_config
from .core.executor_manager import (
    get_executor,
    get_executor_manager,
    parallel_apply,
    parallel_map,
)
from .core.streaming import (
    StreamingContext,
    StreamingPlugin,
    get_streaming_context,
)
from .core.processor import (
    WaveformStruct,
    build_waveform_df,
    group_multi_channel_hits,
)
from .utils.daq import DAQAnalyzer, DAQRun
from .utils.loader import get_raw_files, get_waveforms

__all__ = [
    "WaveformDataset",
    "get_raw_files",
    "get_waveforms",
    "WaveformStruct",
    "build_waveform_df",
    "group_multi_channel_hits",
    "DAQRun",
    "DAQAnalyzer",
    # 执行器管理器
    "get_executor",
    "get_executor_manager",
    "parallel_map",
    "parallel_apply",
    # 执行器配置
    "EXECUTOR_CONFIGS",
    "get_config",
    "register_config",
    # 流式处理
    "StreamingPlugin",
    "StreamingContext",
    "get_streaming_context",
]
