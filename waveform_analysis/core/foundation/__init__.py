# -*- coding: utf-8 -*-
"""
Foundation 子模块 - 框架基础设施

提供异常处理、Mixin、模型、工具函数和进度追踪等基础组件。

主要组件：
- Exceptions: 异常类和错误处理
- Mixins: 功能混合类
- Model: 数据模型
- Utils: 工具函数
- ProgressTracker: 进度追踪

向后兼容：
所有导出的类和函数可以通过以下方式导入：
    from waveform_analysis.core.foundation import PluginError
    from waveform_analysis.core import PluginError  # 通过 core.__init__.py 兼容
"""

# 异常处理
# 文档读取器
from .doc_reader import (
    TOPIC_DOC_MAPPING,
    DocReader,
    find_docs_root,
    get_doc_reader,
)
from .exceptions import (
    ErrorContext,
    ErrorSeverity,
    PluginError,
    PluginTimeoutError,
)

# Mixin
from .mixins import (
    CacheMixin,
    StepMixin,
    chainable_step,
)

# 模型
from .model import (
    EdgeModel,
    LineageGraphModel,
    NodeModel,
    PortModel,
)

# 进度追踪
from .progress import (
    ProgressTracker,
    format_throughput,
    format_time,
    get_global_tracker,
    progress_iter,
    progress_map,
    reset_global_tracker,
    with_progress,
)

# 工具函数
from .utils import (
    LineageStyle,
    OneTimeGenerator,
    Profiler,
    exporter,
)

__all__ = [
    # 异常处理
    "ErrorSeverity",
    "PluginError",
    "ErrorContext",
    "PluginTimeoutError",
    # Mixin
    "CacheMixin",
    "StepMixin",
    "chainable_step",
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
    # 文档读取器
    "DocReader",
    "get_doc_reader",
    "find_docs_root",
    "TOPIC_DOC_MAPPING",
]
