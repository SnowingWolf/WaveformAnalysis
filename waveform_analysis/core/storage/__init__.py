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

# Memmap 存储
# 存储后端
from .backends import (
    SQLiteBackend,
    StorageBackend,
    create_storage_backend,
    validate_storage_backend,
)

# 缓存管理
from .cache import CacheManager

# 缓存管理工具
from .cache_analyzer import CacheAnalyzer, CacheEntry
from .cache_cleaner import CacheCleaner, CleanupPlan, CleanupStrategy
from .cache_diagnostics import CacheDiagnostics, DiagnosticIssue, DiagnosticIssueType
from .cache_manager import RuntimeCacheManager
from .cache_statistics import CacheStatistics, CacheStatsCollector

# 压缩管理
from .compression import (
    Blosc2Compression,
    CompressionManager,
    GzipCompression,
    LZ4Compression,
    ZstdCompression,
    get_compression_manager,
)

# 完整性检查
from .integrity import (
    IntegrityChecker,
    compute_file_checksum,
    get_integrity_checker,
    verify_file_checksum,
)
from .memmap import BufferedStreamWriter, MemmapStorage

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
]
