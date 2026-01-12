# -*- coding: utf-8 -*-
"""
Storage 子模块 - 存储层统一接口

提供数据持久化、缓存管理、压缩和完整性检查等功能。

主要组件：
- MemmapStorage: 基于 numpy.memmap 的零拷贝存储
- StorageBackend: 可插拔存储后端接口
- CacheManager: 缓存管理器
- CompressionManager: 压缩管理器
- IntegrityChecker: 数据完整性检查

向后兼容：
所有导出的类和函数可以通过以下方式导入：
    from waveform_analysis.core.storage import MemmapStorage
    from waveform_analysis.core import MemmapStorage  # 通过 core.__init__.py 兼容
"""

# Memmap 存储
from .memmap import MemmapStorage, BufferedStreamWriter

# 存储后端
from .backends import (
    StorageBackend,
    SQLiteBackend,
    create_storage_backend,
    validate_storage_backend,
)

# 缓存管理
from .cache import CacheManager
from .cache_manager import RuntimeCacheManager

# 压缩管理
from .compression import (
    Blosc2Compression,
    LZ4Compression,
    ZstdCompression,
    GzipCompression,
    CompressionManager,
    get_compression_manager,
)

# 完整性检查
from .integrity import (
    IntegrityChecker,
    get_integrity_checker,
    compute_file_checksum,
    verify_file_checksum,
)

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
]
