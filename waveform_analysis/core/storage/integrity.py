"""
数据完整性校验模块 - 提供高效的checksum计算和验证

支持多种哈希算法:
- xxhash64: 极快速度(推荐用于大文件)
- sha256: 安全性高(用于关键数据)
- md5: 向后兼容
"""

import logging
import os
from typing import Any, Dict, Literal
import warnings

from waveform_analysis.core.foundation.utils import exporter

logger = logging.getLogger(__name__)
export, __all__ = exporter()

# 算法类型
ChecksumAlgorithm = Literal["xxhash64", "sha256", "md5"]


# ===========================
# Integrity Checker
# ===========================


@export
class IntegrityChecker:
    """
    数据完整性校验器

    提供高效的checksum计算和验证功能

    使用示例:
        checker = IntegrityChecker()
        checksum = checker.compute_checksum('/path/to/file.bin', 'xxhash64')
        is_valid = checker.verify_checksum('/path/to/file.bin', checksum, 'xxhash64')
    """

    # 算法优先级(速度优先)
    ALGORITHM_PRIORITY = ["xxhash64", "xxhash32", "sha256", "md5"]

    def __init__(self):
        """
        初始化完整性检查器

        检测并选择最快的可用哈希算法（优先级：xxhash64 > xxhash32 > sha256 > md5）
        """
        self._available_algorithms = self._detect_available_algorithms()

    def _detect_available_algorithms(self) -> Dict[str, bool]:
        """检测可用的哈希算法"""
        available = {}

        # Check xxhash
        try:
            import xxhash

            available["xxhash64"] = True
            available["xxhash32"] = True
        except ImportError:
            available["xxhash64"] = False
            available["xxhash32"] = False

        # sha256 and md5 are always available (hashlib)
        available["sha256"] = True
        available["md5"] = True

        return available

    def get_default_algorithm(self) -> str:
        """获取默认的哈希算法(基于可用性和性能)"""
        for algo in self.ALGORITHM_PRIORITY:
            if self._available_algorithms.get(algo, False):
                return algo
        return "sha256"  # Fallback

    def is_algorithm_available(self, algorithm: str) -> bool:
        """检查指定算法是否可用"""
        return self._available_algorithms.get(algorithm, False)

    def compute_checksum(
        self, file_path: str, algorithm: str = "xxhash64", chunk_size: int = 8192
    ) -> str:
        """
        计算文件的checksum

        Args:
            file_path: 文件路径
            algorithm: 哈希算法 ('xxhash64', 'sha256', 'md5')
            chunk_size: 读取块大小(字节)

        Returns:
            Hex编码的checksum字符串

        Raises:
            ValueError: 算法不可用或不支持
            FileNotFoundError: 文件不存在
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        if not self.is_algorithm_available(algorithm):
            # Try fallback
            warnings.warn(f"Algorithm '{algorithm}' not available, using fallback")
            algorithm = self.get_default_algorithm()

        # Create hash object
        hasher = self._create_hasher(algorithm)

        # Read and update hash
        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                hasher.update(chunk)

        # Return hex digest
        return hasher.hexdigest()

    def compute_checksum_bytes(self, data: bytes, algorithm: str = "xxhash64") -> str:
        """
        计算bytes数据的checksum

        Args:
            data: 二进制数据
            algorithm: 哈希算法

        Returns:
            Hex编码的checksum字符串
        """
        if not self.is_algorithm_available(algorithm):
            warnings.warn(f"Algorithm '{algorithm}' not available, using fallback")
            algorithm = self.get_default_algorithm()

        hasher = self._create_hasher(algorithm)
        hasher.update(data)
        return hasher.hexdigest()

    def verify_checksum(
        self, file_path: str, expected_checksum: str, algorithm: str = "xxhash64"
    ) -> bool:
        """
        验证文件的checksum

        Args:
            file_path: 文件路径
            expected_checksum: 期望的checksum值
            algorithm: 哈希算法

        Returns:
            True if checksum matches, False otherwise
        """
        try:
            actual_checksum = self.compute_checksum(file_path, algorithm)
            return actual_checksum == expected_checksum
        except Exception as e:
            logger.error(f"Failed to verify checksum for {file_path}: {e}")
            return False

    def _create_hasher(self, algorithm: str):
        """创建哈希对象"""
        if algorithm in ["xxhash64", "xxhash32"]:
            import xxhash

            if algorithm == "xxhash64":
                return xxhash.xxh64()
            else:
                return xxhash.xxh32()
        elif algorithm in ["sha256", "md5"]:
            import hashlib

            return hashlib.new(algorithm)
        else:
            raise ValueError(f"Unsupported algorithm: {algorithm}")

    def scan_directory(
        self, directory: str, algorithm: str = "xxhash64", pattern: str = "*.bin"
    ) -> Dict[str, Dict[str, Any]]:
        """
        扫描目录中的所有文件并计算checksum

        Args:
            directory: 目录路径
            algorithm: 哈希算法
            pattern: 文件匹配模式

        Returns:
            {filename: {checksum, size, algorithm}}
        """
        import glob

        results = {}
        file_pattern = os.path.join(directory, pattern)

        for file_path in glob.glob(file_pattern):
            if not os.path.isfile(file_path):
                continue

            try:
                checksum = self.compute_checksum(file_path, algorithm)
                size = os.path.getsize(file_path)

                results[os.path.basename(file_path)] = {
                    "checksum": checksum,
                    "size": size,
                    "algorithm": algorithm,
                    "path": file_path,
                }
            except Exception as e:
                logger.warning(f"Failed to process {file_path}: {e}")

        return results


# ===========================
# Global Instance
# ===========================

_integrity_checker = None


@export
def get_integrity_checker() -> IntegrityChecker:
    """获取全局IntegrityChecker单例"""
    global _integrity_checker
    if _integrity_checker is None:
        _integrity_checker = IntegrityChecker()
    return _integrity_checker


# ===========================
# Convenience Functions
# ===========================


@export
def compute_file_checksum(file_path: str, algorithm: str = "xxhash64") -> str:
    """
    便捷函数:计算文件checksum

    Args:
        file_path: 文件路径
        algorithm: 哈希算法

    Returns:
        Hex编码的checksum字符串
    """
    checker = get_integrity_checker()
    return checker.compute_checksum(file_path, algorithm)


@export
def verify_file_checksum(
    file_path: str, expected_checksum: str, algorithm: str = "xxhash64"
) -> bool:
    """
    便捷函数:验证文件checksum

    Args:
        file_path: 文件路径
        expected_checksum: 期望的checksum值
        algorithm: 哈希算法

    Returns:
        True if valid, False otherwise
    """
    checker = get_integrity_checker()
    return checker.verify_checksum(file_path, expected_checksum, algorithm)
