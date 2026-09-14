"""Hit merge 共享计算 - 供 hit_merged / hit_merge_clusters / hit_merged_components 复用。

本模块持有 hit merge 家族的核心计算（dtype 常量、集群合并、merged 构建）。
属主：hit_merged bundle；兄弟 bundle 单向依赖本模块。
"""

from collections.abc import Iterator
from contextlib import nullcontext
from dataclasses import dataclass
import hashlib
from typing import Any, NamedTuple

import numpy as np

try:
    from numba import njit

    _NUMBA_AVAILABLE = True
except ImportError:
    _NUMBA_AVAILABLE = False
    njit = None

from waveform_analysis.core.hardware.channel import group_indices_by_hardware_channel
from waveform_analysis.core.plugins.builtin.cpu._dt_compat import (
    require_dt_array,
    resolve_dt_config,
)
from waveform_analysis.core.plugins.core.base import Plugin

HIT_MERGED_DTYPE = np.dtype(
    [
        ("merged_id", "i8"),
        ("position", "i8"),
        ("time_start", "i8"),
        ("time_end", "i8"),
        ("sample_start", "i4"),
        ("sample_end", "i4"),
        ("width", "f4"),
        ("dt", "i4"),
        ("timestamp", "i8"),
        ("board", "i2"),
        ("channel", "i2"),
        ("record_id", "i8"),
        ("component_offset", "i8"),
        ("component_count", "i4"),
        ("is_single_record", "?"),
    ]
)

HIT_MERGED_COMPONENTS_DTYPE = np.dtype(
    [
        ("merged_index", "i8"),
        ("hit_index", "i8"),
    ]
)

HIT_MERGE_CLUSTERS_DTYPE = np.dtype(
    [
        ("cluster_index", "i8"),
        ("hit_index", "i8"),
    ]
)


def _get_field_safe(arr: np.ndarray, *candidates: str) -> np.ndarray:
    """Safely get field from array (supports multiple candidate names).

    This replaces the hot _pick function which was called 895k times.
    """
    for name in candidates:
        if name in arr.dtype.names:
            return arr[name]
    raise ValueError(f"None of {candidates} found in array with fields {arr.dtype.names}")


def _resolve_sample_fields(dtype: np.dtype) -> tuple[str, str] | tuple[None, None]:
    names = set(dtype.names or ())
    if {"sample_start", "sample_end"}.issubset(names):
        return "sample_start", "sample_end"
    if {"edge_start", "edge_end"}.issubset(names):
        return "edge_start", "edge_end"
    return None, None


def _materialize_array(data: Any, data_name: str, output_dtype: np.dtype) -> np.ndarray:
    if isinstance(data, np.ndarray):
        return data

    if not isinstance(data, Iterator) and not hasattr(data, "__next__"):
        raise ValueError(f"{data_name} expects a structured array or chunk stream")

    arrays: list[np.ndarray] = []
    total = 0
    for item in data:
        chunk_data = item if isinstance(item, np.ndarray) else getattr(item, "data", item)
        if not isinstance(chunk_data, np.ndarray):
            raise ValueError(f"{data_name} stream items must provide ndarray data")
        if len(chunk_data) > 0:
            arrays.append(chunk_data)
            total += len(chunk_data)

    if not arrays:
        return np.zeros(0, dtype=output_dtype)

    out = np.empty(total, dtype=arrays[0].dtype)
    cursor = 0
    for arr in arrays:
        n = len(arr)
        out[cursor : cursor + n] = arr
        cursor += n
    return out


# Numba-accelerated cluster merging
if _NUMBA_AVAILABLE:

    @njit(cache=True, nogil=True)  # type: ignore[misc]
    def _merge_clusters_numba(
        abs_starts: np.ndarray,
        abs_ends: np.ndarray,
        dt_ps: np.ndarray,
        merge_gap_ps: int,
        max_total_width_ps: int,
    ) -> tuple:
        """Numba JIT-compiled cluster merging.

        Returns (cluster_starts, cluster_ends) as index arrays.
        ~10-20x faster than Python loop.
        """
        n = len(abs_starts)
        if n == 0:
            return (np.empty(0, dtype=np.int32), np.empty(0, dtype=np.int32))

        # Pre-allocate for worst case (no merging)
        starts = np.empty(n, dtype=np.int32)
        ends = np.empty(n, dtype=np.int32)
        n_clusters = 0

        cluster_start_idx = 0
        cluster_start_ps = abs_starts[0]
        cluster_end_ps = abs_ends[0]
        cluster_dt = dt_ps[0]

        for i in range(1, n):
            gap = abs_starts[i] - cluster_end_ps
            next_end = max(cluster_end_ps, abs_ends[i])
            total_width = next_end - cluster_start_ps
            same_dt = dt_ps[i] == cluster_dt

            if (
                merge_gap_ps > 0
                and same_dt
                and gap <= merge_gap_ps
                and total_width <= max_total_width_ps
            ):
                # Merge into current cluster
                cluster_end_ps = next_end
            else:
                # Save current cluster
                starts[n_clusters] = cluster_start_idx
                ends[n_clusters] = i
                n_clusters += 1
                # Start new cluster
                cluster_start_idx = i
                cluster_start_ps = abs_starts[i]
                cluster_end_ps = abs_ends[i]
                cluster_dt = dt_ps[i]

        # Save last cluster
        starts[n_clusters] = cluster_start_idx
        ends[n_clusters] = n
        n_clusters += 1

        return (starts[:n_clusters].copy(), ends[:n_clusters].copy())

