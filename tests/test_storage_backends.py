"""
测试可插拔存储后端
"""

import os
import tempfile

import numpy as np
import pytest

from waveform_analysis.core.storage.backends import (
    SQLiteBackend,
    StorageBackend,
    create_storage_backend,
    validate_storage_backend,
)
from waveform_analysis.core.storage import MemmapStorage
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.core.base import Plugin


class TestStorageBackendProtocol:
    """测试存储后端 Protocol 接口"""

    def test_memmap_storage_is_valid_backend(self, tmp_path):
        """测试 MemmapStorage 实现了 StorageBackend 接口"""
        storage = MemmapStorage(str(tmp_path))
        assert validate_storage_backend(storage)
        assert isinstance(storage, StorageBackend)

    def test_sqlite_backend_is_valid_backend(self, tmp_path):
        """测试 SQLiteBackend 实现了 StorageBackend 接口"""
        db_path = tmp_path / "test.db"
        storage = SQLiteBackend(str(db_path))
        assert validate_storage_backend(storage)
        assert isinstance(storage, StorageBackend)


class TestSQLiteBackend:
    """测试 SQLite 存储后端"""

    @pytest.fixture
    def backend(self, tmp_path):
        """创建临时 SQLite 后端"""
        db_path = tmp_path / "test.db"
        return SQLiteBackend(str(db_path))

    def test_init_creates_database(self, tmp_path):
        """测试初始化创建数据库文件"""
        db_path = tmp_path / "test.db"
        assert not db_path.exists()

        backend = SQLiteBackend(str(db_path))
        assert db_path.exists()

        # 验证表结构
        cursor = backend.conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}
        assert "arrays" in tables
        assert "metadata" in tables

    def test_save_and_load_array(self, backend):
        """测试保存和加载数组"""
        data = np.array([1, 2, 3, 4, 5], dtype=np.int64)

        backend.save_memmap("test_key", data)
        assert backend.exists("test_key")

        loaded = backend.load_memmap("test_key")
        assert loaded is not None
        np.testing.assert_array_equal(loaded, data)

    def test_save_and_load_structured_array(self, backend):
        """测试保存和加载结构化数组"""
        dtype = np.dtype([("time", "i8"), ("value", "f8")])
        data = np.array([(1000, 1.5), (2000, 2.5), (3000, 3.5)], dtype=dtype)

        backend.save_memmap("struct_key", data)
        loaded = backend.load_memmap("struct_key")

        assert loaded is not None
        np.testing.assert_array_equal(loaded, data)
        assert loaded.dtype == data.dtype

    def test_save_with_metadata(self, backend):
        """测试保存数组时附加元数据"""
        data = np.array([1, 2, 3])
        metadata = {"lineage": {"plugin": "TestPlugin"}, "custom_field": "value"}

        backend.save_memmap("key_with_meta", data, extra_metadata=metadata)

        loaded_meta = backend.get_metadata("key_with_meta")
        assert loaded_meta is not None
        assert "lineage" in loaded_meta
        assert loaded_meta["custom_field"] == "value"
        assert loaded_meta["storage_version"] == backend.STORAGE_VERSION

    def test_load_nonexistent_key(self, backend):
        """测试加载不存在的键"""
        result = backend.load_memmap("nonexistent")
        assert result is None

    def test_get_nonexistent_metadata(self, backend):
        """测试获取不存在的元数据"""
        result = backend.get_metadata("nonexistent")
        assert result is None

    def test_exists(self, backend):
        """测试 exists 方法"""
        assert not backend.exists("test_key")

        data = np.array([1, 2, 3])
        backend.save_memmap("test_key", data)

        assert backend.exists("test_key")

    def test_delete(self, backend):
        """测试删除数据"""
        data = np.array([1, 2, 3])
        backend.save_memmap("delete_key", data)
        assert backend.exists("delete_key")

        backend.delete("delete_key")
        assert not backend.exists("delete_key")
        assert backend.load_memmap("delete_key") is None

    def test_list_keys(self, backend):
        """测试列出所有键"""
        backend.save_memmap("key1", np.array([1]))
        backend.save_memmap("key2", np.array([2]))
        backend.save_memmap("key3", np.array([3]))

        keys = backend.list_keys()
        assert "key1" in keys
        assert "key2" in keys
        assert "key3" in keys
        assert len(keys) == 3

    def test_get_size(self, backend):
        """测试获取数据大小"""
        data = np.array([1, 2, 3, 4, 5], dtype=np.int64)
        backend.save_memmap("size_key", data)

        size = backend.get_size("size_key")
        assert size > 0
        assert size == data.nbytes

        assert backend.get_size("nonexistent") == 0

    def test_save_stream(self, backend):
        """测试保存流式数据"""
        dtype = np.dtype("i8")

        def data_stream():
            yield np.array([1, 2, 3], dtype=dtype)
            yield np.array([4, 5], dtype=dtype)
            yield np.array([6, 7, 8, 9], dtype=dtype)

        count = backend.save_stream("stream_key", data_stream(), dtype)
        assert count == 9

        loaded = backend.load_memmap("stream_key")
        assert loaded is not None
        np.testing.assert_array_equal(loaded, np.array([1, 2, 3, 4, 5, 6, 7, 8, 9]))

    def test_replace_existing_data(self, backend):
        """测试替换已存在的数据"""
        backend.save_memmap("replace_key", np.array([1, 2, 3]))
        backend.save_memmap("replace_key", np.array([4, 5, 6, 7]))

        loaded = backend.load_memmap("replace_key")
        np.testing.assert_array_equal(loaded, np.array([4, 5, 6, 7]))


