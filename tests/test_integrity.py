"""
测试数据完整性校验功能
"""

import os
import tempfile
import shutil
import pytest
import numpy as np

from waveform_analysis.core.storage.integrity import (
    IntegrityChecker,
    get_integrity_checker,
    compute_file_checksum,
    verify_file_checksum,
)
from waveform_analysis.core.storage import MemmapStorage


class TestIntegrityChecker:
    """测试IntegrityChecker基本功能"""

    def setup_method(self):
        """Setup temporary directory and test file"""
        self.temp_dir = tempfile.mkdtemp()
        self.test_file = os.path.join(self.temp_dir, "test.bin")

        # Create test file
        data = np.random.bytes(1024)
        with open(self.test_file, 'wb') as f:
            f.write(data)

    def teardown_method(self):
        """Cleanup"""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_checker_creation(self):
        """测试创建IntegrityChecker"""
        checker = IntegrityChecker()
        assert checker is not None

    def test_checker_singleton(self):
        """测试全局单例"""
        checker1 = get_integrity_checker()
        checker2 = get_integrity_checker()
        assert checker1 is checker2

    def test_detect_algorithms(self):
        """测试算法检测"""
        checker = IntegrityChecker()
        available = checker._available_algorithms

        # sha256 and md5 should always be available
        assert available['sha256'] is True
        assert available['md5'] is True

    def test_get_default_algorithm(self):
        """测试获取默认算法"""
        checker = IntegrityChecker()
        default = checker.get_default_algorithm()
        assert default in ['xxhash64', 'xxhash32', 'sha256', 'md5']
        assert checker.is_algorithm_available(default)

    def test_compute_checksum_sha256(self):
        """测试计算SHA256 checksum"""
        checker = IntegrityChecker()
        checksum = checker.compute_checksum(self.test_file, 'sha256')

        assert checksum is not None
        assert isinstance(checksum, str)
        assert len(checksum) == 64  # SHA256 produces 64 hex chars

    def test_compute_checksum_md5(self):
        """测试计算MD5 checksum"""
        checker = IntegrityChecker()
        checksum = checker.compute_checksum(self.test_file, 'md5')

        assert checksum is not None
        assert isinstance(checksum, str)
        assert len(checksum) == 32  # MD5 produces 32 hex chars

    def test_compute_checksum_xxhash_if_available(self):
        """测试xxhash checksum(如果可用)"""
        checker = IntegrityChecker()

        if not checker.is_algorithm_available('xxhash64'):
            pytest.skip("xxhash not available")

        checksum = checker.compute_checksum(self.test_file, 'xxhash64')
        assert checksum is not None
        assert isinstance(checksum, str)

    def test_verify_checksum_valid(self):
        """测试验证正确的checksum"""
        checker = IntegrityChecker()

        # Compute checksum
        checksum = checker.compute_checksum(self.test_file, 'sha256')

        # Verify it
        is_valid = checker.verify_checksum(self.test_file, checksum, 'sha256')
        assert is_valid is True

    def test_verify_checksum_invalid(self):
        """测试验证错误的checksum"""
        checker = IntegrityChecker()

        # Use wrong checksum
        wrong_checksum = "0" * 64

        is_valid = checker.verify_checksum(self.test_file, wrong_checksum, 'sha256')
        assert is_valid is False

    def test_checksum_changes_on_file_modification(self):
        """测试文件修改后checksum变化"""
        checker = IntegrityChecker()

        # Compute original checksum
        checksum1 = checker.compute_checksum(self.test_file, 'sha256')

        # Modify file
        with open(self.test_file, 'ab') as f:
            f.write(b"extra data")

        # Compute new checksum
        checksum2 = checker.compute_checksum(self.test_file, 'sha256')

        assert checksum1 != checksum2

    def test_compute_checksum_bytes(self):
        """测试计算bytes数据的checksum"""
        checker = IntegrityChecker()

        data = b"Hello, World!"
        checksum = checker.compute_checksum_bytes(data, 'sha256')

        assert checksum is not None
        assert isinstance(checksum, str)

    def test_scan_directory(self):
        """测试扫描目录"""
        checker = IntegrityChecker()

        # Create multiple test files
        for i in range(3):
            file_path = os.path.join(self.temp_dir, f"test{i}.bin")
            data = np.random.bytes(512)
            with open(file_path, 'wb') as f:
                f.write(data)

        # Scan directory
        results = checker.scan_directory(self.temp_dir, 'sha256', '*.bin')

        assert len(results) >= 3  # At least 3 files (including self.test_file)
        for filename, info in results.items():
            assert 'checksum' in info
            assert 'size' in info
            assert 'algorithm' in info

    def test_convenience_functions(self):
        """测试便捷函数"""
        checksum = compute_file_checksum(self.test_file, 'sha256')
        assert checksum is not None

        is_valid = verify_file_checksum(self.test_file, checksum, 'sha256')
        assert is_valid is True


