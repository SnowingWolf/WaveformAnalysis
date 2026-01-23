# -*- coding: utf-8 -*-
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

# 时间查询
from .query import (
    TimeIndex,
    TimeRangeQueryEngine,
    TimeRangeCache,
)

# 批量处理和导出
from .batch_processor import BatchProcessor
from .export import DataExporter, batch_export

__all__ = [
    # 时间查询
    "TimeIndex",
    "TimeRangeQueryEngine",
    "TimeRangeCache",
    # 批量处理和导出
    "BatchProcessor",
    "DataExporter",
    "batch_export",
]
