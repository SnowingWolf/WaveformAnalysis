"""
Storage 模块 - 负责数据的持久化与加载。

实现了基于 NumPy Memmap 的多通道数组存储和基于 Parquet 的 DataFrame 存储。
支持原子写入、元数据管理以及存储版本的校验，确保数据的完整性与一致性。

存储架构：
- 分层结构：work_dir/{run_id}/_cache/{key}.bin
- 支持数据压缩（blosc2, lz4, zstd, gzip）
- 压缩数据不支持 memmap，但节省存储空间
"""

import fcntl
import json
import logging
import os
import time
from typing import Any, Dict, Iterator, List, Optional, Tuple, Union
import warnings

import numpy as np
import pandas as pd

# 设置日志记录器
logger = logging.getLogger(__name__)


class BufferedStreamWriter:
    """
    Buffered writer for efficient stream writing to reduce system calls.
    """

    def __init__(self, file_handle, buffer_size=4 * 1024 * 1024):  # 4MB default buffer
        """
        初始化缓冲流写入器

        Args:
            file_handle: 文件句柄（已打开的文件对象）
            buffer_size: 缓冲区大小（字节，默认 4MB）

        Note:
            通过缓冲减少系统调用次数，提升写入性能。
        """
        self.file = file_handle
        self.buffer = bytearray(buffer_size)
        self.buffer_pos = 0
        self.buffer_size = buffer_size

    def write_array(self, arr: np.ndarray):
        """Write numpy array to buffer, flushing when necessary."""
        data = arr.tobytes()
        data_len = len(data)

        # If data larger than buffer, write directly
        if data_len > self.buffer_size:
            self.flush()
            self.file.write(data)
            return

        # If data doesn't fit in remaining buffer space, flush first
        if data_len > self.buffer_size - self.buffer_pos:
            self.flush()

        # Copy data to buffer
        self.buffer[self.buffer_pos : self.buffer_pos + data_len] = data
        self.buffer_pos += data_len

    def flush(self):
        """Flush buffer to file."""
        if self.buffer_pos > 0:
            self.file.write(memoryview(self.buffer)[: self.buffer_pos])
            self.buffer_pos = 0


