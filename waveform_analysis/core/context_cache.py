from __future__ import annotations

import hashlib
import json
import os
from typing import Any

import numpy as np


class ContextCacheDomain:
    """Disk-cache read helpers used by Context."""

    def __init__(self, context: Any) -> None:
        self.ctx = context
        self._compatibility_hits: set[tuple[str, str]] = set()

    @staticmethod
    def _lineage_json(lineage: Any) -> str:
        return json.dumps(lineage, sort_keys=True, default=str)

    @classmethod
    def _without_adapter_info(cls, value: Any, adapter_values: list[str]) -> Any:
        """Remove only adapter_info while retaining every semantic field."""
        if isinstance(value, dict):
            cleaned = {}
            for key, child in value.items():
                if key == "adapter_info":
                    adapter_values.append(cls._lineage_json(child))
                else:
                    cleaned[key] = cls._without_adapter_info(child, adapter_values)
            return cleaned
        if isinstance(value, list):
            return [cls._without_adapter_info(child, adapter_values) for child in value]
        if isinstance(value, tuple):
            return tuple(cls._without_adapter_info(child, adapter_values) for child in value)
        return value

    @classmethod
    def _lineages_compatible(cls, cached: Any, current: Any) -> bool:
        """Accept exact lineage or the historical adapter-placement-only variant."""
        if cls._lineage_json(cached) == cls._lineage_json(current):
            return True

        cached_adapters: list[str] = []
        current_adapters: list[str] = []
        cached_base = cls._without_adapter_info(cached, cached_adapters)
        current_base = cls._without_adapter_info(current, current_adapters)
        if cls._lineage_json(cached_base) != cls._lineage_json(current_base):
            return False

        # Adapter metadata may historically be absent or attached to a nested
        # dependency. If both lineages declare it, every declaration must agree.
        declared = set(cached_adapters + current_adapters)
        return len(declared) <= 1

    def _candidate_cache_keys(self, run_id: str, name: str, canonical_key: str) -> list[str]:
        """Return canonical then historical cache identities for one product."""
        candidates = [canonical_key]

        base_lineage = self.ctx._get_base_lineage(name, set())
        base_hash = hashlib.sha1(self._lineage_json(base_lineage).encode()).hexdigest()[:8]
        direct_legacy_key = f"{run_id}-{name}-{base_hash}"
        if direct_legacy_key not in candidates:
            candidates.append(direct_legacy_key)

        prefix = f"{run_id}-{name}-"
        discovered: set[str] = set()
        storage = self.ctx._get_storage_for_data_name(name)
        for stored_key in self.ctx._storage_list_keys(storage, run_id):
            if not stored_key.startswith(prefix):
                continue
            base_key = stored_key
            channel_marker = base_key.rfind("_ch")
            if channel_marker >= 0 and base_key[channel_marker + 3 :].isdigit():
                base_key = base_key[:channel_marker]
            discovered.add(base_key)

        def candidate_order(candidate: str) -> tuple[float, str]:
            channel_keys = self.ctx._list_channel_keys(storage, run_id, candidate)
            meta_key = channel_keys[0] if channel_keys else candidate
            try:
                meta = self.ctx._storage_call(storage, "get_metadata", meta_key, run_id) or {}
                timestamp = float(meta.get("timestamp", float("-inf")))
            except (TypeError, ValueError, OSError):
                timestamp = float("-inf")
            return timestamp, candidate

        for candidate in sorted(discovered, key=candidate_order, reverse=True):
            if candidate not in candidates:
                candidates.append(candidate)
        return candidates

    def _resolve_disk_cache_key(self, run_id: str, name: str, canonical_key: str) -> str | None:
        """Resolve an exact or metadata-proven equivalent historical cache key."""
        storage = self.ctx._get_storage_for_data_name(name)
        current_lineage = self.ctx.get_lineage(name)

        # Keep the normal path cheap: an exact canonical key never requires a
        # historical-key scan.
        canonical_channels = self.ctx._list_channel_keys(storage, run_id, canonical_key)
        canonical_base = self.ctx._storage_exists(storage, canonical_key, run_id)
        if (canonical_base or canonical_channels) and not (
            canonical_channels and self.ctx._expects_flat_channel_array(name)
        ):
            meta_key = canonical_channels[0] if canonical_channels else canonical_key
            try:
                meta = self.ctx._storage_call(storage, "get_metadata", meta_key, run_id)
            except Exception:
                pass
            else:
                cached_lineage = meta.get("lineage") if meta else None
                if cached_lineage is None or self._lineages_compatible(
                    cached_lineage, current_lineage
                ):
                    return canonical_key

        for candidate in self._candidate_cache_keys(run_id, name, canonical_key):
            if candidate == canonical_key:
                continue
            channel_keys = self.ctx._list_channel_keys(storage, run_id, candidate)
            has_base = self.ctx._storage_exists(storage, candidate, run_id)
            if not has_base and not channel_keys:
                continue
            if channel_keys and self.ctx._expects_flat_channel_array(name):
                continue

            meta_key = channel_keys[0] if channel_keys else candidate
            try:
                meta = self.ctx._storage_call(storage, "get_metadata", meta_key, run_id)
                if meta is None and has_base and meta_key != candidate:
                    meta = self.ctx._storage_call(storage, "get_metadata", candidate, run_id)
            except Exception:
                continue

            cached_lineage = meta.get("lineage") if meta else None
            # Historical keys are read-only and require lineage proof.
            if cached_lineage is None or not self._lineages_compatible(
                cached_lineage, current_lineage
            ):
                continue
            hit = (run_id, name)
            if hit not in self._compatibility_hits:
                self.ctx.logger.info(
                    "Using compatible historical cache for '%s' (%s -> %s)",
                    name,
                    canonical_key,
                    candidate,
                )
                self._compatibility_hits.add(hit)
            return candidate
        return None

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

        # "<data_name>-<lineage_hash>" 与 run_id 无关，预计算一次供所有 run 复用。
        suffix = self.ctx._key_prefix_cache.get(data_name)
        if suffix is None:
            suffix = f"{data_name}-{lineage_hash}"
            self.ctx._key_prefix_cache[data_name] = suffix

        key = f"{run_id}-{suffix}"
        self.ctx._key_cache[cache_key] = key
        self._cap_key_cache()
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

                if name in {"records", "wave_pool"}:
                    removed = self._clear_internal_records_bundle_cache(run_id, verbose=verbose)
                    memory_count += removed
                    count += removed

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

    def _clear_internal_records_bundle_cache(self, run_id: str, verbose: bool = True) -> int:
        """Clear in-memory shared RecordsBundle cache entries for a run."""
        removed = 0
        bundle_prefix = "_records_bundle-"
        keys_to_remove = []

        for key in list(self.ctx._results):
            cached_run_id, name = key
            if cached_run_id != run_id:
                continue
            if not isinstance(name, str) or not name.startswith(bundle_prefix):
                continue
            keys_to_remove.append(key)

        for key in keys_to_remove:
            value = self.ctx._results.pop(key)
            cleanup = getattr(value, "cleanup", None)
            if callable(cleanup):
                cleanup()
            if key in self.ctx._results_lineage:
                del self.ctx._results_lineage[key]
            removed += 1
            if verbose:
                print(f"  ✓ 已清理内部 bundle 缓存: {key}")
            self.ctx.logger.debug("Cleared internal records bundle cache for %s", key)

        return removed

    def load_from_disk_with_check(self, run_id: str, name: str, key: str) -> Any | None:
        """Load cached data from disk after validating storage layout and lineage."""
        resolved_key = self._resolve_disk_cache_key(run_id, name, key)
        if resolved_key is None:
            return None
        key = resolved_key
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
        return self._resolve_disk_cache_key(run_id, name, key) is not None

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

    def _cap_key_cache(self) -> None:
        """Evict oldest entries when _key_cache exceeds its cap.

        key 可廉价重算（get_lineage 命中谱系缓存后仅字符串拼接），FIFO 淘汰安全。
        """
        max_entries = 8192
        while len(self.ctx._key_cache) > max_entries:
            self.ctx._key_cache.pop(next(iter(self.ctx._key_cache)), None)

    def clear_performance_caches(self) -> None:
        """Clear execution/lineage/key caches used for cache planning."""
        self.ctx._execution_plan_cache.clear()
        self.ctx._lineage_cache.clear()
        self.ctx._lineage_hash_cache.clear()
        self.ctx._key_prefix_cache.clear()
        self.ctx._key_cache.clear()
        self.ctx._run_key_list_cache.clear()
        self.ctx.logger.debug("Performance caches cleared")

    def invalidate_caches_for(self, data_name: str) -> None:
        """Invalidate cached plans/hash keys affected by a data name."""
        to_remove = []
        for cache_key, plan in self.ctx._execution_plan_cache.items():
            if cache_key[1] == data_name or data_name in plan:
                to_remove.append(cache_key)

        for cache_key in to_remove:
            del self.ctx._execution_plan_cache[cache_key]

        self._clear_lineage_key_caches(data_name)
        self.ctx.logger.debug("Caches invalidated for '%s'", data_name)

    def _clear_lineage_key_caches(self, data_name: str) -> None:
        """Clear lineage/hash/key performance caches for a data name."""
        self.ctx._lineage_cache.pop(data_name, None)
        self.ctx._lineage_hash_cache.pop(data_name, None)
        self.ctx._key_prefix_cache.pop(data_name, None)
        keys_to_remove = [k for k in self.ctx._key_cache if k[1] == data_name]
        for key in keys_to_remove:
            del self.ctx._key_cache[key]

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

        if count > 0:
            self.ctx._invalidate_storage_key_list_cache(storage, run_id)
        return count
