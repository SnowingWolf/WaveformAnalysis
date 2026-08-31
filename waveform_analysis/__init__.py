"""
Waveform Analysis - 波形数据分析工具包

一个用于处理和分析数据采集(DAQ)系统波形数据的Python包。
提供数据加载、处理、配对、特征提取和可视化功能。
"""

from waveform_analysis._lazy_exports import LazyExport as _LazyExport
from waveform_analysis._lazy_exports import lazy_dir as _lazy_dir
from waveform_analysis._lazy_exports import (
    resolve_lazy_attribute as _resolve_lazy_attribute,
)

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
    # 位置重建可视化
    "render_position_dashboard",
    "render_position_dashboard_2d",
    # 插件热重载
    "PluginHotReloader",
    "enable_hot_reload",
    # 存储层
    "MemmapStorage",
    "CacheManager",
    "StorageBackend",
    "CompressionManager",
    "IntegrityChecker",
    "plugins",
]


_LAZY_EXPORTS: dict[str, _LazyExport] = {
    "__version__": ("._version", "__version__"),
    # Historical module-level imports remain available without loading their
    # metadata leaf during a plain ``import waveform_analysis``.
    "PackageNotFoundError": ("._version", "PackageNotFoundError"),
    "package_version": ("._version", "package_version"),
    "import_module": ("importlib", "import_module"),
    "Context": (".core.context", "Context"),
    "get_timeout_manager": (".core.execution.timeout", "get_timeout_manager"),
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
    "WaveformStruct": (".core.plugins.builtin.st_waveforms.plugin", "WaveformStruct"),
    "WaveformStructConfig": (
        ".core.plugins.builtin.st_waveforms.plugin",
        "WaveformStructConfig",
    ),
    "Option": (".core.plugins.core.base", "Option"),
    "Plugin": (".core.plugins.core.base", "Plugin"),
    "PluginHotReloader": (".core.plugins.core.hot_reload", "PluginHotReloader"),
    "enable_hot_reload": (".core.plugins.core.hot_reload", "enable_hot_reload"),
    "StreamingContext": (".core.plugins.core.streaming", "StreamingContext"),
    "StreamingPlugin": (".core.plugins.core.streaming", "StreamingPlugin"),
    "get_streaming_context": (".core.plugins.core.streaming", "get_streaming_context"),
    "group_multi_channel_hits": (".core.processing.event_grouping", "group_multi_channel_hits"),
    "CacheManager": (".core.storage.cache", "CacheManager"),
    "CompressionManager": (".core.storage.compression", "CompressionManager"),
    "IntegrityChecker": (".core.storage.integrity", "IntegrityChecker"),
    "MemmapStorage": (".core.storage.memmap", "MemmapStorage"),
    "StorageBackend": (".core.storage.backends", "StorageBackend"),
    "DAQAnalyzer": (".acquisition.daq", "DAQAnalyzer"),
    "DAQRun": (".acquisition.daq", "DAQRun"),
    "render_position_dashboard": (".visualization", "render_position_dashboard"),
    "render_position_dashboard_2d": (".visualization", "render_position_dashboard_2d"),
    "plugins": (".plugins", None),
}


def _resolve_package_version() -> str:
    """从包元数据读取版本，保留历史测试和 monkeypatch 入口。"""
    package_version_fn = globals().get("package_version")
    if package_version_fn is None:
        package_version_fn = _resolve_lazy_attribute("package_version", _LAZY_EXPORTS, globals())
    not_found_error = globals().get("PackageNotFoundError")
    if not_found_error is None:
        not_found_error = _resolve_lazy_attribute("PackageNotFoundError", _LAZY_EXPORTS, globals())
    try:
        return package_version_fn("waveform-analysis")
    except not_found_error:
        # 未安装分发包时（如直接源码运行）提供可解析回退版本。
        return "0.0.0+unknown"


# Retain the historical private map name for callers that inspected it.
_LAZY_ATTRS = _LAZY_EXPORTS


def __getattr__(name: str):
    return _resolve_lazy_attribute(name, _LAZY_EXPORTS, globals())


def __dir__():
    return _lazy_dir(globals(), _LAZY_EXPORTS, __all__)
