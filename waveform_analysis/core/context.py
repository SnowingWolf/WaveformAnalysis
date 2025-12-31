import json
import os
import time
import warnings
from typing import Any, Dict, Iterator, List, Optional, Tuple

import numpy as np


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

    def _acquire_lock(self, lock_path: str, timeout: int = 10, stale_timeout: int = 600) -> bool:
        """
        Acquire a file-based lock with stale lock detection.
        Writes PID and timestamp into the lock file.
        """
        with self._timeit("storage.acquire_lock"):
            start_time = time.time()
            pid = os.getpid()

            while time.time() - start_time < timeout:
                try:
                    # Use x mode to create exclusively
                    fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                    try:
                        lock_info = {"pid": pid, "timestamp": time.time()}
                        os.write(fd, json.dumps(lock_info).encode())
                    finally:
                        os.close(fd)
                    return True
                except FileExistsError:
                    # Check if the existing lock is stale
                    try:
                        with open(lock_path, "r") as f:
                            content = f.read()
                            if content:
                                lock_info = json.loads(content)
                                if time.time() - lock_info.get("timestamp", 0) > stale_timeout:
                                    # Lock is stale, try to remove it
                                    warnings.warn(
                                        f"Removing stale lock file at {lock_path} (PID {lock_info.get('pid')}, "
                                        f"age {time.time() - lock_info.get('timestamp'):.1f}s)",
                                        UserWarning,
                                    )
                                    os.remove(lock_path)
                                    continue  # Try to acquire again
                    except (json.JSONDecodeError, OSError, ValueError):
                        # If file is empty or corrupted, we might want to remove it if it's old
                        # But for now, just wait and retry
                        pass

                    time.sleep(0.1)
        return False

    def _release_lock(self, lock_path: str):
        """Release the lock file."""
        if os.path.exists(lock_path):
            try:
                # Optional: check if it's our lock before removing
                # For simplicity and robustness against crashes, we just remove it
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
        self, key: str, total_count: int, dtype: np.dtype, extra_metadata: Optional[Dict[str, Any]] = None
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
            }
            if hasattr(_dtype, "descr"):
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
    ) -> int:
        """
        Consumes a stream of numpy arrays and saves them to a binary file.
        Returns the total number of items saved.
        """
        with self._timeit("storage.save"):
            bin_path, _, lock_path = self._get_paths(key)
            tmp_bin_path = bin_path + ".tmp"

            if not self._acquire_lock(lock_path):
                raise RuntimeError(f"Could not acquire lock for {key} after timeout.")

            total_count = 0
            try:
                with open(tmp_bin_path, "wb") as f:
                    for chunk in stream:
                        if len(chunk) == 0:
                            continue
                        try:
                            arr = np.asarray(chunk, dtype=dtype)
                            f.write(arr.tobytes())
                            total_count += len(arr)
                        except Exception as e:
                            raise RuntimeError(f"Error writing chunk to {tmp_bin_path}: {str(e)}") from e

                self.finalize_save(key, total_count, dtype, extra_metadata)
                return total_count
            except Exception as e:
                # Cleanup on failure
                if os.path.exists(tmp_bin_path):
                    try:
                        os.remove(tmp_bin_path)
                    except:
                        pass
                raise e
            finally:
                self._release_lock(lock_path)
                if os.path.exists(tmp_bin_path):
                    try:
                        os.remove(tmp_bin_path)
                    except:
                        pass

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

            # Integrity Check: File Size
            expected_size = count * itemsize
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

            return np.memmap(bin_path, dtype=dtype, mode="r", shape=(count,))

    def exists(self, key: str) -> bool:
        bin_path, meta_path, _ = self._get_paths(key)
        return os.path.exists(bin_path) and os.path.exists(meta_path)
