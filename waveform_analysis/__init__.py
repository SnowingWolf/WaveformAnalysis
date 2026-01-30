"""
Waveform Analysis - 波形数据分析工具包

一个用于处理和分析数据采集(DAQ)系统波形数据的Python包。
提供数据加载、处理、配对、特征提取和可视化功能。
"""

__version__ = "0.1.0"
__author__ = "Your Name"

from .core.context import Context
from .core.execution import get_timeout_manager
from .core.execution.config import EXECUTOR_CONFIGS, get_config, register_config
from .core.execution.manager import (
    get_executor,
    get_executor_manager,
    parallel_apply,
    parallel_map,
)
from .core.foundation.exceptions import ErrorContext, ErrorSeverity, PluginError
from .core.plugins.builtin.cpu.waveforms import WaveformStruct, WaveformStructConfig
from .core.plugins.core.base import Option, Plugin
from .core.plugins.core.hot_reload import PluginHotReloader, enable_hot_reload
from .core.plugins.core.streaming import (
    StreamingContext,
    StreamingPlugin,
    get_streaming_context,
)
from .core.processing.event_grouping import group_multi_channel_hits
from .core.storage import (
    CacheManager,
    CompressionManager,
    IntegrityChecker,
    MemmapStorage,
    StorageBackend,
)
from .utils.daq import DAQAnalyzer, DAQRun
from .utils.preview import WaveformPreviewer, preview_waveforms

__all__ = [
    "Context",
    "Plugin",
    "Option",
    "ErrorSeverity",
    "PluginError",
    "ErrorContext",
    "WaveformStruct",
    "group_multi_channel_hits",
    "DAQRun",
    "DAQAnalyzer",
    # 执行器管理器
    "get_executor",
    "get_executor_manager",
    "parallel_map",
    "parallel_apply",
    "get_timeout_manager",
    # 执行器配置
    "EXECUTOR_CONFIGS",
    "get_config",
    "register_config",
    # 流式处理
    "StreamingPlugin",
    "StreamingContext",
    "get_streaming_context",
    # 波形预览
    "WaveformPreviewer",
    "preview_waveforms",
    # 插件热重载
    "PluginHotReloader",
    "enable_hot_reload",
    # 存储层
    "MemmapStorage",
    "CacheManager",
    "StorageBackend",
    "CompressionManager",
    "IntegrityChecker",
]
