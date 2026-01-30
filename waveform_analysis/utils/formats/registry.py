"""
格式和适配器注册表

提供格式读取器和 DAQ 适配器的注册、查询功能。

Examples:
    >>> from waveform_analysis.utils.formats import register_format, get_format_reader
    >>> reader = get_format_reader("vx2730_csv")
    >>> data = reader.read_file("data.csv")
"""

from typing import Dict, List, Optional, Type

from waveform_analysis.core.foundation.utils import exporter

from .base import FormatReader, FormatSpec

export, __all__ = exporter()

# 格式读取器注册表
_FORMAT_REGISTRY: Dict[str, Type[FormatReader]] = {}

# 格式规范注册表
_FORMAT_SPECS: Dict[str, FormatSpec] = {}


@export
def register_format(
    name: str, reader_class: Type[FormatReader], spec: Optional[FormatSpec] = None
) -> None:
    """注册一个格式读取器

    Args:
        name: 格式名称（唯一标识符）
        reader_class: 读取器类
        spec: 格式规范（可选）

    Examples:
        >>> register_format("my_format", MyReader, my_spec)
    """
    _FORMAT_REGISTRY[name] = reader_class
    if spec is not None:
        _FORMAT_SPECS[name] = spec


@export
def get_format_reader(name: str, **kwargs) -> FormatReader:
    """获取格式读取器实例

    Args:
        name: 格式名称
        **kwargs: 传递给读取器构造函数的额外参数

    Returns:
        格式读取器实例

    Raises:
        ValueError: 如果格式未注册

    Examples:
        >>> reader = get_format_reader("vx2730_csv")
        >>> data = reader.read_files(file_list)
    """
    if name not in _FORMAT_REGISTRY:
        available = list(_FORMAT_REGISTRY.keys())
        raise ValueError(f"未知格式 '{name}'。可用格式: {available}")

    reader_class = _FORMAT_REGISTRY[name]
    spec = _FORMAT_SPECS.get(name)

    if spec is not None:
        return reader_class(spec, **kwargs)
    return reader_class(**kwargs)


@export
def get_format_spec(name: str) -> Optional[FormatSpec]:
    """获取格式规范

    Args:
        name: 格式名称

    Returns:
        格式规范，如果不存在则返回 None
    """
    return _FORMAT_SPECS.get(name)


@export
def list_formats() -> List[str]:
    """列出所有已注册的格式

    Returns:
        格式名称列表
    """
    return list(_FORMAT_REGISTRY.keys())


@export
def is_format_registered(name: str) -> bool:
    """检查格式是否已注册

    Args:
        name: 格式名称

    Returns:
        是否已注册
    """
    return name in _FORMAT_REGISTRY


@export
def unregister_format(name: str) -> bool:
    """注销一个格式

    Args:
        name: 格式名称

    Returns:
        是否成功注销
    """
    removed = False
    if name in _FORMAT_REGISTRY:
        del _FORMAT_REGISTRY[name]
        removed = True
    if name in _FORMAT_SPECS:
        del _FORMAT_SPECS[name]
        removed = True
    return removed
