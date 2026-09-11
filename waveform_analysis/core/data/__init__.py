"""
Data 子模块 - 数据查询和导出

提供时间范围查询、批量处理和数据导出功能。

主要组件：
- TimeRangeQueryEngine: 时间范围查询引擎
- BatchProcessor: 批量处理器
- DataExporter: 数据导出器

向后兼容：
所有导出的类和函数可以通过以下方式导入：
    from waveform_analysis.core.data import TimeRangeQueryEngine
    from waveform_analysis.core import TimeRangeQueryEngine  # 通过 core.__init__.py 兼容
"""

from waveform_analysis._lazy_exports import LazyExport as _LazyExport
from waveform_analysis._lazy_exports import (
    _install_lazy_export_module as _install_lazy_export_module,
)
from waveform_analysis._lazy_exports import lazy_dir as _lazy_dir
from waveform_analysis._lazy_exports import (
    resolve_lazy_attribute as _resolve_lazy_attribute,
)

_LAZY_EXPORTS: dict[str, _LazyExport] = {
    # 时间查询
    "TimeIndex": (".query", "TimeIndex"),
    "TimeRangeQueryEngine": (".query", "TimeRangeQueryEngine"),
    "TimeRangeCache": (".query", "TimeRangeCache"),
    "RecordsView": (".records_view", "RecordsView"),
    "records_view": (".records_view", "records_view"),
    # 批量处理和导出
    "BatchProcessor": (".batch_processor", "BatchProcessor"),
    "DataExporter": (".export", "DataExporter"),
    "batch_export": (".export", "batch_export"),
}

_install_lazy_export_module(globals())

__all__ = [
    # 时间查询
    "TimeIndex",
    "TimeRangeQueryEngine",
    "TimeRangeCache",
    "RecordsView",
    "records_view",
    # 批量处理和导出
    "BatchProcessor",
    "DataExporter",
    "batch_export",
]


def __getattr__(name: str) -> object:
    return _resolve_lazy_attribute(name, _LAZY_EXPORTS, globals())


def __dir__() -> list[str]:
    return _lazy_dir(globals(), _LAZY_EXPORTS, __all__)
