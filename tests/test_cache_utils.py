"""
cache_utils 模块测试
"""

import os

import pytest

from waveform_analysis.core.storage.cache import WATCH_SIG_KEY, CacheManager


class TestWatchSigKey:
    """WATCH_SIG_KEY 常量测试"""

    def test_watch_sig_key_value(self):
        """测试常量值"""
        assert WATCH_SIG_KEY == "__watch_sig__"

    def test_watch_sig_key_is_string(self):
        """测试常量类型"""
        assert isinstance(WATCH_SIG_KEY, str)


class TestCacheManager:
    """CacheManager 类测试"""

    def test_compute_watch_signature_none_attr(self):
        """测试监视 None 属性的签名"""

        class MockObj:
            attr = None

        sig = CacheManager.compute_watch_signature(MockObj(), ["attr"])
        assert isinstance(sig, str)
        assert len(sig) == 40  # SHA1 哈希长度

    def test_compute_watch_signature_file_path(self, tmp_path):
        """测试监视文件路径的签名"""
        # 创建测试文件
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello world")

        class MockObj:
            file_path = str(test_file)

        sig1 = CacheManager.compute_watch_signature(MockObj(), ["file_path"])
        assert isinstance(sig1, str)
        assert len(sig1) == 40

        # 修改文件内容后签名应该变化
        test_file.write_text("hello world updated")
        sig2 = CacheManager.compute_watch_signature(MockObj(), ["file_path"])
        assert sig1 != sig2

    def test_compute_watch_signature_file_list(self, tmp_path):
        """测试监视文件列表的签名"""
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        file1.write_text("content1")
        file2.write_text("content2")

        class MockObj:
            files = [str(file1), str(file2)]

        sig = CacheManager.compute_watch_signature(MockObj(), ["files"])
        assert isinstance(sig, str)
        assert len(sig) == 40

    def test_compute_watch_signature_multiple_attrs(self, tmp_path):
        """测试监视多个属性的签名"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        class MockObj:
            name = "test"
            file_path = str(test_file)
            count = 42

        sig = CacheManager.compute_watch_signature(MockObj(), ["name", "file_path", "count"])
        assert isinstance(sig, str)
        assert len(sig) == 40

    def test_save_and_load_joblib(self, tmp_path):
        """测试 joblib 后端的保存和加载"""
        pytest.importorskip("joblib")

        data = {"key1": [1, 2, 3], "key2": "value"}
        path = str(tmp_path / "cache.joblib")

        # 保存
        result = CacheManager.save_data(path, data, backend="joblib")
        assert result is True
        assert os.path.exists(path)

        # 加载
        loaded = CacheManager.load_data(path, backend="joblib")
        assert loaded is not None
        assert loaded["key1"] == [1, 2, 3]
        assert loaded["key2"] == "value"

    def test_save_and_load_pickle(self, tmp_path):
        """测试 pickle 后端的保存和加载"""
        data = {"key1": [1, 2, 3], "key2": "value"}
        path = str(tmp_path / "cache.pkl")

        # 保存
        result = CacheManager.save_data(path, data, backend="pickle")
        assert result is True
        assert os.path.exists(path)

        # 加载
        loaded = CacheManager.load_data(path, backend="pickle")
        assert loaded is not None
        assert loaded["key1"] == [1, 2, 3]
        assert loaded["key2"] == "value"

    def test_load_nonexistent_file(self, tmp_path):
        """测试加载不存在的文件"""
        path = str(tmp_path / "nonexistent.joblib")
        result = CacheManager.load_data(path)
        assert result is None

    def test_save_unsupported_backend(self, tmp_path):
        """测试不支持的后端"""
        path = str(tmp_path / "cache.dat")
        result = CacheManager.save_data(path, {"key": "value"}, backend="unsupported")
        assert result is False

    def test_load_unsupported_backend(self, tmp_path):
        """测试不支持的后端加载"""
        # 创建一个空文件
        path = str(tmp_path / "cache.dat")
        with open(path, "w") as f:
            f.write("dummy")

        result = CacheManager.load_data(path, backend="unsupported")
        assert result is None

    def test_delete_cache(self, tmp_path):
        """测试删除缓存"""
        path = str(tmp_path / "cache.joblib")

        # 创建文件
        CacheManager.save_data(path, {"key": "value"}, backend="joblib")
        assert os.path.exists(path)

        # 删除
        result = CacheManager.delete_cache(path)
        assert result is True
        assert not os.path.exists(path)

    def test_delete_nonexistent_cache(self, tmp_path):
        """测试删除不存在的缓存"""
        path = str(tmp_path / "nonexistent.joblib")
        result = CacheManager.delete_cache(path)
        assert result is True

    def test_save_creates_directory(self, tmp_path):
        """测试保存时创建目录"""
        nested_path = str(tmp_path / "nested" / "dir" / "cache.joblib")

        result = CacheManager.save_data(nested_path, {"key": "value"}, backend="joblib")
        assert result is True
        assert os.path.exists(nested_path)


class TestCacheManagerIntegration:
    """CacheManager 集成测试"""

    def test_signature_with_watch_sig_key(self, tmp_path):
        """测试签名与 WATCH_SIG_KEY 的集成"""
        test_file = tmp_path / "data.txt"
        test_file.write_text("initial content")

        class MockObj:
            data_file = str(test_file)

        # 计算签名
        sig = CacheManager.compute_watch_signature(MockObj(), ["data_file"])

        # 保存带签名的数据
        cache_data = {
            "result": [1, 2, 3],
            WATCH_SIG_KEY: sig,
        }
        cache_path = str(tmp_path / "cache.joblib")
        CacheManager.save_data(cache_path, cache_data)

        # 加载并验证签名
        loaded = CacheManager.load_data(cache_path)
        assert loaded[WATCH_SIG_KEY] == sig

        # 修改源文件后签名应该不匹配
        test_file.write_text("modified content")
        new_sig = CacheManager.compute_watch_signature(MockObj(), ["data_file"])
        assert new_sig != loaded[WATCH_SIG_KEY]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
