"""
测试压缩功能
"""

import os
import tempfile
import shutil
import pytest
import numpy as np

from waveform_analysis.core.storage.compression import (
    Blosc2Compression,
    LZ4Compression,
    ZstdCompression,
    GzipCompression,
    CompressionManager,
    get_compression_manager,
)
from waveform_analysis.core.storage import MemmapStorage


class TestCompressionBackends:
    """测试各种压缩后端"""

    def setup_method(self):
        """Setup test data"""
        # Create test data
        self.small_data = b"Hello, World!" * 100
        self.large_data = np.random.randint(0, 255, size=10000, dtype=np.uint8).tobytes()

    def test_gzip_compression(self):
        """测试Gzip压缩(总是可用)"""
        backend = GzipCompression(compresslevel=6)
        assert backend.is_available()
        assert backend.name == "gzip-6"
        assert backend.extension == ".gz"

        compressed = backend.compress(self.small_data)
        decompressed = backend.decompress(compressed)
        assert decompressed == self.small_data
        assert len(compressed) < len(self.small_data)

    def test_blosc2_if_available(self):
        """测试Blosc2压缩(如果可用)"""
        backend = Blosc2Compression(cname='zstd', clevel=5)

        if not backend.is_available():
            pytest.skip("blosc2 not available")

        assert backend.name == "blosc2-zstd"
        assert backend.extension == ".blosc2"

        compressed = backend.compress(self.large_data)
        decompressed = backend.decompress(compressed)
        assert decompressed == self.large_data
        assert len(compressed) < len(self.large_data)

    def test_lz4_if_available(self):
        """测试LZ4压缩(如果可用)"""
        backend = LZ4Compression(compression_level=0)

        if not backend.is_available():
            pytest.skip("lz4 not available")

        assert backend.name == "lz4-0"
        assert backend.extension == ".lz4"

        compressed = backend.compress(self.small_data)
        decompressed = backend.decompress(compressed)
        assert decompressed == self.small_data

    def test_zstd_if_available(self):
        """测试Zstd压缩(如果可用)"""
        backend = ZstdCompression(level=3)

        if not backend.is_available():
            pytest.skip("zstandard not available")

        assert backend.name == "zstd-3"
        assert backend.extension == ".zst"

        compressed = backend.compress(self.small_data)
        decompressed = backend.decompress(compressed)
        assert decompressed == self.small_data
        assert len(compressed) < len(self.small_data)


class TestCompressionManager:
    """测试CompressionManager"""

    def test_get_backend_by_name(self):
        """测试通过名称获取backend"""
        manager = CompressionManager()

        # Gzip应该总是可用
        backend = manager.get_backend('gzip')
        assert backend.is_available()
        assert backend.name.startswith('gzip')

    def test_get_backend_with_fallback(self):
        """测试fallback机制"""
        manager = CompressionManager()

        # 尝试获取可能不存在的backend,应该fallback到gzip
        backend = manager.get_backend('nonexistent', fallback=True)
        assert backend.is_available()

    def test_list_available(self):
        """测试列出可用backend"""
        manager = CompressionManager()
        available = manager.list_available()

        assert len(available) >= 1  # 至少有gzip
        assert all(isinstance(b, dict) for b in available)
        assert all('name' in b and 'speed_priority' in b for b in available)

    def test_singleton(self):
        """测试全局单例"""
        manager1 = get_compression_manager()
        manager2 = get_compression_manager()
        assert manager1 is manager2

    def test_benchmark(self):
        """测试benchmark功能"""
        manager = CompressionManager()
        test_data = b"Test data" * 1000

        results = manager.benchmark(test_data, backends=['gzip'], repeats=2)

        assert 'gzip' in results
        assert 'compress_time_ms' in results['gzip']
        assert 'decompress_time_ms' in results['gzip']
        assert 'compression_ratio' in results['gzip']
        assert results['gzip']['compression_ratio'] > 1.0  # 应该有压缩效果


