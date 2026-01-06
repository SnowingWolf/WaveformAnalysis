"""
Storage 模块 - 负责数据的持久化与加载。

实现了基于 NumPy Memmap 的多通道数组存储和基于 Parquet 的 DataFrame 存储。
支持原子写入、元数据管理以及存储版本的校验，确保数据的完整性与一致性。
"""

import fcntl
import json
import os
import time
import warnings
from typing import Any, Dict, Iterator, List, Optional, Tuple

import numpy as np
import pandas as pd


class BufferedStreamWriter:
    """
    Buffered writer for efficient stream writing to reduce system calls.
    """
    def __init__(self, file_handle, buffer_size=4 * 1024 * 1024):  # 4MB default buffer
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
        self.buffer[self.buffer_pos:self.buffer_pos + data_len] = data
        self.buffer_pos += data_len

    def flush(self):
        """Flush buffer to file."""
        if self.buffer_pos > 0:
            self.file.write(memoryview(self.buffer)[:self.buffer_pos])
            self.buffer_pos = 0


class MemmapStorage:
    """
    Handles persistence of structured numpy data using binary files and memmap.
    """

    STORAGE_VERSION = "1.0.0"

    def __init__(self, base_dir: str, profiler: Optional[Any] = None):
        self.base_dir = base_dir
        self.profiler = profiler
        if not os.path.exists(base_dir):
            os.makedirs(base_dir, exist_ok=True)

    def _timeit(self, key: str):
        if self.profiler:
            return self.profiler.timeit(key)
        from contextlib import nullcontext

        return nullcontext()

    def _get_paths(self, key: str) -> Tuple[str, str, str]:
        bin_path = os.path.join(self.base_dir, f"{key}.bin")
        meta_path = os.path.join(self.base_dir, f"{key}.json")
        lock_path = os.path.join(self.base_dir, f"{key}.lock")
        return bin_path, meta_path, lock_path

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

                    except (BlockingIOError, OSError, IOError):
                        # Lock is held by another process
                        os.close(fd)

                        # Exponential backoff: start at 1ms, max 100ms
                        sleep_time = min(0.001 * (2 ** attempt), 0.1)
                        time.sleep(sleep_time)
                        attempt += 1

                except Exception as e:
                    warnings.warn(
                        f"Unexpected error acquiring lock {lock_path}: {e}",
                        UserWarning
                    )
                    time.sleep(0.1)

            return None

    def _release_lock(self, fd: Optional[int], lock_path: str):
        """Release the lock and close file descriptor."""
        if fd is not None:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            except Exception:
                pass  # Best effort unlock

            try:
                os.close(fd)
            except Exception:
                pass  # Best effort close

        # Clean up lock file (best effort, ignore errors)
        try:
            if os.path.exists(lock_path):
                os.remove(lock_path)
        except Exception:
            pass

    def save_metadata(self, key: str, metadata: Dict[str, Any]):
        """Atomically save metadata for a key."""
        _, meta_path, _ = self._get_paths(key)
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
    ):
        """Finalize a save operation by renaming temp files and writing metadata."""
        bin_path, meta_path, _ = self._get_paths(key)
        tmp_bin_path = bin_path + ".tmp"

        if total_count > 0:
            # Atomic rename for binary file
            if os.path.exists(bin_path):
                os.remove(bin_path)
            os.rename(tmp_bin_path, bin_path)

            # Prepare metadata
            _dtype = np.dtype(dtype)
            metadata = {
                "count": total_count,
                "dtype": _dtype.str,
                "itemsize": _dtype.itemsize,
                "storage_version": self.STORAGE_VERSION,
                "timestamp": time.time(),
                "shape": shape if shape else (total_count,),
            }
            if _dtype.names is not None:
                metadata["dtype_descr"] = _dtype.descr

            if extra_metadata:
                metadata.update(extra_metadata)

            self.save_metadata(key, metadata)
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
    ) -> int:
        """
        Consumes a stream of numpy arrays and saves them to a binary file.
        Returns the total number of items saved.
        """
        with self._timeit("storage.save"):
            bin_path, _, lock_path = self._get_paths(key)
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
                            raise RuntimeError(f"Error writing chunk to {tmp_bin_path}: {str(e)}") from e

                    # Flush remaining data
                    writer.flush()

                self.finalize_save(key, total_count, dtype, extra_metadata, shape=shape)
                return total_count
            except Exception as e:
                # Cleanup on failure
                if os.path.exists(tmp_bin_path):
                    try:
                        os.remove(tmp_bin_path)
                    except Exception:
                        pass
                raise e
            finally:
                self._release_lock(lock_fd, lock_path)
                # Remove temp file if it still exists (shouldn't happen on success)
                if os.path.exists(tmp_bin_path):
                    try:
                        os.remove(tmp_bin_path)
                    except Exception:
                        pass

    def save_memmap(self, key: str, data: np.ndarray, extra_metadata: Optional[Dict[str, Any]] = None):
        """Save a single numpy array to storage."""
        if data is None or data.size == 0:
            return
        self.save_stream(key, iter([data]), data.dtype, extra_metadata, shape=data.shape)

    def get_metadata(self, key: str) -> Optional[Dict[str, Any]]:
        """Retrieve metadata for a given key."""
        with self._timeit("storage.get_metadata"):
            _, meta_path, _ = self._get_paths(key)
            if not os.path.exists(meta_path):
                return None
            try:
                with open(meta_path, "r") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                warnings.warn(f"Failed to read metadata at {meta_path}: {str(e)}")
                return None

    def load_memmap(self, key: str) -> Optional[np.ndarray]:
        """
        Loads a binary file as a read-only memmap with integrity checks.
        """
        with self._timeit("storage.load"):
            bin_path, meta_path, _ = self._get_paths(key)
            if not os.path.exists(bin_path) or not os.path.exists(meta_path):
                return None

            meta = self.get_metadata(key)
            if meta is None:
                return None

            # Integrity Check: Version
            if meta.get("storage_version") != self.STORAGE_VERSION:
                warnings.warn(
                    f"Storage version mismatch for {key}. "
                    f"Expected {self.STORAGE_VERSION}, got {meta.get('storage_version')}. Recomputing.",
                    UserWarning,
                )
                return None

            count = meta["count"]
            itemsize = meta["itemsize"]
            shape = meta.get("shape", (count,))

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

            return np.memmap(bin_path, dtype=dtype, mode="r", shape=tuple(shape))

    def exists(self, key: str) -> bool:
        """
        检查给定 key 的数据是否存在，支持单文件（二进制/memmap, parquet）和多通道格式。
        """
        # 1. 首先检查单文件是否存在
        if self._check_single_exists(key):
            return True

        # 2. 检查多通道是否存在（回退到 _ch0）
        if not key.endswith("_ch0") and self._check_single_exists(f"{key}_ch0"):
            return True

        return False

    def _check_single_exists(self, key: str) -> bool:
        """内部辅助方法：检查单个 key 的数据完整性。"""
        bin_path, meta_path, _ = self._get_paths(key)
        parquet_path = os.path.join(self.base_dir, f"{key}.parquet")

        # 所有格式都必须有元数据文件
        if not os.path.exists(meta_path):
            return False

        try:
            meta = self.get_metadata(key)
            if meta is None:
                return False

            # 情况 1: DataFrame (Parquet)
            if meta.get("type") == "dataframe":
                return os.path.exists(parquet_path)

            # 情况 2: 二进制/Memmap (.bin)
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

            # 存储版本检查
            if meta.get("storage_version") != self.STORAGE_VERSION:
                return False

            return True
        except Exception:
            return False

    def delete(self, key: str):
        """Delete data and metadata for a key."""
        bin_path, meta_path, lock_path = self._get_paths(key)
        for p in [bin_path, meta_path, lock_path]:
            if os.path.exists(p):
                os.remove(p)

    def list_keys(self) -> List[str]:
        """List all keys in the storage."""
        keys = []
        for f in os.listdir(self.base_dir):
            if f.endswith(".json"):
                keys.append(f[:-5])
        return keys

    def get_size(self, key: str) -> int:
        """Get the number of records for a key."""
        meta = self.get_metadata(key)
        if meta:
            return meta.get("count", 0)
        return 0

    def save_dataframe(self, key: str, df: pd.DataFrame):
        """Save a pandas DataFrame as Parquet."""
        path = os.path.join(self.base_dir, f"{key}.parquet")
        df.to_parquet(path)

    def load_dataframe(self, key: str) -> Optional[pd.DataFrame]:
        """Load a pandas DataFrame from Parquet."""
        path = os.path.join(self.base_dir, f"{key}.parquet")
        if os.path.exists(path):
            return pd.read_parquet(path)
        return None
