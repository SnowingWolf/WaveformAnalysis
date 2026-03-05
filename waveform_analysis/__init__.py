"""
Waveform Analysis - 波形数据分析工具包

一个用于处理和分析数据采集(DAQ)系统波形数据的Python包。
提供数据加载、处理、配对、特征提取和可视化功能。
"""

from importlib import import_module
from typing import Dict, Optional, Tuple

__version__ = "0.1.0"
__author__ = "Your Name"

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


_LAZY_ATTRS: Dict[str, Tuple[str, Optional[str]]] = {
    "Context": (".core.context", "Context"),
    "get_timeout_manager": (".core.execution", "get_timeout_manager"),
    "EXECUTOR_CONFIGS": (".core.execution.config", "EXECUTOR_CONFIGS"),
    "get_config": (".core.execution.config", "get_config"),
    "register_config": (".core.execution.config", "register_config"),
    "get_executor": (".core.execution.manager", "get_executor"),
    "get_executor_manager": (".core.execution.manager", "get_executor_manager"),
    "parallel_apply": (".core.execution.manager", "parallel_apply"),
    "parallel_map": (".core.execution.manager", "parallel_map"),
    "ErrorContext": (".core.foundation.exceptions", "ErrorContext"),
    "ErrorSeverity": (".core.foundation.exceptions", "ErrorSeverity"),
    "PluginError": (".core.foundation.exceptions", "PluginError"),
    "WaveformStruct": (".core.plugins.builtin.cpu.waveforms", "WaveformStruct"),
    "WaveformStructConfig": (".core.plugins.builtin.cpu.waveforms", "WaveformStructConfig"),
    "Option": (".core.plugins.core.base", "Option"),
    "Plugin": (".core.plugins.core.base", "Plugin"),
    "PluginHotReloader": (".core.plugins.core.hot_reload", "PluginHotReloader"),
    "enable_hot_reload": (".core.plugins.core.hot_reload", "enable_hot_reload"),
    "StreamingContext": (".core.plugins.core.streaming", "StreamingContext"),
    "StreamingPlugin": (".core.plugins.core.streaming", "StreamingPlugin"),
    "get_streaming_context": (".core.plugins.core.streaming", "get_streaming_context"),
    "group_multi_channel_hits": (".core.processing.event_grouping", "group_multi_channel_hits"),
    "CacheManager": (".core.storage", "CacheManager"),
    "CompressionManager": (".core.storage", "CompressionManager"),
    "IntegrityChecker": (".core.storage", "IntegrityChecker"),
    "MemmapStorage": (".core.storage", "MemmapStorage"),
    "StorageBackend": (".core.storage", "StorageBackend"),
    "DAQAnalyzer": (".utils.daq", "DAQAnalyzer"),
    "DAQRun": (".utils.daq", "DAQRun"),
    "WaveformPreviewer": (".utils.preview", "WaveformPreviewer"),
    "preview_waveforms": (".utils.preview", "preview_waveforms"),
}


def __getattr__(name: str):
    if name in _LAZY_ATTRS:
        module_name, attr_name = _LAZY_ATTRS[name]
        module = import_module(module_name, __name__)
        value = getattr(module, attr_name) if attr_name else module
        globals()[name] = value
        return value
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


def __dir__():
    return sorted(set(globals()) | set(__all__) | set(_LAZY_ATTRS))
