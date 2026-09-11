"""
Storage 子模块 - 存储层统一接口

提供数据持久化、缓存管理、压缩和完整性检查等功能。

主要组件：
- MemmapStorage: 基于 numpy.memmap 的零拷贝存储
- StorageBackend: 可插拔存储后端接口
- CacheManager: 缓存管理器
- CompressionManager: 压缩管理器
- IntegrityChecker: 数据完整性检查

缓存管理工具（新增）：
- CacheAnalyzer: 缓存扫描与索引
- CacheEntry: 缓存条目元数据
- CacheDiagnostics: 缓存诊断与修复
- CacheCleaner: 智能清理策略
- CacheStatsCollector: 统计收集与报告

向后兼容：
所有导出的类和函数可以通过以下方式导入：
    from waveform_analysis.core.storage import MemmapStorage
    from waveform_analysis.core import MemmapStorage  # 通过 core.__init__.py 兼容
"""

from waveform_analysis._lazy_exports import LazyExport as _LazyExport
from waveform_analysis._lazy_exports import lazy_dir as _lazy_dir
from waveform_analysis._lazy_exports import (
    resolve_lazy_attribute as _resolve_lazy_attribute,
)

_LAZY_EXPORTS: dict[str, _LazyExport] = {
    # Memmap 存储
    "MemmapStorage": (".memmap", "MemmapStorage"),
    "BufferedStreamWriter": (".memmap", "BufferedStreamWriter"),
    # 存储后端
    "StorageBackend": (".backends", "StorageBackend"),
    "SQLiteBackend": (".backends", "SQLiteBackend"),
    "create_storage_backend": (".backends", "create_storage_backend"),
    "validate_storage_backend": (".backends", "validate_storage_backend"),
    # 缓存管理
    "CacheManager": (".cache", "CacheManager"),
    "RuntimeCacheManager": (".cache_manager", "RuntimeCacheManager"),
    # 压缩管理
    "Blosc2Compression": (".compression", "Blosc2Compression"),
    "LZ4Compression": (".compression", "LZ4Compression"),
    "ZstdCompression": (".compression", "ZstdCompression"),
    "GzipCompression": (".compression", "GzipCompression"),
    "CompressionManager": (".compression", "CompressionManager"),
    "get_compression_manager": (".compression", "get_compression_manager"),
    # 完整性检查
    "IntegrityChecker": (".integrity", "IntegrityChecker"),
    "get_integrity_checker": (".integrity", "get_integrity_checker"),
    "compute_file_checksum": (".integrity", "compute_file_checksum"),
    "verify_file_checksum": (".integrity", "verify_file_checksum"),
    # 缓存管理工具
    "CacheAnalyzer": (".cache_analyzer", "CacheAnalyzer"),
    "CacheEntry": (".cache_analyzer", "CacheEntry"),
    "CacheDiagnostics": (".cache_diagnostics", "CacheDiagnostics"),
    "DiagnosticIssue": (".cache_diagnostics", "DiagnosticIssue"),
    "DiagnosticIssueType": (".cache_diagnostics", "DiagnosticIssueType"),
    "CacheCleaner": (".cache_cleaner", "CacheCleaner"),
    "CleanupPlan": (".cache_cleaner", "CleanupPlan"),
    "CleanupStrategy": (".cache_cleaner", "CleanupStrategy"),
    "CacheStatsCollector": (".cache_statistics", "CacheStatsCollector"),
    "CacheStatistics": (".cache_statistics", "CacheStatistics"),
    "format_size": (".cache_utils", "format_size"),
    "format_age": (".cache_utils", "format_age"),
    "CacheEntryFilter": (".cache_utils", "CacheEntryFilter"),
}

__all__ = [
    # Memmap 存储
    "MemmapStorage",
    "BufferedStreamWriter",
    # 存储后端
    "StorageBackend",
    "SQLiteBackend",
    "create_storage_backend",
    "validate_storage_backend",
    # 缓存管理
    "CacheManager",
    "RuntimeCacheManager",
    # 压缩管理
    "Blosc2Compression",
    "LZ4Compression",
    "ZstdCompression",
    "GzipCompression",
    "CompressionManager",
    "get_compression_manager",
    # 完整性检查
    "IntegrityChecker",
    "get_integrity_checker",
    "compute_file_checksum",
    "verify_file_checksum",
    # 缓存管理工具
    "CacheAnalyzer",
    "CacheEntry",
    "CacheDiagnostics",
    "DiagnosticIssue",
    "DiagnosticIssueType",
    "CacheCleaner",
    "CleanupPlan",
    "CleanupStrategy",
    "CacheStatsCollector",
    "CacheStatistics",
    "format_size",
    "format_age",
    "CacheEntryFilter",
]


def __getattr__(name: str) -> object:
    return _resolve_lazy_attribute(name, _LAZY_EXPORTS, globals())


def __dir__() -> list[str]:
    return _lazy_dir(globals(), _LAZY_EXPORTS, __all__)