class TestMemmapStorageCompression:
    """测试MemmapStorage的压缩功能"""

    def setup_method(self):
        """Setup temporary directory"""
        self.temp_dir = tempfile.mkdtemp()
        print(f"\nTest directory: {self.temp_dir}")

    def teardown_method(self):
        """Cleanup"""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_storage_without_compression(self):
        """测试无压缩存储(默认行为)"""
        storage = MemmapStorage(self.temp_dir)

        # Create test data
        data = np.array([1, 2, 3, 4, 5], dtype=np.int32)

        # Save
        storage.save_memmap('test_key', data)

        # Check metadata
        meta = storage.get_metadata('test_key')
        assert meta is not None
        assert meta.get('compressed', False) is False
        assert 'compression' not in meta

        # Load
        loaded = storage.load_memmap('test_key')
        assert loaded is not None
        np.testing.assert_array_equal(loaded, data)

        # Should be memmap
        assert isinstance(loaded, np.memmap)

    def test_storage_with_gzip_compression(self):
        """测试Gzip压缩存储"""
        storage = MemmapStorage(self.temp_dir, compression='gzip')

        # Create test data (highly compressible)
        data = np.zeros(1000, dtype=np.float64)
        data[:100] = 1.0

        # Save
        storage.save_memmap('test_compressed', data)

        # Check metadata
        meta = storage.get_metadata('test_compressed')
        assert meta is not None
        assert meta['compressed'] is True
        assert meta['compression'] == 'gzip'
        assert 'compression_ratio' in meta
        assert meta['compression_ratio'] > 1.0  # 应该有压缩效果

        # Check compressed file exists
        bin_path = os.path.join(self.temp_dir, 'test_compressed.bin')
        compressed_path = bin_path + '.gz'
        assert os.path.exists(compressed_path)
        assert not os.path.exists(bin_path)  # 原始文件应该被删除

        # Load
        loaded = storage.load_memmap('test_compressed')
        assert loaded is not None
        np.testing.assert_array_equal(loaded, data)

        # Should NOT be memmap (compressed data is loaded into memory)
        assert not isinstance(loaded, np.memmap)

    def test_storage_exists_with_compression(self):
        """测试exists()方法支持压缩文件"""
        storage = MemmapStorage(self.temp_dir, compression='gzip')

        data = np.array([1, 2, 3], dtype=np.int32)
        storage.save_memmap('test_exists', data)

        assert storage.exists('test_exists')

    def test_storage_structured_array_compression(self):
        """测试structured array的压缩"""
        storage = MemmapStorage(self.temp_dir, compression='gzip')

        # Create structured array (like waveform records)
        dtype = np.dtype([
            ('timestamp', 'i8'),
            ('channel', 'i2'),
            ('value', 'f4'),
        ])
        data = np.zeros(100, dtype=dtype)
        data['timestamp'] = np.arange(100)
        data['channel'] = np.random.randint(0, 4, 100)
        data['value'] = np.random.randn(100)

        # Save and load
        storage.save_memmap('structured_test', data)
        loaded = storage.load_memmap('structured_test')

        assert loaded is not None
        assert loaded.dtype == data.dtype
        np.testing.assert_array_equal(loaded, data)

    def test_backward_compatibility(self):
        """测试向后兼容性:旧版本数据应该可以加载"""
        # Create old version data (without compression)
        storage_old = MemmapStorage(self.temp_dir)
        data = np.array([1, 2, 3, 4, 5], dtype=np.int32)
        storage_old.save_memmap('old_data', data)

        # Load with new storage (compression aware)
        storage_new = MemmapStorage(self.temp_dir, compression='gzip')
        loaded = storage_new.load_memmap('old_data')

        assert loaded is not None
        np.testing.assert_array_equal(loaded, data)

    def test_load_compressed_with_different_backend(self):
        """测试用不同的backend加载压缩数据"""
        # Save with gzip
        storage_save = MemmapStorage(self.temp_dir, compression='gzip')
        data = np.array([1, 2, 3, 4, 5], dtype=np.int32)
        storage_save.save_memmap('test_key', data)

        # Load with no compression configured (should still work)
        storage_load = MemmapStorage(self.temp_dir)
        loaded = storage_load.load_memmap('test_key')

        assert loaded is not None
        np.testing.assert_array_equal(loaded, data)


class TestCompressionPerformance:
    """测试压缩性能"""

    def setup_method(self):
        """Setup test data"""
        # Create realistic waveform data
        self.waveform_data = np.zeros(10000, dtype=np.dtype([
            ('baseline', 'f8'),
            ('timestamp', 'i8'),
            ('event_length', 'i8'),
            ('channel', 'i2'),
            ('wave', 'f4', (800,)),
        ]))

        self.waveform_data['timestamp'] = np.arange(10000)
        self.waveform_data['baseline'] = 100.0
        self.waveform_data['event_length'] = 800
        self.waveform_data['channel'] = np.random.randint(0, 4, 10000)
        self.waveform_data['wave'] = np.random.randn(10000, 800).astype(np.float32)

    def test_compression_effectiveness(self):
        """测试压缩效果"""
        manager = get_compression_manager()
        data_bytes = self.waveform_data.tobytes()

        # Only test gzip (always available)
        results = manager.benchmark(data_bytes, backends=['gzip'], repeats=2)

        print("\nCompression Results:")
        for name, stats in results.items():
            print(f"{name}:")
            print(f"  Compression time: {stats['compress_time_ms']:.2f}ms")
            print(f"  Decompression time: {stats['decompress_time_ms']:.2f}ms")
            print(f"  Compression ratio: {stats['compression_ratio']:.2f}x")
            print(f"  Compressed size: {stats['compressed_size_mb']:.2f}MB")

        assert results['gzip']['compression_ratio'] > 1.0


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