class MemmapStorage:
    """
    Handles persistence of structured numpy data using binary files and memmap.
    """

    STORAGE_VERSION = "1.0.1"  # Bumped to support compression

    def __init__(
        self,
        work_dir: str,
        profiler: Optional[Any] = None,
        compression: Optional[Union[str, Any]] = None,
        compression_kwargs: Optional[Dict[str, Any]] = None,
        enable_checksum: bool = False,
        checksum_algorithm: str = "xxhash64",
        verify_on_load: bool = False,
        data_subdir: str = "_cache",
        side_effects_subdir: str = "side_effects",
    ):
        """
        Initialize MemmapStorage with hierarchical storage structure.

        Args:
            work_dir: Work directory for hierarchical storage.
                     Files organized as: work_dir/{run_id}/_cache/{key}.bin
            profiler: Optional profiler for performance tracking
            compression: Compression backend name ('blosc2', 'lz4', 'zstd', 'gzip') or instance.
                        None means no compression (default, uses memmap).
            compression_kwargs: Additional kwargs passed to compression backend
            enable_checksum: Enable checksum computation for data integrity
            checksum_algorithm: Checksum algorithm ('xxhash64', 'sha256', 'md5')
            verify_on_load: Verify checksum when loading data (may impact performance)
            data_subdir: Subdirectory name for data files (default: "_cache")
            side_effects_subdir: Subdirectory name for side effect outputs (default: "side_effects")

        Storage Structure:
            work_dir/
            ├── {run_id}/
            │   ├── _cache/          # Data files
            │   │   ├── {key}.bin
            │   │   ├── {key}.json
            │   │   └── ...
            │   └── side_effects/    # Side effect outputs
            │       └── ...
            └── ...
        """
        self.work_dir = work_dir
        self.profiler = profiler
        self.compression = None
        self.compression_backend = None
        self.enable_checksum = enable_checksum
        self.checksum_algorithm = checksum_algorithm
        self.verify_on_load = verify_on_load
        self.data_subdir = data_subdir
        self.side_effects_subdir = side_effects_subdir

        # 确保工作目录存在
        if not os.path.exists(work_dir):
            os.makedirs(work_dir, exist_ok=True)

        # Setup compression if specified
        if compression is not None:
            self._setup_compression(compression, compression_kwargs or {})

    def _setup_compression(self, compression: Union[str, Any], kwargs: Dict[str, Any]):
        """Setup compression backend"""
        try:
            from waveform_analysis.core.storage.compression import get_compression_manager

            manager = get_compression_manager()

            if isinstance(compression, str):
                # Get backend by name
                self.compression_backend = manager.get_backend(compression, **kwargs)
                self.compression = compression
            else:
                # Use provided backend instance
                self.compression_backend = compression
                self.compression = compression.name

            if not self.compression_backend.is_available():
                warnings.warn(
                    f"Compression backend '{self.compression}' not available, "
                    f"falling back to no compression"
                )
                self.compression = None
                self.compression_backend = None
        except ImportError:
            warnings.warn("Compression module not available, disabling compression")
            self.compression = None
            self.compression_backend = None

    def _timeit(self, key: str):
        if self.profiler:
            return self.profiler.timeit(key)
        from contextlib import nullcontext

        return nullcontext()

    def _get_paths(self, key: str, run_id: Optional[str] = None) -> Tuple[str, str, str]:
        """
        生成存储路径（分层结构）。

        Args:
            key: 缓存键 (格式: "run_id-data_name-lineage_hash" 或 "data_name-hash")
            run_id: 显式传入的 run_id（推荐）。如果为 None 则从 key 解析。

        Returns:
            (bin_path, meta_path, lock_path)

        Storage Path:
            work_dir/{run_id}/_cache/{key}.bin
        """
        # 从 key 提取 run_id（如果未显式传入）
        if run_id is None:
            # key 格式: "run_001-data_name-hash" -> run_id = "run_001"
            parts = key.split("-")
            if len(parts) >= 1:
                run_id = parts[0]
            else:
                run_id = "default"

        root = os.path.join(self.work_dir, run_id, self.data_subdir)
        os.makedirs(root, exist_ok=True)

        bin_path = os.path.join(root, f"{key}.bin")
        meta_path = os.path.join(root, f"{key}.json")
        lock_path = os.path.join(root, f"{key}.lock")
        return bin_path, meta_path, lock_path

    def get_run_data_dir(self, run_id: str) -> str:
        """
        获取指定 run 的数据目录路径。

        Args:
            run_id: 运行标识符

        Returns:
            run 的数据目录绝对路径 (work_dir/{run_id}/_cache/)
        """
        return os.path.join(self.work_dir, run_id, self.data_subdir)

    def get_run_side_effects_dir(self, run_id: str) -> str:
        """
        获取指定 run 的副作用输出目录路径。

        Args:
            run_id: 运行标识符

        Returns:
            run 的副作用目录绝对路径 (work_dir/{run_id}/side_effects/)
        """
        return os.path.join(self.work_dir, run_id, self.side_effects_subdir)

    def _acquire_lock(self, lock_path: str, timeout: int = 10) -> Optional[int]:
        """
        Acquire an atomic file-based lock using fcntl (POSIX/Linux).
        Returns file descriptor on success, None on timeout.
        """
        with self._timeit("storage.acquire_lock"):
            start_time = time.time()
            attempt = 0

            while time.time() - start_time < timeout:
                try:
                    # Open or create the lock file
                    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o644)

                    try:
                        # Use fcntl for atomic locking (non-blocking)
                        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        # Successfully acquired lock
                        return fd

                    except (BlockingIOError, OSError):
                        # Lock is held by another process
                        os.close(fd)

                        # Exponential backoff: start at 1ms, max 100ms
                        sleep_time = min(0.001 * (2**attempt), 0.1)
                        time.sleep(sleep_time)
                        attempt += 1

                except (PermissionError, FileNotFoundError) as e:
                    # 文件权限问题或目录不存在
                    logger.error(
                        f"Permission or file access error acquiring lock {lock_path}: {e}",
                        exc_info=True,
                    )
                    time.sleep(0.1)
                except Exception as e:
                    # 其他未预期的错误
                    logger.error(f"Unexpected error acquiring lock {lock_path}: {e}", exc_info=True)
                    time.sleep(0.1)

            return None

    def _release_lock(self, fd: Optional[int], lock_path: str):
        """释放锁并关闭文件描述符"""
        if fd is not None:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            except OSError as e:
                # 锁可能已经被释放或文件已关闭
                logger.warning(f"Failed to unlock {lock_path}: {e}")
            except Exception as e:
                # 其他未预期的错误
                logger.error(f"Unexpected error unlocking {lock_path}: {e}", exc_info=True)

            try:
                os.close(fd)
            except OSError as e:
                # 文件描述符可能已经关闭
                logger.warning(f"Failed to close file descriptor for {lock_path}: {e}")
            except Exception as e:
                logger.error(f"Unexpected error closing fd for {lock_path}: {e}", exc_info=True)

        # 清理锁文件（尽力而为）
        try:
            if os.path.exists(lock_path):
                os.remove(lock_path)
        except (PermissionError, OSError) as e:
            # 文件可能已被删除或权限不足
            logger.debug(f"Could not remove lock file {lock_path}: {e}")
        except Exception as e:
            logger.warning(f"Unexpected error removing lock file {lock_path}: {e}")

    def save_metadata(self, key: str, metadata: Dict[str, Any], run_id: Optional[str] = None):
        """Atomically save metadata for a key."""
        _, meta_path, _ = self._get_paths(key, run_id)
        tmp_meta_path = meta_path + ".tmp"
        with open(tmp_meta_path, "w") as f:
            json.dump(metadata, f, default=str)
        if os.path.exists(meta_path):
            os.remove(meta_path)
        os.rename(tmp_meta_path, meta_path)

    def finalize_save(
        self,
        key: str,
        total_count: int,
        dtype: np.dtype,
        extra_metadata: Optional[Dict[str, Any]] = None,
        shape: Optional[Tuple[int, ...]] = None,
        run_id: Optional[str] = None,
    ):
        """Finalize a save operation by renaming temp files and writing metadata."""
        bin_path, meta_path, _ = self._get_paths(key, run_id)
        tmp_bin_path = bin_path + ".tmp"

        if total_count > 0:
            # Atomic rename for binary file
            if os.path.exists(bin_path):
                os.remove(bin_path)
            os.rename(tmp_bin_path, bin_path)

            # Apply compression if enabled
            compressed = False
            compression_ratio = 1.0
            compressed_size = 0  # 初始化以避免未绑定警告
            original_size = os.path.getsize(bin_path)
            final_file_path = bin_path  # Track which file to compute checksum on

            if self.compression_backend is not None:
                try:
                    with self._timeit("storage.compress"):
                        # Read uncompressed data
                        with open(bin_path, "rb") as f:
                            data = f.read()

                        # Compress
                        compressed_data = self.compression_backend.compress(data)
                        compressed_size = len(compressed_data)

                        # Write compressed file (with different extension)
                        compressed_path = bin_path + self.compression_backend.extension
                        with open(compressed_path, "wb") as f:
                            f.write(compressed_data)

                        # Remove original uncompressed file
                        os.remove(bin_path)

                        compressed = True
                        compression_ratio = original_size / compressed_size
                        final_file_path = compressed_path

                except Exception as e:
                    warnings.warn(f"Compression failed for {key}: {e}, storing uncompressed")
                    # Keep uncompressed file
                    compressed = False
                    # Clean up any partial compressed file
                    compressed_path = bin_path + self.compression_backend.extension
                    if os.path.exists(compressed_path):
                        try:
                            os.remove(compressed_path)
                        except (PermissionError, OSError) as cleanup_err:
                            logger.warning(
                                f"Failed to remove partial compressed file {compressed_path}: {cleanup_err}"
                            )
                        except Exception as cleanup_err:
                            logger.error(
                                f"Unexpected error removing compressed file {compressed_path}: {cleanup_err}",
                                exc_info=True,
                            )

            # Compute checksum if enabled
            checksum = None
            if self.enable_checksum and os.path.exists(final_file_path):
                try:
                    from waveform_analysis.core.storage.integrity import get_integrity_checker

                    checker = get_integrity_checker()
                    checksum = checker.compute_checksum(final_file_path, self.checksum_algorithm)
                except Exception as e:
                    warnings.warn(f"Failed to compute checksum for {key}: {e}")
                    checksum = None

            # Prepare metadata
            _dtype = np.dtype(dtype)
            metadata = {
                "count": total_count,
                "dtype": _dtype.str,
                "itemsize": _dtype.itemsize,
                "storage_version": self.STORAGE_VERSION,
                "timestamp": time.time(),
                "shape": shape if shape else (total_count,),
                "compressed": compressed,
            }
            if _dtype.names is not None:
                metadata["dtype_descr"] = _dtype.descr

            if compressed:
                metadata["compression"] = self.compression
                metadata["compression_ratio"] = compression_ratio
                metadata["original_size"] = original_size
                metadata["compressed_size"] = compressed_size

            if checksum is not None:
                metadata["checksum"] = checksum
                metadata["checksum_algorithm"] = self.checksum_algorithm

            if extra_metadata:
                metadata.update(extra_metadata)

            self.save_metadata(key, metadata, run_id)
        else:
            if os.path.exists(tmp_bin_path):
                os.remove(tmp_bin_path)

    def save_stream(
        self,
        key: str,
        stream: Iterator[np.ndarray],
        dtype: np.dtype,
        extra_metadata: Optional[Dict[str, Any]] = None,
        shape: Optional[Tuple[int, ...]] = None,
        run_id: Optional[str] = None,
    ) -> int:
        """
        Consumes a stream of numpy arrays and saves them to a binary file.
        Returns the total number of items saved.
        """
        with self._timeit("storage.save"):
            bin_path, _, lock_path = self._get_paths(key, run_id)
            tmp_bin_path = bin_path + ".tmp"

            # Acquire lock
            lock_fd = self._acquire_lock(lock_path)
            if lock_fd is None:
                raise RuntimeError(f"Could not acquire lock for {key} after timeout.")

            total_count = 0
            try:
                with open(tmp_bin_path, "wb") as f:
                    writer = BufferedStreamWriter(f)
                    for chunk in stream:
                        if len(chunk) == 0:
                            continue
                        try:
                            arr = np.asarray(chunk, dtype=dtype)
                            writer.write_array(arr)
                            total_count += len(arr)
                        except Exception as e:
                            raise RuntimeError(
                                f"Error writing chunk to {tmp_bin_path}: {str(e)}"
                            ) from e

                    # Flush remaining data
                    writer.flush()

                self.finalize_save(
                    key, total_count, dtype, extra_metadata, shape=shape, run_id=run_id
                )
                return total_count
            except Exception as e:
                # Cleanup on failure
                if os.path.exists(tmp_bin_path):
                    try:
                        os.remove(tmp_bin_path)
                    except (PermissionError, OSError) as cleanup_err:
                        logger.warning(
                            f"Failed to remove temporary file {tmp_bin_path} after error: {cleanup_err}"
                        )
                    except Exception as cleanup_err:
                        logger.error(
                            f"Unexpected error removing temp file {tmp_bin_path}: {cleanup_err}",
                            exc_info=True,
                        )
                raise e
            finally:
                self._release_lock(lock_fd, lock_path)
                # Remove temp file if it still exists (shouldn't happen on success)
                if os.path.exists(tmp_bin_path):
                    try:
                        os.remove(tmp_bin_path)
                    except (PermissionError, OSError) as cleanup_err:
                        logger.warning(
                            f"Failed to remove lingering temp file {tmp_bin_path}: {cleanup_err}"
                        )
                    except Exception as cleanup_err:
                        logger.error(
                            f"Unexpected error removing temp file {tmp_bin_path}: {cleanup_err}",
                            exc_info=True,
                        )

    def save_memmap(
        self,
        key: str,
        data: np.ndarray,
        extra_metadata: Optional[Dict[str, Any]] = None,
        run_id: Optional[str] = None,
    ):
        """Save a single numpy array to storage."""
        if data is None or data.size == 0:
            return
        self.save_stream(
            key, iter([data]), data.dtype, extra_metadata, shape=data.shape, run_id=run_id
        )

    def get_metadata(self, key: str, run_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Retrieve metadata for a given key."""
        with self._timeit("storage.get_metadata"):
            _, meta_path, _ = self._get_paths(key, run_id)
            if not os.path.exists(meta_path):
                return None
            try:
                with open(meta_path) as f:
                    return json.load(f)
            except (OSError, json.JSONDecodeError) as e:
                warnings.warn(f"Failed to read metadata at {meta_path}: {str(e)}")
                return None

    def load_memmap(self, key: str, run_id: Optional[str] = None) -> Optional[np.ndarray]:
        """
        Loads a binary file as a read-only memmap with integrity checks.

        If data is compressed, it will be fully loaded into memory (not memmap).
        """
        with self._timeit("storage.load"):
            bin_path, meta_path, _ = self._get_paths(key, run_id)
            if not os.path.exists(meta_path):
                return None

            meta = self.get_metadata(key, run_id)
            if meta is None:
                return None

            # Integrity Check: Version (allow both 1.0.0 and 1.0.1)
            storage_version = meta.get("storage_version")
            if storage_version not in [self.STORAGE_VERSION, "1.0.0"]:
                warnings.warn(
                    f"Storage version mismatch for {key}. "
                    f"Expected {self.STORAGE_VERSION}, got {storage_version}. Recomputing.",
                    UserWarning,
                )
                return None

            count = meta["count"]
            itemsize = meta["itemsize"]
            shape = meta.get("shape", (count,))
            is_compressed = meta.get("compressed", False)

            # Reconstruct dtype
            try:
                if "dtype_descr" in meta:
                    descr = []
                    for item in meta["dtype_descr"]:
                        if isinstance(item, list):
                            descr.append(tuple(item))
                        else:
                            descr.append(item)
                    dtype = np.dtype(descr)
                else:
                    dtype = np.dtype(meta["dtype"])
            except Exception as e:
                warnings.warn(f"Failed to reconstruct dtype for {key}: {str(e)}")
                return None

            # Handle compressed data
            if is_compressed:
                return self._load_compressed(key, meta, dtype, shape, run_id)

            # Handle uncompressed data (original memmap logic)
            if not os.path.exists(bin_path):
                return None

            # Integrity Check: File Size
            expected_size = np.prod(shape) * itemsize
            actual_size = os.path.getsize(bin_path)
            if actual_size != expected_size:
                warnings.warn(
                    f"File size mismatch for {bin_path}. "
                    f"Expected {expected_size} bytes, got {actual_size} bytes. Cache corrupted.",
                    UserWarning,
                )
                return None

            # Integrity Check: Checksum (if enabled and available in metadata)
            if self.verify_on_load and "checksum" in meta:
                expected_checksum = meta["checksum"]
                algorithm = meta.get("checksum_algorithm", self.checksum_algorithm)

                try:
                    from waveform_analysis.core.storage.integrity import get_integrity_checker

                    checker = get_integrity_checker()

                    if not checker.verify_checksum(bin_path, expected_checksum, algorithm):
                        warnings.warn(
                            f"Checksum verification failed for {bin_path}. Data may be corrupted.",
                            UserWarning,
                        )
                        return None
                except Exception as e:
                    warnings.warn(f"Failed to verify checksum for {key}: {e}")
                    # Continue loading even if verification fails

            return np.memmap(bin_path, dtype=dtype, mode="r", shape=tuple(shape))

    def _load_compressed(
        self,
        key: str,
        meta: Dict[str, Any],
        dtype: np.dtype,
        shape: Tuple[int, ...],
        run_id: Optional[str] = None,
    ) -> Optional[np.ndarray]:
        """Load compressed data (returns in-memory array, not memmap)"""
        bin_path, _, _ = self._get_paths(key, run_id)

        # Get compression algorithm
        compression_name = meta.get("compression")
        if not compression_name:
            warnings.warn(f"Compressed flag set but no compression algorithm specified for {key}")
            return None

        # Setup compression backend if not already configured
        if self.compression_backend is None or self.compression != compression_name:
            try:
                from waveform_analysis.core.storage.compression import get_compression_manager

                manager = get_compression_manager()
                backend = manager.get_backend(compression_name, fallback=False)
            except Exception as e:
                warnings.warn(f"Failed to get compression backend '{compression_name}': {e}")
                return None
        else:
            backend = self.compression_backend

        # Find compressed file (might have extension)
        compressed_path = bin_path + backend.extension
        if not os.path.exists(compressed_path):
            warnings.warn(f"Compressed file not found: {compressed_path}")
            return None

        # Verify checksum if enabled
        if self.verify_on_load and "checksum" in meta:
            expected_checksum = meta["checksum"]
            algorithm = meta.get("checksum_algorithm", self.checksum_algorithm)

            try:
                from waveform_analysis.core.storage.integrity import get_integrity_checker

                checker = get_integrity_checker()

                if not checker.verify_checksum(compressed_path, expected_checksum, algorithm):
                    warnings.warn(
                        f"Checksum verification failed for {compressed_path}. Data may be corrupted.",
                        UserWarning,
                    )
                    return None
            except Exception as e:
                warnings.warn(f"Failed to verify checksum for {key}: {e}")

        try:
            with self._timeit("storage.decompress"):
                # Read compressed data
                with open(compressed_path, "rb") as f:
                    compressed_data = f.read()

                # Decompress
                decompressed_data = backend.decompress(compressed_data)

                # Convert to numpy array
                arr = np.frombuffer(decompressed_data, dtype=dtype)
                arr = arr.reshape(shape)

                return arr

        except Exception as e:
            warnings.warn(f"Failed to decompress {key}: {e}")
            return None

    def exists(self, key: str, run_id: Optional[str] = None) -> bool:
        """
        检查给定 key 的数据是否存在，支持单文件（二进制/memmap, parquet）和多通道格式。
        """
        # 1. 首先检查单文件是否存在
        if self._check_single_exists(key, run_id):
            return True

        # 2. 检查多通道是否存在（先回退到 _ch0）
        if not key.endswith("_ch0") and self._check_single_exists(f"{key}_ch0", run_id):
            return True

        # 3. 检查任意通道号（key_ch*）
        if self._list_channel_keys(key, run_id):
            return True

        return False

    def _list_channel_keys(self, key: str, run_id: Optional[str] = None) -> List[str]:
        """列出指定 key 的所有多通道缓存 key（key_ch*）。"""
        if run_id is None:
            parts = key.split("-")
            if len(parts) >= 1:
                run_id = parts[0]
            else:
                run_id = "default"

        data_dir = os.path.join(self.work_dir, run_id, self.data_subdir)
        if not os.path.exists(data_dir):
            return []

        prefix = f"{key}_ch"
        keys = []
        for f in os.listdir(data_dir):
            if f.endswith(".json") and f.startswith(prefix):
                keys.append(f[:-5])
        return keys

    def _check_single_exists(self, key: str, run_id: Optional[str] = None) -> bool:
        """内部辅助方法：检查单个 key 的数据完整性。"""
        bin_path, meta_path, _ = self._get_paths(key, run_id)

        # 获取 parquet 路径
        effective_run_id = run_id
        if effective_run_id is None:
            parts = key.split("-")
            if len(parts) >= 1:
                effective_run_id = parts[0]
            else:
                effective_run_id = "default"

        parquet_root = os.path.join(self.work_dir, effective_run_id, self.data_subdir)
        parquet_path = os.path.join(parquet_root, f"{key}.parquet")

        # 所有格式都必须有元数据文件
        if not os.path.exists(meta_path):
            return False

        try:
            meta = self.get_metadata(key, run_id)
            if meta is None:
                return False

            # 情况 1: DataFrame (Parquet)
            if meta.get("type") == "dataframe":
                return os.path.exists(parquet_path)

            # 情况 2: 压缩的二进制数据
            if meta.get("compressed", False):
                compression_name = meta.get("compression")
                if compression_name:
                    # Get the expected extension
                    try:
                        from waveform_analysis.core.storage.compression import (
                            get_compression_manager,
                        )

                        manager = get_compression_manager()
                        backend = manager.get_backend(compression_name, fallback=False)
                        compressed_path = bin_path + backend.extension
                        return os.path.exists(compressed_path)
                    except ImportError as e:
                        logger.debug(f"Compression module not available: {e}")
                        return False
                    except Exception as e:
                        logger.warning(
                            f"Failed to check compressed file for {key} with {compression_name}: {e}"
                        )
                        return False
                return False

            # 情况 3: 未压缩的二进制/Memmap (.bin)
            if not os.path.exists(bin_path):
                return False

            # 二进制文件的完整性检查
            count = meta.get("count")
            itemsize = meta.get("itemsize")
            shape = meta.get("shape", (count,))
            if count is not None and itemsize is not None:
                expected_size = int(np.prod(shape)) * int(itemsize)
                actual_size = os.path.getsize(bin_path)
                if actual_size != expected_size:
                    return False

            # 存储版本检查 (allow both versions)
            storage_version = meta.get("storage_version")
            if storage_version not in [self.STORAGE_VERSION, "1.0.0"]:
                return False

            return True
        except (OSError, json.JSONDecodeError) as e:
            # JSON 解析错误或 I/O 错误
            logger.debug(f"Failed to check existence of {key}: JSON or I/O error: {e}")
            return False
        except Exception as e:
            # 其他未预期的错误
            logger.warning(f"Unexpected error checking existence of {key}: {e}", exc_info=False)
            return False

    def delete(self, key: str, run_id: Optional[str] = None):
        """Delete data and metadata for a key."""
        bin_path, meta_path, lock_path = self._get_paths(key, run_id)
        for p in [bin_path, meta_path, lock_path]:
            if os.path.exists(p):
                os.remove(p)

    def list_keys(self, run_id: Optional[str] = None) -> List[str]:
        """
        List all keys in the storage.

        Args:
            run_id: Run ID to list keys for. If None, returns empty list (must specify run).

        Returns:
            List of cache keys for the specified run
        """
        keys = []

        if run_id is None:
            # 分层模式下，必须指定 run_id
            return keys

        data_dir = os.path.join(self.work_dir, run_id, self.data_subdir)
        if not os.path.exists(data_dir):
            return keys

        for f in os.listdir(data_dir):
            if f.endswith(".json"):
                keys.append(f[:-5])

        return keys

    def list_runs(self) -> List[str]:
        """
        List all run IDs in the work_dir.

        Returns:
            List of run_id strings
        """
        runs = []
        if os.path.exists(self.work_dir):
            for d in os.listdir(self.work_dir):
                data_dir = os.path.join(self.work_dir, d, self.data_subdir)
                # 只有包含 data 子目录的才算有效 run
                if os.path.isdir(data_dir):
                    runs.append(d)
        return sorted(runs)

    def get_size(self, key: str, run_id: Optional[str] = None) -> int:
        """Get the number of records for a key."""
        meta = self.get_metadata(key, run_id)
        if meta:
            return meta.get("count", 0)
        return 0

    def save_dataframe(self, key: str, df: pd.DataFrame, run_id: Optional[str] = None):
        """Save a pandas DataFrame as Parquet."""
        # 提取 run_id（如果未显式传入）
        effective_run_id = run_id
        if effective_run_id is None:
            parts = key.split("-")
            if len(parts) >= 1:
                effective_run_id = parts[0]
            else:
                effective_run_id = "default"

        data_dir = os.path.join(self.work_dir, effective_run_id, self.data_subdir)
        os.makedirs(data_dir, exist_ok=True)
        path = os.path.join(data_dir, f"{key}.parquet")
        df.to_parquet(path)

    def load_dataframe(self, key: str, run_id: Optional[str] = None) -> Optional[pd.DataFrame]:
        """Load a pandas DataFrame from Parquet."""
        # 提取 run_id（如果未显式传入）
        effective_run_id = run_id
        if effective_run_id is None:
            parts = key.split("-")
            if len(parts) >= 1:
                effective_run_id = parts[0]
            else:
                effective_run_id = "default"

        data_dir = os.path.join(self.work_dir, effective_run_id, self.data_subdir)
        path = os.path.join(data_dir, f"{key}.parquet")

        if os.path.exists(path):
            return pd.read_parquet(path)
        return None

    def verify_integrity(
        self, run_id: Optional[str] = None, verbose: bool = True
    ) -> Dict[str, Any]:
        """
        验证存储数据的完整性

        检查:
        1. Metadata与实际文件的一致性
        2. 文件大小是否匹配
        3. Checksum验证(如果有)

        Args:
            run_id: 运行标识符。如果为 None，验证所有 runs。
            verbose: 是否打印详细信息

        Returns:
            {
                'total': int,
                'valid': int,
                'invalid': int,
                'errors': List[Dict]
            }
        """
        results = {"total": 0, "valid": 0, "invalid": 0, "errors": []}

        # 如果指定了 run_id，只验证该 run
        if run_id is not None:
            keys = self.list_keys(run_id)
        else:
            # 验证所有 runs
            keys = []
            for rid in self.list_runs():
                keys.extend(self.list_keys(rid))

        results["total"] = len(keys)

        for key in keys:
            try:
                # 从 key 提取 run_id
                key_run_id = run_id
                if key_run_id is None:
                    parts = key.split("-")
                    if len(parts) >= 1:
                        key_run_id = parts[0]
                    else:
                        key_run_id = "default"

                meta = self.get_metadata(key, key_run_id)
                if meta is None:
                    results["invalid"] += 1
                    results["errors"].append({"key": key, "error": "Missing metadata"})
                    continue

                # Check if it's a DataFrame
                if meta.get("type") == "dataframe":
                    data_dir = os.path.join(self.work_dir, key_run_id, self.data_subdir)
                    parquet_path = os.path.join(data_dir, f"{key}.parquet")
                    if not os.path.exists(parquet_path):
                        results["invalid"] += 1
                        results["errors"].append({"key": key, "error": "Parquet file missing"})
                    else:
                        results["valid"] += 1
                    continue

                # Check binary files
                bin_path, _, _ = self._get_paths(key, key_run_id)
                is_compressed = meta.get("compressed", False)

                if is_compressed:
                    # Get compression extension
                    compression_name = meta.get("compression")
                    if compression_name:
                        try:
                            from waveform_analysis.core.storage.compression import (
                                get_compression_manager,
                            )

                            manager = get_compression_manager()
                            backend = manager.get_backend(compression_name, fallback=False)
                            file_path = bin_path + backend.extension
                        except Exception:
                            results["invalid"] += 1
                            results["errors"].append(
                                {
                                    "key": key,
                                    "error": f"Cannot find compression backend: {compression_name}",
                                }
                            )
                            continue
                    else:
                        results["invalid"] += 1
                        results["errors"].append(
                            {
                                "key": key,
                                "error": "Compressed flag set but no compression algorithm",
                            }
                        )
                        continue
                else:
                    file_path = bin_path

                # Check file exists
                if not os.path.exists(file_path):
                    results["invalid"] += 1
                    results["errors"].append(
                        {"key": key, "error": f"Data file missing: {file_path}"}
                    )
                    continue

                # Check file size (for uncompressed)
                if not is_compressed:
                    count = meta.get("count")
                    itemsize = meta.get("itemsize")
                    shape = meta.get("shape", (count,))
                    if count is not None and itemsize is not None:
                        expected_size = int(np.prod(shape)) * int(itemsize)
                        actual_size = os.path.getsize(file_path)
                        if actual_size != expected_size:
                            results["invalid"] += 1
                            results["errors"].append(
                                {
                                    "key": key,
                                    "error": f"File size mismatch: expected {expected_size}, got {actual_size}",
                                }
                            )
                            continue

                # Verify checksum if available
                if "checksum" in meta:
                    expected_checksum = meta["checksum"]
                    algorithm = meta.get("checksum_algorithm", "xxhash64")

                    try:
                        from waveform_analysis.core.storage.integrity import get_integrity_checker

                        checker = get_integrity_checker()

                        if not checker.verify_checksum(file_path, expected_checksum, algorithm):
                            results["invalid"] += 1
                            results["errors"].append(
                                {"key": key, "error": "Checksum verification failed"}
                            )
                            continue
                    except Exception as e:
                        results["invalid"] += 1
                        results["errors"].append(
                            {"key": key, "error": f"Checksum verification error: {e}"}
                        )
                        continue

                # All checks passed
                results["valid"] += 1

            except Exception as e:
                results["invalid"] += 1
                results["errors"].append({"key": key, "error": f"Exception: {e}"})

        if verbose:
            print("\nIntegrity Check Results:")
            print(f"  Total files: {results['total']}")
            print(f"  Valid: {results['valid']}")
            print(f"  Invalid: {results['invalid']}")
            if results["errors"]:
                print("\nErrors:")
                for err in results["errors"]:
                    print(f"  - {err['key']}: {err['error']}")

        return results