else:
    # Fallback when Numba is not available
    def _merge_clusters_numba(
        abs_starts: np.ndarray,
        abs_ends: np.ndarray,
        dt_ps: np.ndarray,
        merge_gap_ps: int,
        max_total_width_ps: int,
    ) -> tuple:
        """Python fallback when Numba unavailable."""
        raise RuntimeError("Numba not available")


def _pick(hit: np.void, *candidates: str) -> Any:
    """Legacy compatibility function - prefer _get_field_safe for arrays."""
    for name in candidates:
        if hit.dtype.names and name in hit.dtype.names:
            return hit[name]
    raise KeyError(f"Missing fields {candidates} in HIT_DTYPE")


def _resolve_merge_config(context: Any, plugin: Plugin) -> tuple[float, float, int | None]:
    merge_gap_ns = float(context.get_config(plugin, "merge_gap_ns"))
    max_total_width_ns = float(context.get_config(plugin, "max_total_width_ns"))
    explicit_dt = resolve_dt_config(
        context, plugin, deprecated_keys=("sampling_interval_ns", "dt_ns")
    )
    return merge_gap_ns, max_total_width_ns, explicit_dt


class _EnrichedArrays(NamedTuple):
    source_indices: np.ndarray
    abs_start_ps: np.ndarray
    abs_end_ps: np.ndarray
    dt_ns: np.ndarray
    dt_ps: np.ndarray


def _build_enriched_arrays(
    hits: np.ndarray,
    dt_values: np.ndarray,
    source_indices: np.ndarray,
    pre_trigger_ps: int = 0,
) -> _EnrichedArrays:
    n = len(hits)
    if n == 0:
        return _EnrichedArrays(
            source_indices=np.zeros(0, dtype=np.int64),
            abs_start_ps=np.zeros(0, dtype=np.int64),
            abs_end_ps=np.zeros(0, dtype=np.int64),
            dt_ns=np.zeros(0, dtype=np.int64),
            dt_ps=np.zeros(0, dtype=np.int64),
        )

    timestamps = _get_field_safe(hits, "timestamp", "hit_timestamp_ps").astype(np.int64)
    positions = _get_field_safe(hits, "position", "hit_sample_idx").astype(np.int64)
    edge_starts = _get_field_safe(hits, "edge_start", "sample_start", "hit_left_sample_idx").astype(
        np.int64
    )
    edge_ends = _get_field_safe(hits, "edge_end", "sample_end", "hit_right_sample_idx").astype(
        np.int64
    )

    dt_ns = dt_values.astype(np.int64)
    dt_ps = dt_values.astype(np.int64) * np.int64(1000)

    # 修正 timestamp：如果配置了 pre_trigger，则从触发点时间修正到 sample 0 时间
    corrected_timestamps = timestamps - np.int64(pre_trigger_ps)
    abs_start_ps = corrected_timestamps + (edge_starts - positions) * dt_ps
    abs_end_ps = corrected_timestamps + (edge_ends - positions) * dt_ps

    return _EnrichedArrays(
        source_indices=source_indices.astype(np.int64, copy=False),
        abs_start_ps=abs_start_ps,
        abs_end_ps=abs_end_ps,
        dt_ns=dt_ns,
        dt_ps=dt_ps,
    )


def _same_record_window(
    hits: np.ndarray,
    hit_indices: np.ndarray,
    start_name: str,
    end_name: str,
) -> tuple[int, int]:
    record_ids = hits["record_id"][hit_indices]
    if len(record_ids) == 0:
        return -1, -1

    first_record_id = record_ids[0]
    if not np.all(record_ids == first_record_id):
        return -1, -1

    sample_start = int(np.min(hits[start_name][hit_indices]))
    sample_end = int(np.max(hits[end_name][hit_indices]))
    return sample_start, sample_end


def _cluster_bounds_python(
    abs_starts: np.ndarray,
    abs_ends: np.ndarray,
    dt_ps: np.ndarray,
    merge_gap_ps: int,
    max_total_width_ps: int,
) -> tuple[np.ndarray, np.ndarray]:
    starts: list[int] = []
    ends: list[int] = []

    cluster_start_idx = 0
    cluster_start_ps = int(abs_starts[0])
    cluster_end_ps = int(abs_ends[0])
    cluster_dt = int(dt_ps[0])

    for idx in range(1, len(abs_starts)):
        gap_ps = int(abs_starts[idx]) - cluster_end_ps
        next_end = max(cluster_end_ps, int(abs_ends[idx]))
        total_width_ps = next_end - cluster_start_ps
        same_dt = int(dt_ps[idx]) == cluster_dt

        if (
            merge_gap_ps > 0
            and same_dt
            and gap_ps <= merge_gap_ps
            and total_width_ps <= max_total_width_ps
        ):
            cluster_end_ps = next_end
        else:
            starts.append(cluster_start_idx)
            ends.append(idx)
            cluster_start_idx = idx
            cluster_start_ps = int(abs_starts[idx])
            cluster_end_ps = int(abs_ends[idx])
            cluster_dt = int(dt_ps[idx])

    starts.append(cluster_start_idx)
    ends.append(len(abs_starts))
    return np.asarray(starts, dtype=np.int32), np.asarray(ends, dtype=np.int32)


