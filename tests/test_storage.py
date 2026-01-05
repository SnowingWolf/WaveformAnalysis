"""
Storage 模块测试
"""

import json
import os
import time

import numpy as np
import pytest

from waveform_analysis.core.storage import MemmapStorage


class TestMemmapStorage:
    """MemmapStorage 测试"""

    @pytest.fixture
    def storage(self, tmp_path):
        """创建临时存储"""
        return MemmapStorage(str(tmp_path))

    @pytest.fixture
    def sample_dtype(self):
        """创建测试用的 dtype"""
        return np.dtype([("time", "<i8"), ("channel", "<u1"), ("value", "<f8")])

    def test_init_creates_directory(self, tmp_path):
        """测试初始化时创建目录"""
        storage_path = tmp_path / "new_storage"
        assert not storage_path.exists()

        storage = MemmapStorage(str(storage_path))
        assert storage_path.exists()

    def test_get_paths(self, storage):
        """测试路径生成"""
        bin_path, meta_path, lock_path = storage._get_paths("test_key")

        assert bin_path.endswith("test_key.bin")
        assert meta_path.endswith("test_key.json")
        assert lock_path.endswith("test_key.lock")

    def test_save_metadata(self, storage, tmp_path):
        """测试元数据保存"""
        metadata = {"count": 100, "dtype": "<i8", "custom_field": "test_value"}
        storage.save_metadata("test_key", metadata)

        meta_path = tmp_path / "test_key.json"
        assert meta_path.exists()

        with open(meta_path, "r") as f:
            loaded = json.load(f)

        assert loaded["count"] == 100
        assert loaded["dtype"] == "<i8"
        assert loaded["custom_field"] == "test_value"

    def test_get_metadata_not_exists(self, storage):
        """测试获取不存在的元数据"""
        result = storage.get_metadata("nonexistent_key")
        assert result is None

    def test_get_metadata_exists(self, storage, tmp_path):
        """测试获取存在的元数据"""
        metadata = {"count": 50, "test": "value"}
        meta_path = tmp_path / "existing_key.json"
        with open(meta_path, "w") as f:
            json.dump(metadata, f)

        result = storage.get_metadata("existing_key")
        assert result is not None
        assert result["count"] == 50
        assert result["test"] == "value"

    def test_save_stream_empty(self, storage, sample_dtype):
        """测试保存空流"""

        def empty_stream():
            return
            yield  # Make it a generator

        count = storage.save_stream("empty_key", iter([]), sample_dtype)
        assert count == 0

    def test_save_stream_with_data(self, storage, sample_dtype, tmp_path):
        """测试保存有数据的流"""
        data = np.array([(1000, 0, 1.5), (2000, 1, 2.5), (3000, 0, 3.5)], dtype=sample_dtype)

        def data_stream():
            yield data[:2]
            yield data[2:]

        count = storage.save_stream("data_key", data_stream(), sample_dtype)
        assert count == 3

        # 验证文件存在
        assert (tmp_path / "data_key.bin").exists()
        assert (tmp_path / "data_key.json").exists()

    def test_save_stream_cleanup_on_error(self, storage, sample_dtype, tmp_path):
        """测试 save_stream 在写入失败时清理临时文件和锁"""

        def bad_stream():
            # 有效的首个 chunk
            data = np.array([(1000, 0, 1.5)], dtype=sample_dtype)
            yield data
            # 模拟迭代中抛出异常（例如写入失败或生成器错误）
            raise RuntimeError("boom")

        tmp_bin = tmp_path / "bad_key.bin.tmp"
        lock = tmp_path / "bad_key.lock"
        with pytest.raises(Exception):
            storage.save_stream("bad_key", bad_stream(), sample_dtype)

        # 临时文件和锁应已被清理
        assert not tmp_bin.exists()
        assert not lock.exists()

    def test_delete(self, storage, sample_dtype):
        """测试删除数据"""
        data = np.array([(1000, 0, 1.5)], dtype=sample_dtype)
        storage.save_stream("delete_key", [data], sample_dtype)
        assert storage.exists("delete_key")

        storage.delete("delete_key")
        assert not storage.exists("delete_key")

    def test_list_keys(self, storage, sample_dtype):
        """测试列出所有 key"""
        data = np.array([(1000, 0, 1.5)], dtype=sample_dtype)
        storage.save_stream("key1", [data], sample_dtype)
        storage.save_stream("key2", [data], sample_dtype)

        keys = storage.list_keys()
        assert "key1" in keys
        assert "key2" in keys

    def test_get_size(self, storage, sample_dtype):
        """测试获取数据大小"""
        data = np.array([(1000, 0, 1.5)], dtype=sample_dtype)
        storage.save_stream("size_key", [data], sample_dtype)

        size = storage.get_size("size_key")
        assert size > 0
        assert storage.get_size("nonexistent") == 0

    def test_lock_mechanism(self, storage):
        """测试文件锁机制"""
        _, _, lock_path = storage._get_paths("lock_test")

        # Acquire lock
        assert storage._acquire_lock(lock_path)
        # Try to acquire again (should fail if not re-entrant, but our impl uses simple open)
        # Actually our impl uses:
        # with open(lock_path, "w") as f: f.write(str(os.getpid()))
        # It doesn't actually block other processes unless we use fcntl.
        # Let's check the implementation.
        storage._release_lock(lock_path)
        assert not os.path.exists(lock_path)

    def test_acquire_removes_stale_lock(self, storage, tmp_path):
        """测试过期锁会被移除"""
        _, _, lock_path = storage._get_paths("stale_test")

        # 写入一个旧的锁信息（较早的 timestamp）
        stale_info = {"pid": 999999, "timestamp": time.time() - 1000}
        with open(lock_path, "w") as f:
            json.dump(stale_info, f)

        # 通过传入较小的 stale_timeout 确保被认为是过期锁
        assert storage._acquire_lock(lock_path, timeout=1, stale_timeout=1)
        storage._release_lock(lock_path)
        assert not os.path.exists(lock_path)

    def test_acquire_respects_live_lock(self, storage, tmp_path, monkeypatch):
        """如果 PID 被认为是存活的，acquire 不应移除锁"""
        _, _, lock_path = storage._get_paths("live_test")

        stale_info = {"pid": 9999, "timestamp": time.time() - 1000}
        with open(lock_path, "w") as f:
            json.dump(stale_info, f)

        # 模拟 os.kill 不抛异常，表示进程仍然存活
        def fake_kill(pid, sig):
            return None

        monkeypatch.setattr(os, "kill", fake_kill)

        assert not storage._acquire_lock(lock_path, timeout=0.5, stale_timeout=1)
        # 锁文件应保留
        assert os.path.exists(lock_path)

    def test_acquire_removes_stale_lock_when_pid_dead(self, storage, tmp_path, monkeypatch):
        """如果 PID 不存在（os.kill 抛出），应移除锁并获取"""
        _, _, lock_path = storage._get_paths("stale_pid_test")

        stale_info = {"pid": 9999, "timestamp": time.time() - 1000}
        with open(lock_path, "w") as f:
            json.dump(stale_info, f)

        # 模拟 os.kill 抛出 ProcessLookupError，表示进程不存在
        def fake_kill(pid, sig):
            raise ProcessLookupError

        monkeypatch.setattr(os, "kill", fake_kill)

        assert storage._acquire_lock(lock_path, timeout=1, stale_timeout=1)
        storage._release_lock(lock_path)
        assert not os.path.exists(lock_path)

    def test_load_memmap_not_exists(self, storage):
        """测试加载不存在的 memmap"""
        result = storage.load_memmap("nonexistent")
        assert result is None

    def test_save_and_load_memmap(self, storage, sample_dtype):
        """测试保存然后加载 memmap"""
        data = np.array([(1000, 0, 1.5), (2000, 1, 2.5)], dtype=sample_dtype)

        storage.save_stream("roundtrip_key", iter([data]), sample_dtype)

        loaded = storage.load_memmap("roundtrip_key")
        assert loaded is not None
        assert len(loaded) == 2
        assert loaded[0]["time"] == 1000
        assert loaded[1]["channel"] == 1

    def test_exists(self, storage, sample_dtype):
        """测试存在性检查"""
        assert not storage.exists("nonexistent")

        data = np.array([(1000, 0, 1.5)], dtype=sample_dtype)
        storage.save_stream("exists_key", iter([data]), sample_dtype)

        assert storage.exists("exists_key")

    def test_exists_false_on_corruption(self, storage, sample_dtype, tmp_path):
        """当元数据损坏或与二进制不匹配时，exists 应返回 False"""
        data = np.array([(1000, 0, 1.5)], dtype=sample_dtype)
        storage.save_stream("corrupt_key", iter([data]), sample_dtype)

        meta_path = tmp_path / "corrupt_key.json"
        with open(meta_path, "r") as f:
            meta = json.load(f)

        # 篡改元数据使 count 和 shape 不匹配
        meta["count"] = 9999
        meta["shape"] = [9999]
        with open(meta_path, "w") as f:
            json.dump(meta, f)

        assert not storage.exists("corrupt_key")


class TestStorageIntegrity:
    """存储完整性测试"""

    def test_metadata_includes_version(self, tmp_path):
        """测试元数据包含版本信息"""
        storage = MemmapStorage(str(tmp_path))
        dtype = np.dtype("<i8")
        data = np.array([1, 2, 3], dtype=dtype)

        storage.save_stream("version_test", iter([data]), dtype)

        metadata = storage.get_metadata("version_test")
        assert metadata is not None
        assert "storage_version" in metadata
        assert metadata["storage_version"] == MemmapStorage.STORAGE_VERSION

    def test_corrupted_metadata(self, tmp_path):
        """测试损坏的元数据处理"""
        storage = MemmapStorage(str(tmp_path))

        # 写入损坏的 JSON
        meta_path = tmp_path / "corrupted.json"
        with open(meta_path, "w") as f:
            f.write("not valid json {{{")

        # 应该返回 None 而不是抛异常
        result = storage.get_metadata("corrupted")
        assert result is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
