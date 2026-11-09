"""
Storage 模块测试
"""

from concurrent.futures import ThreadPoolExecutor
import fcntl
import json
import os
from threading import Event

import numpy as np
import pandas as pd
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

    @pytest.fixture
    def test_run_id(self):
        """测试用的 run_id"""
        return "test_run"

    def test_init_creates_directory(self, tmp_path):
        """测试初始化时创建目录"""
        storage_path = tmp_path / "new_storage"
        assert not storage_path.exists()

        MemmapStorage(str(storage_path))
        assert storage_path.exists()

    def test_get_paths(self, storage, tmp_path, test_run_id):
        """测试路径生成"""
        bin_path, meta_path, lock_path = storage._get_paths("test_key", test_run_id)

        assert bin_path.endswith("test_key.bin")
        assert meta_path.endswith("test_key.json")
        assert lock_path.endswith("test_key.lock")
        # 验证路径包含 run_id
        assert test_run_id in bin_path
        assert not (tmp_path / test_run_id).exists()

    @pytest.mark.parametrize(
        ("method_name", "expected"),
        [
            ("get_metadata", None),
            ("load_memmap", None),
            ("load_dataframe", None),
            ("exists", False),
            ("get_size", 0),
            ("delete", None),
        ],
    )
    def test_missing_key_does_not_create_run_directory(
        self, storage, tmp_path, test_run_id, method_name, expected
    ):
        assert getattr(storage, method_name)("missing", test_run_id) == expected
        assert not (tmp_path / test_run_id).exists()

    def test_save_metadata(self, storage, tmp_path, test_run_id):
        """测试元数据保存"""
        metadata = {"count": 100, "dtype": "<i8", "custom_field": "test_value"}
        storage.save_metadata("test_key", metadata, test_run_id)

        meta_path = tmp_path / test_run_id / "_cache" / "test_key.json"
        assert meta_path.exists()

        with open(meta_path) as f:
            loaded = json.load(f)

        assert loaded["count"] == 100
        assert loaded["dtype"] == "<i8"
        assert loaded["custom_field"] == "test_value"

    def test_get_metadata_not_exists(self, storage, test_run_id):
        """测试获取不存在的元数据"""
        result = storage.get_metadata("nonexistent_key", test_run_id)
        assert result is None

    def test_get_metadata_exists(self, storage, tmp_path, test_run_id):
        """测试获取存在的元数据"""
        metadata = {"count": 50, "test": "value"}
        # 创建分层目录结构
        meta_dir = tmp_path / test_run_id / "_cache"
        meta_dir.mkdir(parents=True, exist_ok=True)
        meta_path = meta_dir / "existing_key.json"
        with open(meta_path, "w") as f:
            json.dump(metadata, f)

        result = storage.get_metadata("existing_key", test_run_id)
        assert result is not None
        assert result["count"] == 50
        assert result["test"] == "value"

    def test_save_stream_empty(self, storage, sample_dtype, test_run_id):
        """测试保存空流"""

        def empty_stream():
            return
            yield  # Make it a generator

        count = storage.save_stream("empty_key", iter([]), sample_dtype, run_id=test_run_id)
        assert count == 0

    def test_save_stream_with_data(self, storage, sample_dtype, tmp_path, test_run_id):
        """测试保存有数据的流"""
        data = np.array([(1000, 0, 1.5), (2000, 1, 2.5), (3000, 0, 3.5)], dtype=sample_dtype)

        def data_stream():
            yield data[:2]
            yield data[2:]

        count = storage.save_stream("data_key", data_stream(), sample_dtype, run_id=test_run_id)
        assert count == 3

        # 验证文件存在（分层结构）
        data_dir = tmp_path / test_run_id / "_cache"
        assert (data_dir / "data_key.bin").exists()
        assert (data_dir / "data_key.json").exists()

    def test_save_stream_cleanup_on_error(self, storage, sample_dtype, tmp_path, test_run_id):
        """失败时清理临时文件并释放锁，保留共享锁文件。"""

        def bad_stream():
            # 有效的首个 chunk
            data = np.array([(1000, 0, 1.5)], dtype=sample_dtype)
            yield data
            # 模拟迭代中抛出异常（例如写入失败或生成器错误）
            raise RuntimeError("boom")

        data_dir = tmp_path / test_run_id / "_cache"
        tmp_bin = data_dir / "bad_key.bin.tmp"
        lock = data_dir / "bad_key.lock"
        with pytest.raises(Exception):
            storage.save_stream("bad_key", bad_stream(), sample_dtype, run_id=test_run_id)

        # 临时文件已清理，稳定的锁 inode 可以再次获取。
        assert not tmp_bin.exists()
        assert lock.exists()
        lock_fd = storage._acquire_lock(str(lock), timeout=0.1)
        try:
            assert lock_fd is not None
        finally:
            storage._release_lock(lock_fd, str(lock))

    def test_save_stream_cleanup_does_not_remove_next_writer_tempfile(
        self, storage, sample_dtype, tmp_path, test_run_id, monkeypatch
    ):
        key = "consecutive_writers"
        first_data = np.array([(1000, 0, 1.5)], dtype=sample_dtype)
        next_data = np.array([(2000, 1, 2.5)], dtype=sample_dtype)
        next_writer_opened = Event()
        finish_next_writer = Event()
        release_lock = storage._release_lock
        next_write = None

        def next_stream():
            # save_stream has opened its temporary file before consuming us.
            next_writer_opened.set()
            assert finish_next_writer.wait(5)
            yield next_data

        with ThreadPoolExecutor(max_workers=1) as executor:

            def start_next_writer_after_release(fd, lock_path):
                nonlocal next_write
                release_lock(fd, lock_path)
                if next_write is None:
                    next_write = executor.submit(
                        storage.save_stream, key, next_stream(), sample_dtype, run_id=test_run_id
                    )
                    assert next_writer_opened.wait(5)

            monkeypatch.setattr(storage, "_release_lock", start_next_writer_after_release)
            try:
                storage.save_stream(key, [first_data], sample_dtype, run_id=test_run_id)
                assert (tmp_path / test_run_id / "_cache" / f"{key}.bin.tmp").exists()
            finally:
                finish_next_writer.set()
            assert next_write.result(timeout=5) == 1

        np.testing.assert_array_equal(storage.load_memmap(key, test_run_id), next_data)

    def test_save_stream_releases_lock_when_tempfile_check_fails(
        self, storage, sample_dtype, test_run_id, monkeypatch
    ):
        key = "cleanup_failure"
        data = np.array([(1000, 0, 1.5)], dtype=sample_dtype)
        bin_path, _, lock_path = storage._get_paths(key, test_run_id)
        exists = os.path.exists

        def fail_tempfile_check(path):
            if path == bin_path + ".tmp":
                raise RuntimeError("cleanup inspection failed")
            return exists(path)

        monkeypatch.setattr(os.path, "exists", fail_tempfile_check)
        with pytest.raises(RuntimeError, match="cleanup inspection failed"):
            storage.save_stream(key, [data], sample_dtype, run_id=test_run_id)

        lock_fd = storage._acquire_lock(lock_path, timeout=0.01)
        try:
            assert lock_fd is not None
        finally:
            storage._release_lock(lock_fd, lock_path)

    @pytest.mark.parametrize("replacement", ["binary", "metadata"])
    def test_failed_replacement_preserves_previous_cache(
        self, storage, sample_dtype, test_run_id, monkeypatch, replacement
    ):
        key = "replace_key"
        data = np.array([(1000, 0, 1.5)], dtype=sample_dtype)
        storage.save_stream(key, [data], sample_dtype, run_id=test_run_id)
        metadata = storage.get_metadata(key, test_run_id)
        bin_path, meta_path, _ = storage._get_paths(key, test_run_id)
        target = bin_path if replacement == "binary" else meta_path
        replace = os.replace

        def fail_replacement(source, destination):
            if destination == target:
                raise OSError("replacement failed")
            return replace(source, destination)

        monkeypatch.setattr(os, "replace", fail_replacement)
        with pytest.raises(OSError, match="replacement failed"):
            if replacement == "binary":
                storage.save_stream(key, [data[:0], data], sample_dtype, run_id=test_run_id)
            else:
                storage.save_metadata(key, {"replacement": True}, test_run_id)

        assert storage.get_metadata(key, test_run_id) == metadata
        np.testing.assert_array_equal(storage.load_memmap(key, test_run_id), data)

    def test_delete(self, storage, sample_dtype, test_run_id):
        """测试删除数据"""
        data = np.array([(1000, 0, 1.5)], dtype=sample_dtype)
        storage.save_stream("delete_key", [data], sample_dtype, run_id=test_run_id)
        assert storage.exists("delete_key", test_run_id)

        storage.delete("delete_key", test_run_id)
        assert not storage.exists("delete_key", test_run_id)

    def test_delete_preserves_writer_lock_and_data_on_timeout(
        self, storage, sample_dtype, test_run_id, monkeypatch
    ):
        key = "locked_delete"
        data = np.array([(1000, 0, 1.5)], dtype=sample_dtype)
        storage.save_stream(key, [data], sample_dtype, run_id=test_run_id)
        _, _, lock_path = storage._get_paths(key, test_run_id)
        lock_fd = storage._acquire_lock(lock_path)
        inode = os.fstat(lock_fd).st_ino
        acquire_lock = storage._acquire_lock
        monkeypatch.setattr(storage, "_acquire_lock", lambda path: acquire_lock(path, timeout=0.01))
        try:
            with pytest.raises(RuntimeError, match="Could not acquire lock"):
                storage.delete(key, test_run_id)
            assert storage.exists(key, test_run_id)
            assert os.stat(lock_path).st_ino == inode
        finally:
            storage._release_lock(lock_fd, lock_path)

        storage.delete(key, test_run_id)
        assert not storage.exists(key, test_run_id)
        assert os.stat(lock_path).st_ino == inode

    def test_list_keys(self, storage, sample_dtype, test_run_id):
        """测试列出所有 key"""
        data = np.array([(1000, 0, 1.5)], dtype=sample_dtype)
        storage.save_stream("key1", [data], sample_dtype, run_id=test_run_id)
        storage.save_stream("key2", [data], sample_dtype, run_id=test_run_id)

        keys = storage.list_keys(test_run_id)
        assert "key1" in keys
        assert "key2" in keys

    def test_get_size(self, storage, sample_dtype, test_run_id):
        """测试获取数据大小"""
        data = np.array([(1000, 0, 1.5)], dtype=sample_dtype)
        storage.save_stream("size_key", [data], sample_dtype, run_id=test_run_id)

        size = storage.get_size("size_key", test_run_id)
        assert size > 0
        assert storage.get_size("nonexistent", test_run_id) == 0

    def test_lock_mechanism(self, storage, test_run_id):
        """测试文件锁机制（fcntl based）"""
        _, _, lock_path = storage._get_paths("lock_test", test_run_id)

        # Acquire lock
        lock_fd = storage._acquire_lock(lock_path)
        assert lock_fd is not None, "Should acquire lock successfully"

        inode = os.fstat(lock_fd).st_ino
        storage._release_lock(lock_fd, lock_path)
        assert os.stat(lock_path).st_ino == inode

    def test_old_inode_waiter_excludes_new_contenders(self, storage, test_run_id, monkeypatch):
        """Open a waiting fd before release, then contend through the same path."""
        _, _, lock_path = storage._get_paths("lock_handoff", test_run_id)
        owner_fd = storage._acquire_lock(lock_path)
        inode = os.fstat(owner_fd).st_ino
        waiter_fd = None
        newcomer_fd = None
        flock = fcntl.flock

        def release_owner_before_waiter_flock(fd, operation):
            nonlocal owner_fd
            if owner_fd is not None and operation == (fcntl.LOCK_EX | fcntl.LOCK_NB):
                # _acquire_lock has already opened the waiting fd on the old inode.
                released_fd = owner_fd
                owner_fd = None
                storage._release_lock(released_fd, lock_path)
            return flock(fd, operation)

        monkeypatch.setattr(fcntl, "flock", release_owner_before_waiter_flock)
        try:
            waiter_fd = storage._acquire_lock(lock_path)
            assert waiter_fd is not None
            assert os.fstat(waiter_fd).st_ino == inode
            newcomer_fd = storage._acquire_lock(lock_path, timeout=0.01)
            assert newcomer_fd is None
            assert os.stat(lock_path).st_ino == inode
        finally:
            for fd in (owner_fd, waiter_fd, newcomer_fd):
                storage._release_lock(fd, lock_path)

    def test_release_without_descriptor_keeps_active_lock(self, storage, test_run_id):
        _, _, lock_path = storage._get_paths("active_lock", test_run_id)
        lock_fd = storage._acquire_lock(lock_path)
        contender_fd = None
        try:
            storage._release_lock(None, lock_path)
            contender_fd = storage._acquire_lock(lock_path, timeout=0.01)
            assert contender_fd is None
        finally:
            storage._release_lock(contender_fd, lock_path)
            storage._release_lock(lock_fd, lock_path)

    def test_load_memmap_not_exists(self, storage, test_run_id):
        """测试加载不存在的 memmap"""
        result = storage.load_memmap("nonexistent", test_run_id)
        assert result is None

    def test_save_and_load_memmap(self, storage, sample_dtype, test_run_id):
        """测试保存然后加载 memmap"""
        data = np.array([(1000, 0, 1.5), (2000, 1, 2.5)], dtype=sample_dtype)

        storage.save_stream("roundtrip_key", iter([data]), sample_dtype, run_id=test_run_id)

        loaded = storage.load_memmap("roundtrip_key", test_run_id)
        assert loaded is not None
        assert len(loaded) == 2
        assert loaded[0]["time"] == 1000
        assert loaded[1]["channel"] == 1

    def test_exists(self, storage, sample_dtype, test_run_id):
        """测试存在性检查"""
        assert not storage.exists("nonexistent", test_run_id)

        data = np.array([(1000, 0, 1.5)], dtype=sample_dtype)
        storage.save_stream("exists_key", iter([data]), sample_dtype, run_id=test_run_id)

        assert storage.exists("exists_key", test_run_id)

    def test_dataframe_pickle_fallback_when_parquet_engine_missing(
        self, storage, tmp_path, test_run_id, monkeypatch
    ):
        """缺少 parquet 引擎时，DataFrame 缓存应自动回退为 pickle。"""
        key = "df_fallback_key"
        df = pd.DataFrame({"timestamp": [1, 2], "value": [10.0, 20.0]})

        def _raise_no_engine(*args, **kwargs):
            raise ImportError("Unable to find a usable parquet engine")

        monkeypatch.setattr(pd.DataFrame, "to_parquet", _raise_no_engine)

        storage.save_dataframe(key, df, run_id=test_run_id)
        storage.save_metadata(key, {"type": "dataframe"}, run_id=test_run_id)

        data_dir = tmp_path / test_run_id / "_cache"
        assert (data_dir / f"{key}.pkl").exists()
        assert not (data_dir / f"{key}.parquet").exists()
        assert storage.exists(key, test_run_id)

        loaded = storage.load_dataframe(key, run_id=test_run_id)
        pd.testing.assert_frame_equal(loaded, df)

        integrity = storage.verify_integrity(run_id=test_run_id, verbose=False)
        assert integrity["invalid"] == 0

    def test_exists_false_on_corruption(self, storage, sample_dtype, tmp_path, test_run_id):
        """当元数据损坏或与二进制不匹配时，exists 应返回 False"""
        data = np.array([(1000, 0, 1.5)], dtype=sample_dtype)
        storage.save_stream("corrupt_key", iter([data]), sample_dtype, run_id=test_run_id)

        meta_path = tmp_path / test_run_id / "_cache" / "corrupt_key.json"
        with open(meta_path) as f:
            meta = json.load(f)

        # 篡改元数据使 count 和 shape 不匹配
        meta["count"] = 9999
        meta["shape"] = [9999]
        with open(meta_path, "w") as f:
            json.dump(meta, f)

        assert not storage.exists("corrupt_key", test_run_id)


