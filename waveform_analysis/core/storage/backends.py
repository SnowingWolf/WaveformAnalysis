# -*- coding: utf-8 -*-
"""
Storage Backends 模块 - 可插拔存储后端抽象层

提供统一的存储接口，支持多种存储实现：
- MemmapBackend: 基于 numpy.memmap 的零拷贝存储（默认）
- SQLiteBackend: 基于 SQLite 的轻量级数据库存储
- 未来可扩展：S3Backend, RedisBackend, HDF5Backend 等

设计原则：
1. Protocol 定义统一接口，无需继承
2. 每个后端独立实现，互不依赖
3. 向后兼容现有 MemmapStorage
"""

import json
import logging
from typing import Any, Dict, Iterator, List, Optional, Protocol, runtime_checkable

import numpy as np

from waveform_analysis.core.foundation.utils import exporter

export, __all__ = exporter()

logger = logging.getLogger(__name__)


@export
@runtime_checkable
class StorageBackend(Protocol):
    """
    存储后端统一接口（Protocol）

    所有存储后端必须实现以下方法。使用 Protocol 而非抽象基类，
    允许鸭子类型和更灵活的实现。
    """

    def exists(self, key: str) -> bool:
        """
        检查数据是否存在

        Args:
            key: 数据的唯一标识符

        Returns:
            True if data exists, False otherwise
        """
        ...

    def save_memmap(self, key: str, data: np.ndarray, extra_metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        保存 numpy 数组

        Args:
            key: 数据标识符
            data: 要保存的数组
            extra_metadata: 额外的元数据字典
        """
        ...

    def load_memmap(self, key: str) -> Optional[np.ndarray]:
        """
        加载 numpy 数组

        Args:
            key: 数据标识符

        Returns:
            加载的数组，如果不存在返回 None
        """
        ...

    def save_metadata(self, key: str, metadata: Dict[str, Any]) -> None:
        """
        保存元数据

        Args:
            key: 数据标识符
            metadata: 元数据字典
        """
        ...

    def get_metadata(self, key: str) -> Optional[Dict[str, Any]]:
        """
        获取元数据

        Args:
            key: 数据标识符

        Returns:
            元数据字典，如果不存在返回 None
        """
        ...

    def delete(self, key: str) -> None:
        """
        删除数据和元数据

        Args:
            key: 数据标识符
        """
        ...

    def list_keys(self) -> List[str]:
        """
        列出所有存储的键

        Returns:
            键列表
        """
        ...

    def get_size(self, key: str) -> int:
        """
        获取数据大小（字节）

        Args:
            key: 数据标识符

        Returns:
            数据大小，如果不存在返回 0
        """
        ...

    def save_stream(
        self,
        key: str,
        stream: Iterator[np.ndarray],
        dtype: np.dtype,
        extra_metadata: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        保存流式数据

        Args:
            key: 数据标识符
            stream: 数据流迭代器
            dtype: 数据类型
            extra_metadata: 额外元数据

        Returns:
            保存的记录数
        """
        ...

    def finalize_save(
        self,
        key: str,
        count: int,
        dtype: np.dtype,
        extra_metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        完成流式保存（原子化写入）

        Args:
            key: 数据标识符
            count: 记录总数
            dtype: 数据类型
            extra_metadata: 额外元数据
        """
        ...


@export
class SQLiteBackend:
    """
    基于 SQLite 的存储后端

    特点：
    - 轻量级，单文件数据库
    - 支持事务和并发读
    - 适合中小规模数据集
    - 支持元数据查询

    存储结构：
    - arrays 表：存储 numpy 数组（二进制 blob）
    - metadata 表：存储 JSON 元数据
    """

    STORAGE_VERSION = "1.0.0"

    def __init__(self, db_path: str):
        """
        初始化 SQLite 后端

        Args:
            db_path: 数据库文件路径
        """
        import sqlite3

        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self._init_schema()

        logger.info(f"SQLiteBackend initialized at {db_path}")

    def _init_schema(self):
        """初始化数据库表结构"""
        cursor = self.conn.cursor()

        # 数组表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS arrays (
                key TEXT PRIMARY KEY,
                data BLOB NOT NULL,
                dtype TEXT NOT NULL,
                shape TEXT NOT NULL,
                count INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 元数据表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY,
                metadata TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 创建索引
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_created_at ON arrays(created_at)")

        self.conn.commit()

    def exists(self, key: str) -> bool:
        cursor = self.conn.cursor()
        cursor.execute("SELECT 1 FROM arrays WHERE key = ?", (key,))
        return cursor.fetchone() is not None

    def save_memmap(self, key: str, data: np.ndarray, extra_metadata: Optional[Dict[str, Any]] = None) -> None:
        blob = data.tobytes()
        # 保存 dtype 描述符（支持结构化数组）
        # 使用 str(data.dtype) 并在加载时通过 np.dtype() 重建
        dtype_str = str(data.dtype)
        shape_str = json.dumps(data.shape)
        count = len(data)

        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO arrays (key, data, dtype, shape, count)
            VALUES (?, ?, ?, ?, ?)
        """, (key, blob, dtype_str, shape_str, count))

        # 保存元数据
        if extra_metadata:
            metadata = extra_metadata.copy()
        else:
            metadata = {}

        metadata.update({
            "storage_version": self.STORAGE_VERSION,
            "dtype": dtype_str,
            "shape": data.shape,
            "count": count
        })

        self.save_metadata(key, metadata)
        self.conn.commit()

    def load_memmap(self, key: str) -> Optional[np.ndarray]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT data, dtype, shape FROM arrays WHERE key = ?", (key,))
        row = cursor.fetchone()

        if row is None:
            return None

        blob, dtype_str, shape_str = row
        shape = tuple(json.loads(shape_str))

        # 从字符串重建 dtype（支持结构化数组）
        # 结构化数组: "[('time', '<i8'), ('value', '<f8')]"
        # 简单数组: "int64" or "<i8"
        try:
            dtype = np.dtype(eval(dtype_str) if dtype_str.startswith('[') else dtype_str)
        except:
            # 回退：尝试直接解析
            dtype = np.dtype(dtype_str)

        # 从 blob 重建数组
        arr = np.frombuffer(blob, dtype=dtype)
        if len(shape) > 1 or (len(shape) == 1 and shape[0] != len(arr)):
            arr = arr.reshape(shape)

        return arr

    def save_metadata(self, key: str, metadata: Dict[str, Any]) -> None:
        metadata_json = json.dumps(metadata, default=str)

        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO metadata (key, metadata)
            VALUES (?, ?)
        """, (key, metadata_json))
        self.conn.commit()

    def get_metadata(self, key: str) -> Optional[Dict[str, Any]]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT metadata FROM metadata WHERE key = ?", (key,))
        row = cursor.fetchone()

        if row is None:
            return None

        return json.loads(row[0])

    def delete(self, key: str) -> None:
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM arrays WHERE key = ?", (key,))
        cursor.execute("DELETE FROM metadata WHERE key = ?", (key,))
        self.conn.commit()

    def list_keys(self) -> List[str]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT key FROM arrays ORDER BY created_at DESC")
        return [row[0] for row in cursor.fetchall()]

    def get_size(self, key: str) -> int:
        cursor = self.conn.cursor()
        cursor.execute("SELECT LENGTH(data) FROM arrays WHERE key = ?", (key,))
        row = cursor.fetchone()
        return row[0] if row else 0

    def save_stream(
        self,
        key: str,
        stream: Iterator[np.ndarray],
        dtype: np.dtype,
        extra_metadata: Optional[Dict[str, Any]] = None
    ) -> int:
        """累积流数据并保存"""
        chunks = []
        total_count = 0

        for chunk in stream:
            arr = np.asarray(chunk, dtype=dtype)
            chunks.append(arr)
            total_count += len(arr)

        if chunks:
            full_array = np.concatenate(chunks)
            self.save_memmap(key, full_array, extra_metadata)

        return total_count

    def finalize_save(
        self,
        key: str,
        count: int,
        dtype: np.dtype,
        extra_metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """SQLite 后端在 save_stream 中已完成保存，无需额外操作"""
        pass

    def close(self):
        """关闭数据库连接"""
        self.conn.close()

    def __del__(self):
        try:
            self.conn.close()
        except:
            pass


@export
def create_storage_backend(backend_type: str = "memmap", **kwargs) -> StorageBackend:
    """
    存储后端工厂函数

    Args:
        backend_type: 后端类型 ("memmap", "sqlite", 等)
        **kwargs: 传递给后端构造函数的参数

    Returns:
        存储后端实例

    Examples:
        >>> # 使用默认 memmap 后端
        >>> storage = create_storage_backend("memmap", storage_dir="./data")

        >>> # 使用 SQLite 后端
        >>> storage = create_storage_backend("sqlite", db_path="./data.db")
    """
    if backend_type == "memmap":
        from waveform_analysis.core.storage.memmap import MemmapStorage
        storage_dir = kwargs.get("storage_dir", "./strax_data")
        profiler = kwargs.get("profiler", None)
        return MemmapStorage(storage_dir, profiler=profiler)

    elif backend_type == "sqlite":
        db_path = kwargs.get("db_path")
        if not db_path:
            raise ValueError("SQLiteBackend requires 'db_path' parameter")
        return SQLiteBackend(db_path)

    else:
        raise ValueError(f"Unknown storage backend type: {backend_type}")


@export
def validate_storage_backend(backend: Any) -> bool:
    """
    验证对象是否实现了 StorageBackend 接口

    Args:
        backend: 要验证的对象

    Returns:
        True if valid, False otherwise
    """
    return isinstance(backend, StorageBackend)
