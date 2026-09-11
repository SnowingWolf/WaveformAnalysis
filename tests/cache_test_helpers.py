"""Shared helpers for cache tests (cache analyzer / cleaner / diagnostics / statistics)."""

from collections.abc import Iterable

import numpy as np

from waveform_analysis.core.context import Context

# 每个条目: (run_id, data_name, size, timestamp_or_None)
CacheEntrySpec = tuple[str, str, int, float | None]


def build_cache_context(
    storage_dir: str,
    entries: Iterable[CacheEntrySpec],
    *,
    with_lineage: bool = False,
) -> Context:
    """创建带有预置缓存条目的 Context。

    对每个条目 ``(run_id, data_name, size, timestamp)``：
    - 保存 ``size`` 长度的 memmap 数据，key 为 ``{run_id}-{data_name}-abc123``；
    - 更新元数据 ``plugin_version``（可选 ``lineage``）；
    - ``timestamp`` 不为 None 时写入元数据 ``timestamp``。

    行为与原先各 cache 测试文件中的局部 fixture 完全一致。
    """
    ctx = Context(storage_dir=storage_dir)
    storage = ctx.storage

    for run_id, data_name, size, timestamp in entries:
        key = f"{run_id}-{data_name}-abc123"
        data = np.zeros(size, dtype=[("time", "<f8"), ("value", "<f4")])
        storage.save_memmap(key, data, run_id=run_id)

        meta = storage.get_metadata(key, run_id)
        if meta:
            meta["plugin_version"] = "1.0.0"
            if with_lineage:
                meta["lineage"] = {"version": "1.0.0"}
            if timestamp is not None:
                meta["timestamp"] = timestamp
            storage.save_metadata(key, meta, run_id)

    return ctx
