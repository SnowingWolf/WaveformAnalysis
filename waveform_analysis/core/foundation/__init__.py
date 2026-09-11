"""
Foundation 子模块 - 框架基础设施

提供异常处理、模型、工具函数和进度追踪等基础组件。

主要组件：
- Exceptions: 异常类和错误处理
- Model: 数据模型
- Utils: 工具函数
- ProgressTracker: 进度追踪

向后兼容：
所有导出的类和函数可以通过以下方式导入：
    from waveform_analysis.core.foundation import PluginError
    from waveform_analysis.core import PluginError  # 通过 core.__init__.py 兼容
"""

from waveform_analysis._lazy_exports import LazyExport as _LazyExport
from waveform_analysis._lazy_exports import lazy_dir as _lazy_dir
from waveform_analysis._lazy_exports import (
    resolve_lazy_attribute as _resolve_lazy_attribute,
)

_LAZY_EXPORTS: dict[str, _LazyExport] = {
    # 异常处理
    "ErrorSeverity": (".exceptions", "ErrorSeverity"),
    "PluginError": (".exceptions", "PluginError"),
    "ErrorContext": (".exceptions", "ErrorContext"),
    "PluginTimeoutError": (".exceptions", "PluginTimeoutError"),
    # 模型
    "PortModel": (".model", "PortModel"),
    "NodeModel": (".model", "NodeModel"),
    "EdgeModel": (".model", "EdgeModel"),
    "LineageGraphModel": (".model", "LineageGraphModel"),
    # 工具函数
    "exporter": (".utils", "exporter"),
    "Profiler": (".utils", "Profiler"),
    "LineageStyle": (".utils", "LineageStyle"),
    "OneTimeGenerator": (".utils", "OneTimeGenerator"),
    # 进度追踪
    "ProgressTracker": (".progress", "ProgressTracker"),
    "with_progress": (".progress", "with_progress"),
    "progress_iter": (".progress", "progress_iter"),
    "progress_map": (".progress", "progress_map"),
    "get_global_tracker": (".progress", "get_global_tracker"),
    "reset_global_tracker": (".progress", "reset_global_tracker"),
    "format_time": (".progress", "format_time"),
    "format_throughput": (".progress", "format_throughput"),
}

__all__ = [
    # 异常处理
    "ErrorSeverity",
    "PluginError",
    "ErrorContext",
    "PluginTimeoutError",
    # 模型
    "PortModel",
    "NodeModel",
    "EdgeModel",
    "LineageGraphModel",
    # 工具函数
    "exporter",
    "Profiler",
    "LineageStyle",
    "OneTimeGenerator",
    # 进度追踪
    "ProgressTracker",
    "with_progress",
    "progress_iter",
    "progress_map",
    "get_global_tracker",
    "reset_global_tracker",
    "format_time",
    "format_throughput",
]


def __getattr__(name: str) -> object:
    return _resolve_lazy_attribute(name, _LAZY_EXPORTS, globals())


def __dir__() -> list[str]:
    return _lazy_dir(globals(), _LAZY_EXPORTS, __all__)