def _fill_cluster_rows_from_bounds(
    rows: np.ndarray,
    row_offset: int,
    sorted_source_indices: np.ndarray,
    cluster_starts: np.ndarray,
    cluster_ends: np.ndarray,
    cluster_offset: int,
) -> int:
    """Fill one channel's cluster rows into the shared output buffer."""

    n_clusters = len(cluster_starts)
    if n_clusters == 0:
        return row_offset

    counts = (cluster_ends - cluster_starts).astype(np.int64, copy=False)
    row_end = row_offset + len(sorted_source_indices)
    channel_rows = rows[row_offset:row_end]
    channel_rows["cluster_index"] = np.repeat(
        np.arange(cluster_offset, cluster_offset + n_clusters, dtype=np.int64),
        counts,
    )
    channel_rows["hit_index"] = sorted_source_indices
    return row_end


def _profile_block(profiler: Any | None, key: str):
    """Return a profiler timing block without requiring profiling support."""

    if profiler is None:
        return nullcontext()
    return profiler.timeit(key)


def _compute_cluster_rows(
    hits: np.ndarray,
    merge_gap_ns: float,
    max_total_width_ns: float,
    explicit_dt: int | None,
    plugin_name: str,
    pre_trigger_ps: int = 0,
    enriched: _EnrichedArrays | None = None,
    *,
    profiler: Any | None = None,
) -> np.ndarray:
    if len(hits) == 0:
        return np.zeros(0, dtype=HIT_MERGE_CLUSTERS_DTYPE)

    if "board" in hits.dtype.names:
        boards = hits["board"]
    else:
        boards = np.zeros(len(hits), dtype=np.int16)
    if "channel" not in hits.dtype.names:
        raise ValueError(f"{plugin_name} requires hit data with a 'channel' field")
    channels = hits["channel"]

    cluster_rows = np.empty(len(hits), dtype=HIT_MERGE_CLUSTERS_DTYPE)
    row_offset = 0
    cluster_offset = 0
    merge_gap_ps = int(round(merge_gap_ns * 1e3))
    max_total_width_ps = int(round(max_total_width_ns * 1e3))

    with _profile_block(profiler, "hit_merged.group_hardware_channels"):
        hardware_channels = group_indices_by_hardware_channel(boards, channels)

    if enriched is None:
        # Keep direct callers compatible while making the canonical path build
        # these arrays once for the complete hit table before channel grouping.
        enriched = _build_enriched_for_hits(
            hits,
            explicit_dt=explicit_dt,
            plugin_name=plugin_name,
            pre_trigger_ps=pre_trigger_ps,
        )

    for _hw_channel, indices in hardware_channels.items():
        if len(indices) == 0:
            continue

        # ``group_indices_by_hardware_channel`` returns stable row indices.
        # Indexing the one global enriched table with those rows preserves the
        # historical per-channel order, including equal-start-time ties.
        channel_indices = np.asarray(indices, dtype=np.int64)
        with _profile_block(profiler, "hit_merged.per_channel_mergesort"):
            channel_abs_starts = enriched.abs_start_ps[channel_indices]
            order = np.argsort(channel_abs_starts, kind="mergesort")
            sorted_indices = channel_indices[order]
            abs_starts = channel_abs_starts[order]
            abs_ends = enriched.abs_end_ps[sorted_indices]
            dts = enriched.dt_ps[sorted_indices]
            sorted_source_indices = enriched.source_indices[sorted_indices]

        with _profile_block(profiler, "hit_merged.cluster_scan"):
            if _NUMBA_AVAILABLE and len(abs_starts) > 50:
                cluster_starts, cluster_ends = _merge_clusters_numba(
                    abs_starts, abs_ends, dts, merge_gap_ps, max_total_width_ps
                )
            else:
                # Numba 不可用时直接报错
                if not _NUMBA_AVAILABLE:
                    raise RuntimeError("Numba is required for hit merging")
                cluster_starts, cluster_ends = _cluster_bounds_python(
                    abs_starts, abs_ends, dts, merge_gap_ps, max_total_width_ps
                )

        row_offset = _fill_cluster_rows_from_bounds(
            cluster_rows,
            row_offset,
            sorted_source_indices,
            cluster_starts,
            cluster_ends,
            cluster_offset,
        )
        cluster_offset += len(cluster_starts)

    with _profile_block(profiler, "hit_merged.cluster_rows_prealloc"):
        return cluster_rows[:row_offset]


def _build_enriched_for_hits(
    hits: np.ndarray,
    explicit_dt: int | None,
    plugin_name: str,
    pre_trigger_ps: int = 0,
) -> _EnrichedArrays:
    dt_values = require_dt_array(
        hits,
        explicit_dt=explicit_dt,
        plugin_name=plugin_name,
        data_name="hit_threshold",
    )
    return _build_enriched_arrays(
        hits, dt_values, np.arange(len(hits), dtype=np.int64), pre_trigger_ps=pre_trigger_ps
    )