class TestStorageBackendFactory:
    """测试存储后端工厂函数"""

    def test_create_memmap_backend(self, tmp_path):
        """测试创建 memmap 后端"""
        storage = create_storage_backend("memmap", storage_dir=str(tmp_path))
        assert isinstance(storage, MemmapStorage)
        assert validate_storage_backend(storage)

    def test_create_sqlite_backend(self, tmp_path):
        """测试创建 SQLite 后端"""
        db_path = tmp_path / "test.db"
        storage = create_storage_backend("sqlite", db_path=str(db_path))
        assert isinstance(storage, SQLiteBackend)
        assert validate_storage_backend(storage)

    def test_create_sqlite_without_db_path_raises(self):
        """测试创建 SQLite 后端时缺少 db_path 参数"""
        with pytest.raises(ValueError, match="requires 'db_path'"):
            create_storage_backend("sqlite")

    def test_create_unknown_backend_raises(self):
        """测试创建未知类型的后端"""
        with pytest.raises(ValueError, match="Unknown storage backend"):
            create_storage_backend("unknown_type")


class TestContextWithCustomStorage:
    """测试 Context 使用自定义存储后端"""

    def test_context_with_sqlite_backend(self, tmp_path):
        """测试 Context 使用 SQLite 后端"""
        db_path = tmp_path / "test.db"
        storage = SQLiteBackend(str(db_path))

        ctx = Context(storage=storage)
        assert ctx.storage is storage
        assert isinstance(ctx.storage, SQLiteBackend)

    def test_context_with_factory_created_backend(self, tmp_path):
        """测试 Context 使用工厂函数创建的后端"""
        db_path = tmp_path / "test.db"
        storage = create_storage_backend("sqlite", db_path=str(db_path))

        ctx = Context(storage=storage)
        assert isinstance(ctx.storage, SQLiteBackend)

    def test_context_plugin_data_with_sqlite(self, tmp_path):
        """测试使用 SQLite 后端的插件数据流"""

        class SimplePlugin(Plugin):
            provides = "test_data"
            save_when = "always"  # 确保数据被保存
            output_dtype = np.dtype("i8")

            def compute(self, context, run_id):
                return np.array([1, 2, 3, 4, 5])

        db_path = tmp_path / "test.db"
        storage = SQLiteBackend(str(db_path))
        ctx = Context(storage=storage)
        ctx.register_plugin_(SimplePlugin())

        data = ctx.get_data("run_001", "test_data")
        np.testing.assert_array_equal(data, np.array([1, 2, 3, 4, 5]))

        # 验证数据存储在 SQLite 中
        # 因为 key 包含 lineage hash，我们列出所有 key 并检查是否包含 test_data
        keys = storage.list_keys()
        assert any("test_data" in key for key in keys), f"Expected test_data in keys, got: {keys}"

    def test_context_default_storage_is_memmap(self, tmp_path):
        """测试 Context 默认使用 memmap 存储"""
        ctx = Context(storage_dir=str(tmp_path))
        assert isinstance(ctx.storage, MemmapStorage)


class TestStorageBackendComparison:
    """测试不同存储后端的行为一致性"""

    @pytest.fixture(params=["memmap", "sqlite"])
    def storage_backend(self, request, tmp_path):
        """参数化fixture：提供不同的存储后端"""
        if request.param == "memmap":
            return MemmapStorage(str(tmp_path))
        elif request.param == "sqlite":
            db_path = tmp_path / "test.db"
            return SQLiteBackend(str(db_path))

    def test_basic_operations_consistent(self, storage_backend):
        """测试基本操作在不同后端上的一致性"""
        data = np.array([10, 20, 30, 40, 50], dtype=np.int64)

        # 保存
        storage_backend.save_memmap("key", data)

        # 存在性检查
        assert storage_backend.exists("key")

        # 加载
        loaded = storage_backend.load_memmap("key")
        np.testing.assert_array_equal(loaded, data)

        # 元数据
        metadata = {"test": "value"}
        storage_backend.save_metadata("key", metadata)
        loaded_meta = storage_backend.get_metadata("key")
        assert loaded_meta["test"] == "value"

        # 删除
        storage_backend.delete("key")
        assert not storage_backend.exists("key")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