class TestStorageWithChecksum:
    """测试MemmapStorage的checksum集成"""

    def setup_method(self):
        """Setup temporary directory"""
        self.temp_dir = tempfile.mkdtemp()
        self.test_run_id = "test_run"

    def teardown_method(self):
        """Cleanup"""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_storage_without_checksum(self):
        """测试不启用checksum的存储(默认)"""
        storage = MemmapStorage(self.temp_dir, enable_checksum=False)

        data = np.array([1, 2, 3, 4, 5], dtype=np.int32)
        storage.save_memmap('test_key', data, run_id=self.test_run_id)

        meta = storage.get_metadata('test_key', run_id=self.test_run_id)
        assert 'checksum' not in meta

    def test_storage_with_checksum(self):
        """测试启用checksum的存储"""
        storage = MemmapStorage(
            self.temp_dir,
            enable_checksum=True,
            checksum_algorithm='sha256'
        )

        data = np.array([1, 2, 3, 4, 5], dtype=np.int32)
        storage.save_memmap('test_key', data, run_id=self.test_run_id)

        # Check metadata contains checksum
        meta = storage.get_metadata('test_key', run_id=self.test_run_id)
        assert 'checksum' in meta
        assert 'checksum_algorithm' in meta
        assert meta['checksum_algorithm'] == 'sha256'

        # Load should work
        loaded = storage.load_memmap('test_key', run_id=self.test_run_id)
        assert loaded is not None
        np.testing.assert_array_equal(loaded, data)

    def test_storage_verify_on_load(self):
        """测试加载时验证checksum"""
        # Save with checksum
        storage_save = MemmapStorage(
            self.temp_dir,
            enable_checksum=True,
            verify_on_load=False
        )

        data = np.array([1, 2, 3, 4, 5], dtype=np.int32)
        storage_save.save_memmap('test_key', data, run_id=self.test_run_id)

        # Load with verification enabled
        storage_load = MemmapStorage(
            self.temp_dir,
            enable_checksum=True,
            verify_on_load=True
        )

        loaded = storage_load.load_memmap('test_key', run_id=self.test_run_id)
        assert loaded is not None
        np.testing.assert_array_equal(loaded, data)

    def test_storage_detect_corruption(self):
        """测试检测数据损坏"""
        # Save with checksum
        storage = MemmapStorage(
            self.temp_dir,
            enable_checksum=True,
            verify_on_load=True
        )

        data = np.array([1, 2, 3, 4, 5], dtype=np.int32)
        storage.save_memmap('test_key', data, run_id=self.test_run_id)

        # Corrupt the file
        bin_path = os.path.join(self.temp_dir, self.test_run_id, '_cache', 'test_key.bin')
        with open(bin_path, 'r+b') as f:
            f.seek(0)
            f.write(b'\x00\x00\x00\x00')

        # Loading should fail (or warn and return None)
        loaded = storage.load_memmap('test_key', run_id=self.test_run_id)
        assert loaded is None

    def test_storage_checksum_with_compression(self):
        """测试压缩数据的checksum"""
        storage = MemmapStorage(
            self.temp_dir,
            compression='gzip',
            enable_checksum=True,
            checksum_algorithm='sha256'
        )

        data = np.zeros(100, dtype=np.float64)
        data[:10] = 1.0

        storage.save_memmap('test_compressed', data, run_id=self.test_run_id)

        # Check metadata
        meta = storage.get_metadata('test_compressed', run_id=self.test_run_id)
        assert meta['compressed'] is True
        assert 'checksum' in meta
        assert 'checksum_algorithm' in meta

        # Load and verify
        loaded = storage.load_memmap('test_compressed', run_id=self.test_run_id)
        assert loaded is not None
        np.testing.assert_array_equal(loaded, data)

    def test_verify_integrity_method(self):
        """测试verify_integrity方法"""
        storage = MemmapStorage(
            self.temp_dir,
            enable_checksum=True
        )

        # Save multiple files
        for i in range(3):
            data = np.array([i, i+1, i+2], dtype=np.int32)
            storage.save_memmap(f'test_{i}', data, run_id=self.test_run_id)

        # Verify integrity
        results = storage.verify_integrity(run_id=self.test_run_id, verbose=False)

        assert results['total'] == 3
        assert results['valid'] == 3
        assert results['invalid'] == 0

    def test_verify_integrity_detect_issues(self):
        """测试verify_integrity检测问题"""
        storage = MemmapStorage(
            self.temp_dir,
            enable_checksum=True
        )

        # Save a file
        data = np.array([1, 2, 3], dtype=np.int32)
        storage.save_memmap('test_key', data, run_id=self.test_run_id)

        # Corrupt the file
        bin_path = os.path.join(self.temp_dir, self.test_run_id, '_cache', 'test_key.bin')
        with open(bin_path, 'r+b') as f:
            f.write(b'\xFF' * 12)

        # Verify should detect corruption
        results = storage.verify_integrity(run_id=self.test_run_id, verbose=False)

        assert results['total'] == 1
        assert results['invalid'] == 1
        assert len(results['errors']) == 1


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
