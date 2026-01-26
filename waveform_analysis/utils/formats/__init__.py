# -*- coding: utf-8 -*-
"""
DAQ 数据格式适配器

提供统一的 DAQ 数据格式读取接口，支持不同的文件格式和目录结构。

核心组件:
- FormatSpec: 格式规范数据类
- ColumnMapping: CSV 列映射配置
- TimestampUnit: 时间戳单位枚举
- FormatReader: 格式读取器抽象基类
- DirectoryLayout: 目录结构配置
- DAQAdapter: 完整的 DAQ 适配器

内置适配器:
- vx2730: CAEN VX2730 数字化仪（CSV 格式）

Examples:
    基础用法（使用默认 VX2730 适配器）:
    >>> from waveform_analysis.utils.formats import get_adapter
    >>> adapter = get_adapter("vx2730")
    >>> channel_files = adapter.scan_run("DAQ", "run_001")
    >>> data = adapter.load_channel("DAQ", "run_001", channel=0)

    使用格式读取器:
    >>> from waveform_analysis.utils.formats import get_format_reader
    >>> reader = get_format_reader("vx2730_csv")
    >>> data = reader.read_files(['CH0_0.CSV', 'CH0_1.CSV'])

    自定义格式:
    >>> from waveform_analysis.utils.formats import (
    ...     FormatSpec, ColumnMapping, TimestampUnit,
    ...     GenericCSVReader, register_format
    ... )
    >>> my_spec = FormatSpec(
    ...     name="my_format",
    ...     columns=ColumnMapping(timestamp=3),
    ...     timestamp_unit=TimestampUnit.NANOSECONDS,
    ...     delimiter=",",
    ... )
    >>> register_format("my_format", GenericCSVReader, my_spec)
"""

# 基础类
# DAQ 适配器
from .adapter import (
    DAQAdapter,
    get_adapter,
    is_adapter_registered,
    list_adapters,
    register_adapter,
    unregister_adapter,
)
from .base import (
    ColumnMapping,
    FormatReader,
    FormatSpec,
    TimestampUnit,
)

# 目录布局
from .directory import (
    FLAT_LAYOUT,
    DirectoryLayout,
)

# 通用 CSV 读取器
from .generic import GenericCSVReader

# 格式注册表
from .registry import (
    get_format_reader,
    get_format_spec,
    is_format_registered,
    list_formats,
    register_format,
    unregister_format,
)

# VX2730 完整适配器（包含格式规范、目录布局、读取器）
from .vx2730 import (
    VX2730_ADAPTER,
    VX2730_LAYOUT,
    VX2730_SPEC,
    VX2730Reader,
    VX2730Spec,
)
from .v1725 import (
    V1725_ADAPTER,
    V1725_LAYOUT,
    V1725_SPEC,
    V1725Adapter,
    V1725Reader,
    V1725Spec,
)

# 自动注册内置格式
register_format("vx2730_csv", VX2730Reader, VX2730_SPEC)
register_format("v1725_bin", V1725Reader, V1725_SPEC)

__all__ = [
    # 基础类
    "ColumnMapping",
    "FormatReader",
    "FormatSpec",
    "TimestampUnit",
    # 通用读取器
    "GenericCSVReader",
    # 注册表
    "get_format_reader",
    "get_format_spec",
    "is_format_registered",
    "list_formats",
    "register_format",
    "unregister_format",
    # 目录布局
    "DirectoryLayout",
    "FLAT_LAYOUT",
    # DAQ 适配器
    "DAQAdapter",
    "get_adapter",
    "is_adapter_registered",
    "list_adapters",
    "register_adapter",
    "unregister_adapter",
    # VX2730 适配器
    "VX2730Reader",
    "VX2730_ADAPTER",
    "VX2730_LAYOUT",
    "VX2730_SPEC",
    "VX2730Spec",
    # V1725 adapter
    "V1725Reader",
    "V1725Adapter",
    "V1725_ADAPTER",
    "V1725_LAYOUT",
    "V1725_SPEC",
    "V1725Spec",
]