class TestStorageIntegrity:
    """存储完整性测试"""

    @pytest.fixture
    def test_run_id(self):
        """测试用的 run_id"""
        return "test_run"

    def test_metadata_includes_version(self, tmp_path, test_run_id):
        """测试元数据包含版本信息"""
        storage = MemmapStorage(str(tmp_path))
        dtype = np.dtype("<i8")
        data = np.array([1, 2, 3], dtype=dtype)

        storage.save_stream("version_test", iter([data]), dtype, run_id=test_run_id)

        metadata = storage.get_metadata("version_test", test_run_id)
        assert metadata is not None
        assert "storage_version" in metadata
        assert metadata["storage_version"] == MemmapStorage.STORAGE_VERSION

    def test_corrupted_metadata(self, tmp_path, test_run_id):
        """测试损坏的元数据处理"""
        storage = MemmapStorage(str(tmp_path))

        # 写入损坏的 JSON
        meta_dir = tmp_path / test_run_id / "_cache"
        meta_dir.mkdir(parents=True, exist_ok=True)
        meta_path = meta_dir / "corrupted.json"
        with open(meta_path, "w") as f:
            f.write("not valid json {{{")

        # 应该返回 None 而不是抛异常
        result = storage.get_metadata("corrupted", test_run_id)
        assert result is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
