from __future__ import annotations

import hashlib
import json
import os
from typing import Any
import warnings

import numpy as np


class ContextCacheDomain:
    """Disk-cache read helpers used by Context."""

    def __init__(self, context: Any) -> None:
        self.ctx = context

    def _dtype_from_meta(self, meta: dict[str, Any]) -> np.dtype | None:
        if not meta:
            return None
        if "dtype_descr" in meta:
            descr = []
            for item in meta["dtype_descr"]:
                if isinstance(item, list):
                    descr.append(tuple(item))
                else:
                    descr.append(item)
            try:
                return np.dtype(descr)
            except Exception:
                return None
        if "dtype" in meta:
            try:
                return np.dtype(meta["dtype"])
            except Exception:
                return None
        return None

    def key_for(self, run_id: str, data_name: str) -> str:
        """Build the cache identity key for a run/data pair."""
        cache_key = (run_id, data_name)
        if cache_key in self.ctx._key_cache:
            return self.ctx._key_cache[cache_key]

        if data_name in self.ctx._lineage_hash_cache:
            lineage_hash = self.ctx._lineage_hash_cache[data_name]
        else:
            lineage = self.ctx.get_lineage(data_name)
            lineage_json = json.dumps(lineage, sort_keys=True, default=str)
            lineage_hash = hashlib.sha1(lineage_json.encode()).hexdigest()[:8]
            self.ctx._lineage_hash_cache[data_name] = lineage_hash

        key = f"{run_id}-{data_name}-{lineage_hash}"
        self.ctx._key_cache[cache_key] = key
        return key

    def clear_cache_for(
        self,
        run_id: str,
        data_name: str | None = None,
        downstream: bool = False,
        clear_memory: bool = True,
        clear_disk: bool = True,
        verbose: bool = True,
    ) -> int:
        """Clear memory/disk cache entries for one or more data names."""
        count = 0
        memory_count = 0
        disk_count = 0

        if data_name is None:
            data_names = list(self.ctx._plugins.keys())
            if verbose:
                print(f"[清理缓存] 运行: {run_id}, 清理所有数据类型的缓存 ({len(data_names)} 个)")
        else:
            if downstream:
                downstream_names = self.ctx._collect_downstream_data_names(data_name, run_id=run_id)
                data_names = [data_name] + sorted(downstream_names)
            else:
                data_names = [data_name]
            if verbose:
                print(f"[清理缓存] 运行: {run_id}, 数据类型: {data_name}")

        for name in data_names:
            if clear_memory:
                key = (run_id, name)
                if key in self.ctx._results:
                    del self.ctx._results[key]
                    if key in self.ctx._results_lineage:
                        del self.ctx._results_lineage[key]
                    memory_count += 1
                    count += 1
                    if verbose:
                        print(f"  ✓ 已清理内存缓存: ({run_id}, {name})")
                    self.ctx.logger.debug("Cleared memory cache for (%s, %s)", run_id, name)
                elif verbose:
                    print(f"  - 内存缓存不存在: ({run_id}, {name})")

            if clear_disk:
                try:
                    cache_key = self.key_for(run_id, name)
                    deleted = self.delete_disk_cache(cache_key, run_id, data_name=name)
                    disk_count += deleted
                    count += deleted
                    if deleted > 0:
                        if verbose:
                            print(f"  ✓ 已清理磁盘缓存: {cache_key} ({deleted} 个文件)")
                        self.ctx.logger.debug("Cleared disk cache for (%s, %s)", run_id, name)
                    elif verbose:
                        print(f"  - 磁盘缓存不存在: {cache_key}")
                except Exception as e:
                    if verbose:
                        print(f"  ✗ 清理磁盘缓存失败: ({run_id}, {name}) - {e}")
                    self.ctx.logger.warning(
                        "Failed to clear disk cache for (%s, %s): %s", run_id, name, e
                    )

        if verbose:
            print(f"[清理完成] 总计: {count} 个缓存项 (内存: {memory_count}, 磁盘: {disk_count})")
            if count == 0:
                print("  ⚠️  没有找到需要清理的缓存")
            else:
                print("  ✓ 缓存清理成功")

        return count

    def load_from_disk_with_check(self, run_id: str, name: str, key: str) -> Any | None:
        """Load cached data from disk after validating storage layout and lineage."""
        storage = self.ctx._get_storage_for_data_name(name)
        channel_keys = self.ctx._list_channel_keys(storage, run_id, key)
        has_base = self.ctx._storage_exists(storage, key, run_id)
        if not has_base and not channel_keys:
            return None
        if channel_keys and self.ctx._expects_flat_channel_array(name):
            self.ctx.logger.warning(
                "Legacy multi-channel cache detected for '%s'. "
                "This data now uses a single array with a channel field. Recomputing.",
                name,
            )
            return None

        meta_key = channel_keys[0] if channel_keys else key
        meta = self.ctx._storage_call(storage, "get_metadata", meta_key, run_id)
        if meta is None and has_base and meta_key != key:
            meta = self.ctx._storage_call(storage, "get_metadata", key, run_id)
        if meta and "lineage" in meta:
            current_lineage = self.ctx.get_lineage(name)
            s1 = json.dumps(meta["lineage"], sort_keys=True, default=str)
            s2 = json.dumps(current_lineage, sort_keys=True, default=str)
            if s1 != s2:
                warnings.warn(f"Lineage mismatch for '{name}' in cache. Recomputing.", UserWarning)
                return None

        meta = meta or {}
        if meta.get("type") == "dataframe":
            data = self.ctx._storage_call(storage, "load_dataframe", key, run_id)
        elif channel_keys:
            channel_count = meta.get("channel_count")
            if isinstance(channel_count, int) and channel_count >= 0:
                dtype = self._dtype_from_meta(meta)
                prefix = f"{key}_ch"
                keyed: dict[int, str] = {}
                for ch_key in channel_keys:
                    suffix = ch_key[len(prefix) :]
                    try:
                        idx = int(suffix)
                    except ValueError:
                        continue
                    keyed[idx] = ch_key

                data = []
                for idx in range(channel_count):
                    ch_key = keyed.get(idx)
                    if ch_key is None:
                        data.append(np.zeros(0, dtype=dtype) if dtype is not None else np.array([]))
                        continue
                    arr = self.ctx._storage_call(storage, "load_memmap", ch_key, run_id)
                    if arr is None:
                        arr = np.zeros(0, dtype=dtype) if dtype is not None else np.array([])
                    data.append(arr)
            else:
                data = [
                    self.ctx._storage_call(storage, "load_memmap", ch_key, run_id)
                    for ch_key in channel_keys
                ]
        else:
            data = self.ctx._storage_call(storage, "load_memmap", key, run_id)

        if data is not None:
            if self.ctx.config.get("show_progress", True):
                print(f"[cache] Loaded '{name}' from disk (run_id: {run_id})")
            self.ctx._set_data(run_id, name, data)
        return data

    def is_disk_cache_valid(self, run_id: str, name: str, key: str) -> bool:
        """Check whether disk cache exists and lineage matches without loading data."""
        storage = self.ctx._get_storage_for_data_name(name)
        channel_keys = self.ctx._list_channel_keys(storage, run_id, key)
        has_base = self.ctx._storage_exists(storage, key, run_id)
        if not has_base and not channel_keys:
            return False
        if channel_keys and self.ctx._expects_flat_channel_array(name):
            return False
        meta_key = channel_keys[0] if channel_keys else key

        try:
            meta = self.ctx._storage_call(storage, "get_metadata", meta_key, run_id)
        except Exception:
            return False

        if meta and "lineage" in meta:
            current_lineage = self.ctx.get_lineage(name)
            s1 = json.dumps(meta["lineage"], sort_keys=True, default=str)
            s2 = json.dumps(current_lineage, sort_keys=True, default=str)
            return s1 == s2

        return True

    def is_cache_hit(self, run_id: str, name: str, load: bool = False) -> bool:
        """Check memory/disk cache status. Optionally load disk cache into memory."""
        if self.ctx._get_data_from_memory(run_id, name) is not None:
            return True

        if name not in self.ctx._plugins:
            return False

        key = self.ctx.key_for(run_id, name)
        if load:
            _data, cache_hit = self.ctx._cache_manager.check_cache(run_id, name, key)
            return cache_hit

        return self.is_disk_cache_valid(run_id, name, key)

    def clear_performance_caches(self) -> None:
        """Clear execution/lineage/key caches used for cache planning."""
        self.ctx._execution_plan_cache.clear()
        self.ctx._lineage_cache.clear()
        self.ctx._lineage_hash_cache.clear()
        self.ctx._key_cache.clear()
        self.ctx.logger.debug("Performance caches cleared")

    def invalidate_caches_for(self, data_name: str) -> None:
        """Invalidate cached plans/hash keys affected by a data name."""
        if data_name in self.ctx._execution_plan_cache:
            del self.ctx._execution_plan_cache[data_name]

        to_remove = []
        for cached_name, plan in self.ctx._execution_plan_cache.items():
            if data_name in plan:
                to_remove.append(cached_name)

        for name in to_remove:
            del self.ctx._execution_plan_cache[name]

        if data_name in self.ctx._lineage_cache:
            del self.ctx._lineage_cache[data_name]
        if data_name in self.ctx._lineage_hash_cache:
            del self.ctx._lineage_hash_cache[data_name]

        keys_to_remove = [k for k in self.ctx._key_cache if k[1] == data_name]
        for key in keys_to_remove:
            del self.ctx._key_cache[key]

        self.ctx.logger.debug("Caches invalidated for '%s'", data_name)

    def delete_disk_cache(
        self, key: str, run_id: str | None = None, data_name: str | None = None
    ) -> int:
        """Delete disk cache entries, including multi-channel and DataFrame artifacts."""
        count = 0
        storage = self.ctx._get_storage_for_data_name(data_name) if data_name else self.ctx.storage

        if self.ctx._storage_exists(storage, key, run_id):
            try:
                self.ctx._storage_call(storage, "delete", key, run_id)
                count += 1
            except Exception as e:
                self.ctx.logger.warning("Failed to delete cache key %s: %s", key, e)

        for ch_key in self.ctx._list_channel_keys(storage, run_id, key):
            try:
                self.ctx._storage_call(storage, "delete", ch_key, run_id)
                count += 1
            except Exception as e:
                self.ctx.logger.warning("Failed to delete multi-channel cache %s: %s", ch_key, e)

        if hasattr(storage, "save_dataframe"):
            if hasattr(storage, "work_dir") and run_id:
                dataframe_paths = [
                    os.path.join(storage.work_dir, run_id, storage.data_subdir, f"{key}.parquet"),
                    os.path.join(storage.work_dir, run_id, storage.data_subdir, f"{key}.pkl"),
                ]
            elif hasattr(storage, "db_path"):
                base_dir = os.path.dirname(storage.db_path)
                dataframe_paths = [
                    os.path.join(base_dir, f"{key}.parquet"),
                    os.path.join(base_dir, f"{key}.pkl"),
                ]
            else:
                dataframe_paths = []

            for dataframe_path in dataframe_paths:
                if os.path.exists(dataframe_path):
                    try:
                        os.remove(dataframe_path)
                        count += 1
                    except Exception as e:
                        self.ctx.logger.warning(
                            "Failed to delete dataframe cache file %s: %s",
                            dataframe_path,
                            e,
                        )

        return count