def _cluster_bounds(cluster_rows: np.ndarray) -> list[tuple[int, int, int]]:
    if len(cluster_rows) == 0:
        return []

    cluster_indices = np.asarray(cluster_rows["cluster_index"], dtype=np.int64)
    boundaries = np.flatnonzero(np.diff(cluster_indices) != 0) + 1
    starts = np.concatenate(([0], boundaries))
    ends = np.concatenate((boundaries, [len(cluster_rows)]))
    return [
        (int(cluster_indices[start]), int(start), int(end))
        for start, end in zip(starts, ends, strict=False)
    ]


def _cluster_bounds_arrays(cluster_rows: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    cluster_index = cluster_rows["cluster_index"]
    boundaries = np.flatnonzero(np.diff(cluster_index) != 0) + 1

    starts = np.empty(len(boundaries) + 1, dtype=np.int64)
    starts[0] = 0
    starts[1:] = boundaries

    ends = np.empty_like(starts)
    ends[:-1] = boundaries
    ends[-1] = len(cluster_rows)

    counts = ends - starts
    return starts, ends, counts


def _hits_to_merged_fast(hits: np.ndarray, explicit_dt: int | None, plugin_name: str) -> np.ndarray:
    dt_values = require_dt_array(
        hits,
        explicit_dt=explicit_dt,
        plugin_name=plugin_name,
        data_name="hit_threshold",
    )
    start_name, end_name = _resolve_sample_fields(hits.dtype)
    if start_name is None or end_name is None:
        raise ValueError(f"{plugin_name} requires hit data with sample start/end fields")

    out = np.zeros(len(hits), dtype=HIT_MERGED_DTYPE)
    out["merged_id"] = np.arange(len(hits), dtype=np.int64)
    out["position"] = _get_field_safe(hits, "position", "hit_sample_idx")
    out["sample_start"] = hits[start_name]
    out["sample_end"] = hits[end_name]
    out["width"] = _get_field_safe(hits, "width")
    out["dt"] = dt_values
    out["timestamp"] = _get_field_safe(hits, "timestamp", "hit_timestamp_ps")
    out["board"] = hits["board"] if "board" in hits.dtype.names else 0
    out["channel"] = hits["channel"]
    out["record_id"] = hits["record_id"]
    out["component_offset"] = np.arange(len(hits), dtype=np.int64)
    out["component_count"] = 1
    out["is_single_record"] = True

    # 计算绝对时间
    positions = out["position"]
    timestamps = out["timestamp"]
    sample_starts = out["sample_start"]
    sample_ends = out["sample_end"]
    dt_ps = dt_values.astype(np.int64) * 1000

    out["time_start"] = timestamps + (sample_starts - positions) * dt_ps
    out["time_end"] = timestamps + (sample_ends - positions) * dt_ps

    return out


def _hits_to_cluster_rows_fast(hits: np.ndarray) -> np.ndarray:
    rows = np.zeros(len(hits), dtype=HIT_MERGE_CLUSTERS_DTYPE)
    rows["cluster_index"] = np.arange(len(hits), dtype=np.int64)
    rows["hit_index"] = np.arange(len(hits), dtype=np.int64)
    return rows


def _compute_canonical_cluster_rows(
    hits: np.ndarray,
    context: Any,
    merge_plugin: Plugin,
    pre_trigger_ps: int,
    *,
    profiler: Any | None = None,
) -> tuple[np.ndarray, int | None, bool, _EnrichedArrays | None]:
    merge_gap_ns, max_total_width_ns, explicit_dt = _resolve_merge_config(context, merge_plugin)
    if merge_gap_ns <= 0:
        return _hits_to_cluster_rows_fast(hits), explicit_dt, True, None
    enriched = _build_enriched_for_hits(
        hits,
        explicit_dt=explicit_dt,
        plugin_name=merge_plugin.provides,
        pre_trigger_ps=pre_trigger_ps,
    )
    return (
        _compute_cluster_rows(
            hits,
            merge_gap_ns=merge_gap_ns,
            max_total_width_ns=max_total_width_ns,
            explicit_dt=explicit_dt,
            plugin_name=merge_plugin.provides,
            pre_trigger_ps=pre_trigger_ps,
            enriched=enriched,
            profiler=profiler,
        ),
        explicit_dt,
        False,
        enriched,
    )


_HIT_MERGE_CLUSTER_ROWS_CACHE_PREFIX = "_hit_merge_cluster_rows-"


@dataclass(frozen=True)
class _CanonicalClusterRowsCache:
    """Context-local canonical membership shared by the hit-merge family.

    The membership array is deliberately kept as an internal Context result rather
    than registered as a plugin output.  This lets ``hit_merged_components`` and the
    optional ``hit_merge_clusters`` output reuse the rows built by ``hit_merged``
    without changing the DAG or forcing a second persisted relation cache.
    """

    guard: str
    rows: np.ndarray
    explicit_dt: int | None
    merge_disabled: bool


def _hit_merge_cluster_rows_guard(
    context: Any,
    run_id: str,
    merge_plugin: Plugin,
    pre_trigger_ps: int,
) -> str:
    """Build a bounded guard for the Context-local membership cache.

    ``Context.key_for`` captures plugin version, tracked configuration and upstream
    lineage.  The explicit config tuple and pre-trigger offset are included as well
    because lightweight test contexts and some compatibility adapters do not expose
    a complete lineage implementation.  The digest keeps the internal result key
    short and avoids storing user configuration text in the Context namespace.
    """

    lineage_keys: list[str] = []
    key_for = getattr(context, "key_for", None)
    if callable(key_for):
        for data_name in ("hit_merged", "hit_threshold"):
            try:
                lineage_keys.append(f"{data_name}={key_for(run_id, data_name)}")
            except Exception:
                lineage_keys.append(f"{data_name}=unavailable")
    else:
        lineage_keys.extend(("hit_merged=unavailable", "hit_threshold=unavailable"))

    config_values: list[str] = []
    get_config = getattr(context, "get_config", None)
    for name in ("merge_gap_ns", "max_total_width_ns", "dt"):
        try:
            value = get_config(merge_plugin, name) if callable(get_config) else None
        except Exception:
            value = "unavailable"
        config_values.append(f"{name}={value!r}")

    payload = "|".join(
        (
            f"run_id={run_id}",
            f"plugin={merge_plugin.__class__.__module__}.{merge_plugin.__class__.__qualname__}",
            f"version={getattr(merge_plugin, 'version', '0.0.0')}",
            *lineage_keys,
            *config_values,
            f"pre_trigger_ps={int(pre_trigger_ps)}",
        )
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _hit_merge_cluster_rows_cache_key(guard: str) -> str:
    """Return the private Context result key for one canonical membership guard."""

    return f"{_HIT_MERGE_CLUSTER_ROWS_CACHE_PREFIX}{guard}"


def _context_result_get(context: Any, run_id: str, name: str) -> Any | None:
    results = getattr(context, "_results", None)
    if not isinstance(results, dict):
        return None
    lock = getattr(context, "_data_lock", None)
    if lock is None:
        return results.get((run_id, name))
    with lock:
        return results.get((run_id, name))


def _context_result_remove(context: Any, run_id: str, name: str) -> None:
    results = getattr(context, "_results", None)
    if not isinstance(results, dict):
        return
    lock = getattr(context, "_data_lock", None)
    if lock is None:
        results.pop((run_id, name), None)
        return
    with lock:
        results.pop((run_id, name), None)


def _context_result_store(context: Any, run_id: str, name: str, value: Any) -> None:
    """Store a private result without exposing it as a Context attribute."""

    results = getattr(context, "_results", None)
    if not isinstance(results, dict):
        # Minimal compatibility contexts may only expose the historical helper.
        set_data = getattr(context, "_set_data", None)
        if callable(set_data):
            set_data(run_id, name, value)
        return
    lock = getattr(context, "_data_lock", None)
    if lock is None:
        results[(run_id, name)] = value
        return
    with lock:
        results[(run_id, name)] = value


def _clear_hit_merge_cluster_rows_cache(
    context: Any,
    run_id: str | None = None,
    *,
    keep: str | None = None,
) -> int:
    """Release private membership arrays for one run or the whole Context.

    Context cache/config invalidation calls this helper explicitly.  The cache is
    owned by the Context (not a module-global registry), so normal Context
    destruction also releases all rows without requiring weak-reference callbacks.
    """

    results = getattr(context, "_results", None)
    if not isinstance(results, dict):
        return 0
    lock = getattr(context, "_data_lock", None)
    removed = 0

    def remove_stale() -> None:
        nonlocal removed
        for result_key in list(results):
            if not isinstance(result_key, tuple) or len(result_key) != 2:
                continue
            cached_run_id, cached_name = result_key
            if (
                (run_id is None or cached_run_id == run_id)
                and isinstance(cached_name, str)
                and cached_name.startswith(_HIT_MERGE_CLUSTER_ROWS_CACHE_PREFIX)
                and cached_name != keep
            ):
                results.pop(result_key, None)
                removed += 1

    if lock is None:
        remove_stale()
    else:
        with lock:
            remove_stale()
    return removed


def _compute_canonical_cluster_rows_shared(
    hits: np.ndarray,
    context: Any,
    merge_plugin: Plugin,
    pre_trigger_ps: int,
    run_id: str,
) -> tuple[np.ndarray, int | None, bool]:
    """Compute or reuse canonical membership without exposing enriched arrays."""

    cluster_rows, explicit_dt, merge_disabled, _enriched = (
        _compute_canonical_cluster_rows_shared_with_enriched(
            hits, context, merge_plugin, pre_trigger_ps, run_id
        )
    )
    return cluster_rows, explicit_dt, merge_disabled


def _compute_canonical_cluster_rows_shared_with_enriched(
    hits: np.ndarray,
    context: Any,
    merge_plugin: Plugin,
    pre_trigger_ps: int,
    run_id: str,
) -> tuple[np.ndarray, int | None, bool, _EnrichedArrays | None]:
    """Compute or reuse canonical cluster membership for one Context/run/lineage."""

    guard = _hit_merge_cluster_rows_guard(context, run_id, merge_plugin, pre_trigger_ps)
    cache_key = _hit_merge_cluster_rows_cache_key(guard)
    cached = _context_result_get(context, run_id, cache_key)
    if isinstance(cached, _CanonicalClusterRowsCache) and cached.guard == guard:
        logger = getattr(context, "logger", None)
        if logger is not None:
            logger.debug("hit merge cluster rows cache hit: run_id=%s guard=%s", run_id, guard[:12])
        # Enriched arrays are intentionally transient; retaining them in the
        # Context-local membership cache would pin several full-size arrays.
        return cached.rows, cached.explicit_dt, cached.merge_disabled, None

    if cached is not None:
        _context_result_remove(context, run_id, cache_key)

    cluster_rows, explicit_dt, merge_disabled, enriched = _compute_canonical_cluster_rows(
        hits,
        context,
        merge_plugin,
        pre_trigger_ps,
        profiler=getattr(context, "profiler", None),
    )
    _clear_hit_merge_cluster_rows_cache(context, run_id, keep=cache_key)
    _context_result_store(
        context,
        run_id,
        cache_key,
        _CanonicalClusterRowsCache(
            guard=guard,
            rows=cluster_rows,
            explicit_dt=explicit_dt,
            merge_disabled=merge_disabled,
        ),
    )
    logger = getattr(context, "logger", None)
    if logger is not None:
        logger.debug("hit merge cluster rows cache miss: run_id=%s guard=%s", run_id, guard[:12])
    return cluster_rows, explicit_dt, merge_disabled, enriched


def _cluster_rows_to_components(cluster_rows: np.ndarray) -> np.ndarray:
    out = np.zeros(len(cluster_rows), dtype=HIT_MERGED_COMPONENTS_DTYPE)
    out["merged_index"] = cluster_rows["cluster_index"]
    out["hit_index"] = cluster_rows["hit_index"]
    return out


def _fill_multi_hit_clusters_python(
    multi_out: np.ndarray,
    starts: np.ndarray,
    ends: np.ndarray,
    hit_index_all: np.ndarray,
    abs_start_ps: np.ndarray,
    abs_end_ps: np.ndarray,
    positions: np.ndarray,
    sample_starts: np.ndarray,
    sample_ends: np.ndarray,
    record_ids: np.ndarray,
    dt_values: np.ndarray,
    timestamps: np.ndarray,
    channels: np.ndarray,
    boards: np.ndarray,
    out_position: np.ndarray,
    out_time_start: np.ndarray,
    out_time_end: np.ndarray,
    out_sample_start: np.ndarray,
    out_sample_end: np.ndarray,
    out_width: np.ndarray,
    out_dt: np.ndarray,
    out_timestamp: np.ndarray,
    out_channel: np.ndarray,
    out_record_id: np.ndarray,
    out_component_offset: np.ndarray,
    out_component_count: np.ndarray,
    out_is_single_record: np.ndarray,
    out_board: np.ndarray,
) -> None:
    """Reference implementation for filling multi-hit merged rows.

    This intentionally mirrors the historical Python loop in
    ``_build_merged_from_cluster_rows``.  Besides being a fallback when Numba is
    unavailable, it is the oracle used by the focused exactness tests for the
    serial kernel below.
    """

    for out_idx in multi_out:
        start = int(starts[out_idx])
        end = int(ends[out_idx])
        hit_indices = hit_index_all[start:end]
        cluster_abs_starts = abs_start_ps[hit_indices]
        cluster_abs_ends = abs_end_ps[hit_indices]

        cluster_start_ps = int(np.min(cluster_abs_starts))
        cluster_end_ps = int(np.max(cluster_abs_ends))
        mid2 = cluster_start_ps + cluster_end_ps
        mids2 = cluster_abs_starts + cluster_abs_ends
        anchor_local = int(np.argmin(np.abs(mids2 - mid2)))
        anchor_idx = int(hit_indices[anchor_local])

        record_values = record_ids[hit_indices]
        if len(record_values) == 0 or not np.all(record_values == record_values[0]):
            sample_start = -1
            sample_end = -1
        else:
            sample_start = int(np.min(sample_starts[hit_indices]))
            sample_end = int(np.max(sample_ends[hit_indices]))

        out_position[out_idx] = positions[anchor_idx]
        out_time_start[out_idx] = cluster_start_ps
        out_time_end[out_idx] = cluster_end_ps
        out_sample_start[out_idx] = sample_start
        out_sample_end[out_idx] = sample_end
        out_is_single_record[out_idx] = sample_start >= 0 and sample_end >= 0
        if sample_start < 0 or sample_end < 0:
            out_width[out_idx] = -1.0
        else:
            out_width[out_idx] = float(sample_end - sample_start)
        out_dt[out_idx] = dt_values[anchor_idx]
        out_timestamp[out_idx] = timestamps[anchor_idx]
        out_channel[out_idx] = channels[anchor_idx]
        out_record_id[out_idx] = record_ids[anchor_idx]
        out_component_offset[out_idx] = start
        out_component_count[out_idx] = end - start
        out_board[out_idx] = boards[anchor_idx]


if _NUMBA_AVAILABLE:

    @njit(cache=True, nogil=True)  # type: ignore[misc]
    def _fill_multi_hit_clusters_numba(
        multi_out: np.ndarray,
        starts: np.ndarray,
        ends: np.ndarray,
        hit_index_all: np.ndarray,
        abs_start_ps: np.ndarray,
        abs_end_ps: np.ndarray,
        positions: np.ndarray,
        sample_starts: np.ndarray,
        sample_ends: np.ndarray,
        record_ids: np.ndarray,
        dt_values: np.ndarray,
        timestamps: np.ndarray,
        channels: np.ndarray,
        boards: np.ndarray,
        out_position: np.ndarray,
        out_time_start: np.ndarray,
        out_time_end: np.ndarray,
        out_sample_start: np.ndarray,
        out_sample_end: np.ndarray,
        out_width: np.ndarray,
        out_dt: np.ndarray,
        out_timestamp: np.ndarray,
        out_channel: np.ndarray,
        out_record_id: np.ndarray,
        out_component_offset: np.ndarray,
        out_component_count: np.ndarray,
        out_is_single_record: np.ndarray,
        out_board: np.ndarray,
    ) -> None:
        """Fill multi-hit rows with a serial Numba CSR-style kernel.

        ``starts``/``ends`` are the CSR row pointers and ``hit_index_all`` is the
        flat membership index array.  Every argument is a primitive NumPy field
        view (or a primitive output view); no structured array is passed into the
        jitted function.  The loop is deliberately serial: the output rows are
        independent, but preserving the canonical exact path and avoiding nested
        thread pools is more important than speculative parallelism here.
        """

        for multi_idx in range(len(multi_out)):
            out_idx = multi_out[multi_idx]
            start = starts[out_idx]
            end = ends[out_idx]
            first_hit_idx = hit_index_all[start]

            cluster_start_ps = abs_start_ps[first_hit_idx]
            cluster_end_ps = abs_end_ps[first_hit_idx]
            first_record_id = record_ids[first_hit_idx]
            same_record = True
            sample_start = sample_starts[first_hit_idx]
            sample_end = sample_ends[first_hit_idx]

            for member_pos in range(start, end):
                hit_idx = hit_index_all[member_pos]
                hit_start_ps = abs_start_ps[hit_idx]
                hit_end_ps = abs_end_ps[hit_idx]
                if hit_start_ps < cluster_start_ps:
                    cluster_start_ps = hit_start_ps
                if hit_end_ps > cluster_end_ps:
                    cluster_end_ps = hit_end_ps
                if record_ids[hit_idx] != first_record_id:
                    same_record = False
                if sample_starts[hit_idx] < sample_start:
                    sample_start = sample_starts[hit_idx]
                if sample_ends[hit_idx] > sample_end:
                    sample_end = sample_ends[hit_idx]

            # The historical implementation uses np.argmin over the int64
            # midpoint distances, which chooses the first member on a tie.
            mid2 = cluster_start_ps + cluster_end_ps
            best_distance = np.int64(-1)
            anchor_idx = first_hit_idx
            for member_pos in range(start, end):
                hit_idx = hit_index_all[member_pos]
                hit_start_ps = abs_start_ps[hit_idx]
                hit_end_ps = abs_end_ps[hit_idx]
                midpoint2 = hit_start_ps + hit_end_ps
                distance = midpoint2 - mid2
                if distance < 0:
                    distance = -distance
                if best_distance < 0 or distance < best_distance:
                    best_distance = distance
                    anchor_idx = hit_idx

            if not same_record:
                sample_start = -1
                sample_end = -1

            out_position[out_idx] = positions[anchor_idx]
            out_time_start[out_idx] = cluster_start_ps
            out_time_end[out_idx] = cluster_end_ps
            out_sample_start[out_idx] = sample_start
            out_sample_end[out_idx] = sample_end
            out_is_single_record[out_idx] = sample_start >= 0 and sample_end >= 0
            if sample_start < 0 or sample_end < 0:
                out_width[out_idx] = -1.0
            else:
                out_width[out_idx] = float(sample_end - sample_start)
            out_dt[out_idx] = dt_values[anchor_idx]
            out_timestamp[out_idx] = timestamps[anchor_idx]
            out_channel[out_idx] = channels[anchor_idx]
            out_record_id[out_idx] = record_ids[anchor_idx]
            out_component_offset[out_idx] = start
            out_component_count[out_idx] = end - start
            out_board[out_idx] = boards[anchor_idx]

else:

    _fill_multi_hit_clusters_numba = None


def _fill_multi_hit_clusters(
    multi_out: np.ndarray,
    starts: np.ndarray,
    ends: np.ndarray,
    hit_index_all: np.ndarray,
    abs_start_ps: np.ndarray,
    abs_end_ps: np.ndarray,
    positions: np.ndarray,
    sample_starts: np.ndarray,
    sample_ends: np.ndarray,
    record_ids: np.ndarray,
    dt_values: np.ndarray,
    timestamps: np.ndarray,
    channels: np.ndarray,
    boards: np.ndarray,
    out_position: np.ndarray,
    out_time_start: np.ndarray,
    out_time_end: np.ndarray,
    out_sample_start: np.ndarray,
    out_sample_end: np.ndarray,
    out_width: np.ndarray,
    out_dt: np.ndarray,
    out_timestamp: np.ndarray,
    out_channel: np.ndarray,
    out_record_id: np.ndarray,
    out_component_offset: np.ndarray,
    out_component_count: np.ndarray,
    out_is_single_record: np.ndarray,
    out_board: np.ndarray,
) -> bool:
    """Use the serial Numba kernel, falling back to the Python oracle.

    Returning whether the accelerated path ran makes the choice observable to
    direct benchmarks without changing the plugin output contract.
    """

    if len(multi_out) == 0:
        return False
    if _NUMBA_AVAILABLE and _fill_multi_hit_clusters_numba is not None:
        try:
            _fill_multi_hit_clusters_numba(
                multi_out,
                starts,
                ends,
                hit_index_all,
                abs_start_ps,
                abs_end_ps,
                positions,
                sample_starts,
                sample_ends,
                record_ids,
                dt_values,
                timestamps,
                channels,
                boards,
                out_position,
                out_time_start,
                out_time_end,
                out_sample_start,
                out_sample_end,
                out_width,
                out_dt,
                out_timestamp,
                out_channel,
                out_record_id,
                out_component_offset,
                out_component_count,
                out_is_single_record,
                out_board,
            )
            return True
        except Exception:
            # Keep an exact, dependency-free oracle for unsupported structured
            # field dtypes or a broken optional Numba installation.
            pass

    _fill_multi_hit_clusters_python(
        multi_out,
        starts,
        ends,
        hit_index_all,
        abs_start_ps,
        abs_end_ps,
        positions,
        sample_starts,
        sample_ends,
        record_ids,
        dt_values,
        timestamps,
        channels,
        boards,
        out_position,
        out_time_start,
        out_time_end,
        out_sample_start,
        out_sample_end,
        out_width,
        out_dt,
        out_timestamp,
        out_channel,
        out_record_id,
        out_component_offset,
        out_component_count,
        out_is_single_record,
        out_board,
    )
    return False


def _build_merged_from_cluster_rows(
    hits: np.ndarray,
    cluster_rows: np.ndarray,
    enriched: _EnrichedArrays,
) -> np.ndarray:
    """Build hit_merged output from cluster_rows and enriched arrays.

    Pre-allocates output array and fills in-place, avoiding list append + np.array conversion.
    """
    if len(cluster_rows) == 0:
        return np.zeros(0, dtype=HIT_MERGED_DTYPE)

    start_name, end_name = _resolve_sample_fields(hits.dtype)
    if start_name is None or end_name is None:
        raise ValueError("hit_merged requires sample start/end fields")

    starts, ends, counts = _cluster_bounds_arrays(cluster_rows)
    n_clusters = len(starts)
    if not np.array_equal(cluster_rows["cluster_index"][starts], np.arange(n_clusters)):
        raise ValueError("hit_merge_clusters rows are not ordered by cluster_index without gaps")

    merged = np.empty(n_clusters, dtype=HIT_MERGED_DTYPE)
    merged["merged_id"] = np.arange(n_clusters, dtype=np.int64)
    hit_index_all = cluster_rows["hit_index"]
    if np.any(hit_index_all < 0) or np.any(hit_index_all >= len(hits)):
        raise ValueError("hit_merge_clusters rows reference an invalid hit index")

    single_out = np.flatnonzero(counts == 1)
    if len(single_out) > 0:
        single_hit_idx = hit_index_all[starts[single_out]]

        merged["position"][single_out] = hits["position"][single_hit_idx]
        merged["sample_start"][single_out] = hits[start_name][single_hit_idx]
        merged["sample_end"][single_out] = hits[end_name][single_hit_idx]
        merged["width"][single_out] = hits["width"][single_hit_idx]
        merged["timestamp"][single_out] = hits["timestamp"][single_hit_idx]
        merged["channel"][single_out] = hits["channel"][single_hit_idx]
        merged["record_id"][single_out] = hits["record_id"][single_hit_idx]
        merged["component_offset"][single_out] = starts[single_out]
        merged["component_count"][single_out] = 1
        merged["is_single_record"][single_out] = True
        if "dt" in hits.dtype.names:
            merged["dt"][single_out] = hits["dt"][single_hit_idx]
        else:
            merged["dt"][single_out] = enriched.dt_ns[single_hit_idx]
        if "board" in hits.dtype.names:
            merged["board"][single_out] = hits["board"][single_hit_idx]
        else:
            merged["board"][single_out] = 0

        # 计算绝对时间（单 hit 情况）
        merged["time_start"][single_out] = enriched.abs_start_ps[single_hit_idx]
        merged["time_end"][single_out] = enriched.abs_end_ps[single_hit_idx]

    multi_out = np.flatnonzero(counts != 1).astype(np.int64, copy=False)
    if len(multi_out) > 0:
        if "dt" in hits.dtype.names:
            dt_values = hits["dt"]
        else:
            dt_values = enriched.dt_ns
        if "board" in hits.dtype.names:
            boards = hits["board"]
        else:
            boards = np.zeros(len(hits), dtype=np.int16)

        _fill_multi_hit_clusters(
            multi_out,
            starts,
            ends,
            hit_index_all,
            enriched.abs_start_ps,
            enriched.abs_end_ps,
            hits["position"],
            hits[start_name],
            hits[end_name],
            hits["record_id"],
            dt_values,
            hits["timestamp"],
            hits["channel"],
            boards,
            merged["position"],
            merged["time_start"],
            merged["time_end"],
            merged["sample_start"],
            merged["sample_end"],
            merged["width"],
            merged["dt"],
            merged["timestamp"],
            merged["channel"],
            merged["record_id"],
            merged["component_offset"],
            merged["component_count"],
            merged["is_single_record"],
            merged["board"],
        )

    return merged
