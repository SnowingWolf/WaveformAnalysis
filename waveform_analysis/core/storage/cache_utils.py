"""
缓存工具函数 - 缓存管理模块的共享工具。

提供格式化、过滤等通用功能，避免代码重复。
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING, List, Optional

from ..foundation.utils import exporter

if TYPE_CHECKING:
    from .cache_analyzer import CacheEntry

export, __all__ = exporter()


@export
def format_size(size_bytes: int) -> str:
    """格式化字节大小为人类可读字符串

    Args:
        size_bytes: 字节大小

    Returns:
        人类可读的大小字符串（如 "1.5 MB", "2.3 GB"）

    Examples:
        >>> format_size(1024)
        '1.0 KB'
        >>> format_size(1024 * 1024)
        '1.0 MB'
        >>> format_size(1024 * 1024 * 1024)
        '1.00 GB'
    """
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


@export
def format_age(age_days: float) -> str:
    """格式化天数为人类可读字符串

    Args:
        age_days: 天数

    Returns:
        人类可读的时间字符串（如 "2.5h", "3.2d", "1.5mo", "2.1y"）

    Examples:
        >>> format_age(0.5)
        '12.0h'
        >>> format_age(5)
        '5.0d'
        >>> format_age(60)
        '2.0mo'
        >>> format_age(400)
        '1.1y'
    """
    if age_days < 1:
        return f"{age_days * 24:.1f}h"
    elif age_days < 30:
        return f"{age_days:.1f}d"
    elif age_days < 365:
        return f"{age_days / 30:.1f}mo"
    else:
        return f"{age_days / 365:.1f}y"


@export
@dataclass
class CacheEntryFilter:
    """可复用的缓存条目过滤器

    提供声明式的过滤条件，支持多条件组合。

    Attributes:
        run_id: 按运行 ID 过滤
        data_name: 按数据类型名称过滤
        min_size: 最小大小（字节）
        max_size: 最大大小（字节）
        min_age_days: 最小年龄（天）
        max_age_days: 最大年龄（天）
        compressed_only: 仅压缩条目（True）或仅未压缩（False）

    Examples:
        >>> # 过滤大于 1MB 的条目
        >>> filter = CacheEntryFilter(min_size=1024*1024)
        >>> large_entries = filter.filter(all_entries)
        >>>
        >>> # 过滤特定 run 的旧条目
        >>> filter = CacheEntryFilter(run_id='run_001', min_age_days=30)
        >>> old_entries = filter.filter(all_entries)
    """

    run_id: Optional[str] = None
    data_name: Optional[str] = None
    min_size: Optional[int] = None
    max_size: Optional[int] = None
    min_age_days: Optional[float] = None
    max_age_days: Optional[float] = None
    compressed_only: Optional[bool] = None

    def matches(self, entry: "CacheEntry") -> bool:
        """检查条目是否匹配所有过滤条件

        Args:
            entry: 要检查的缓存条目

        Returns:
            True 如果条目匹配所有非 None 的过滤条件
        """
        if self.run_id and entry.run_id != self.run_id:
            return False
        if self.data_name and entry.data_name != self.data_name:
            return False
        if self.min_size and entry.size_bytes < self.min_size:
            return False
        if self.max_size and entry.size_bytes > self.max_size:
            return False
        if self.min_age_days and entry.age_days < self.min_age_days:
            return False
        if self.max_age_days and entry.age_days > self.max_age_days:
            return False
        if self.compressed_only is not None and entry.compressed != self.compressed_only:
            return False
        return True

    def filter(self, entries: List["CacheEntry"]) -> List["CacheEntry"]:
        """过滤条目列表

        Args:
            entries: 要过滤的条目列表

        Returns:
            匹配所有过滤条件的条目列表
        """
        return [e for e in entries if self.matches(e)]
