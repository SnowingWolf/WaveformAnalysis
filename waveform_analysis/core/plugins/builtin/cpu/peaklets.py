"""
Peaklet Plugin - 跨通道局部脉冲候选构建与特征计算。
"""

from typing import Any

import numpy as np

from waveform_analysis.core.plugins.builtin.cpu._dt_compat import resolve_dt_config
from waveform_analysis.core.plugins.builtin.cpu.hit_finder import THRESHOLD_HIT_DTYPE
from waveform_analysis.core.plugins.builtin.cpu.hit_merge import (
    HIT_MERGED_COMPONENTS_DTYPE,
    HIT_MERGED_DTYPE,
)
from waveform_analysis.core.plugins.core.base import Option
from waveform_analysis.core.plugins.core.batch_processing import BatchProcessingPlugin
from waveform_analysis.core.processing.chunk import Chunk

PEAKLET_DTYPE = np.dtype(
    [
        ("time_start", "i8"),
        ("time_end", "i8"),
        ("center_time", "i8"),
        ("max_time", "i8"),
        ("area", "f4"),
        ("height", "f4"),
        ("width", "f4"),
        ("rise_time", "f4"),
        ("fall_time", "f4"),
        ("n_hits", "i4"),
        ("n_channels", "i4"),
        ("component_offset", "i8"),
        ("component_count", "i4"),
    ]
)

PEAKLET_COMPONENTS_DTYPE = np.dtype(
    [
        ("peaklet_index", "i8"),
        ("merged_index", "i8"),
    ]
)


def _empty_peaklets() -> np.ndarray:
    return np.zeros(0, dtype=PEAKLET_DTYPE)


def _empty_components() -> np.ndarray:
    return np.zeros(0, dtype=PEAKLET_COMPONENTS_DTYPE)


def _record_array(obj: Any) -> np.ndarray:
    if isinstance(obj, np.ndarray):
        return obj
    if hasattr(obj, "records"):
        return np.asarray(obj.records)
    raise ValueError("peaklets expects records as a structured array or RecordsView-like object")


def _wave_pool_array(obj: Any) -> np.ndarray:
    if obj is None:
        raise ValueError("peaklets requires wave_pool or wave_pool_filtered")
    return np.asarray(obj)


def _record_lookup(records: np.ndarray) -> dict[int, np.void]:
    names = records.dtype.names or ()
    if "record_id" in names:
        return {int(rec["record_id"]): rec for rec in records}
    return dict(enumerate(records))


def _abs_window(rows: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    names = rows.dtype.names or ()
    if {"sample_start", "sample_end"}.issubset(names):
        start_name = "sample_start"
        end_name = "sample_end"
    elif {"edge_start", "edge_end"}.issubset(names):
        start_name = "edge_start"
        end_name = "edge_end"
    else:
        raise KeyError("peaklets input rows require sample_start/sample_end or edge_start/edge_end")

    dt_ps = np.asarray(rows["dt"], dtype=np.float64) * 1e3
    timestamps = np.asarray(rows["timestamp"], dtype=np.float64)
    positions = np.asarray(rows["position"], dtype=np.float64)
    starts = np.asarray(rows[start_name], dtype=np.float64)
    ends = np.asarray(rows[end_name], dtype=np.float64)
    return timestamps + (starts - positions) * dt_ps, timestamps + (ends - positions) * dt_ps


def _cluster_merged_hits(
    merged: np.ndarray,
    time_window_ns: float,
    max_total_width_ns: float,
) -> list[list[int]]:
    if len(merged) == 0:
        return []
    if time_window_ns < 0:
        raise ValueError("peaklets.time_window_ns must be >= 0")
    if max_total_width_ns <= 0:
        raise ValueError("peaklets.max_total_width_ns must be > 0")

    abs_starts, abs_ends = _abs_window(merged)
    order = np.argsort(abs_starts, kind="mergesort")
    gap_ps = time_window_ns * 1e3
    max_width_ps = max_total_width_ns * 1e3

    clusters: list[list[int]] = []
    current = [int(order[0])]
    cluster_start = float(abs_starts[order[0]])
    cluster_end = float(abs_ends[order[0]])

    for raw_idx in order[1:]:
        idx = int(raw_idx)
        next_end = max(cluster_end, float(abs_ends[idx]))
        total_width = next_end - cluster_start
        if abs_starts[idx] <= cluster_end + gap_ps and total_width <= max_width_ps:
            current.append(idx)
            cluster_end = next_end
        else:
            clusters.append(current)
            current = [idx]
            cluster_start = float(abs_starts[idx])
            cluster_end = float(abs_ends[idx])

    clusters.append(current)
    return clusters


def _component_hit_indices(
    merged_indices: list[int],
    merged: np.ndarray,
    component_rows: np.ndarray | None,
) -> np.ndarray:
    names = merged.dtype.names or ()
    if component_rows is None or len(component_rows) == 0:
        return np.asarray(merged_indices, dtype=np.int64)

    hit_indices = np.asarray(component_rows["hit_index"], dtype=np.int64)
    if {"component_offset", "component_count"}.issubset(names):
        out: list[int] = []
        for merged_idx in merged_indices:
            offset = int(merged[merged_idx]["component_offset"])
            count = int(merged[merged_idx]["component_count"])
            out.extend(hit_indices[offset : offset + count].tolist())
        return np.asarray(out, dtype=np.int64)

    merged_row_indices = np.asarray(component_rows["merged_index"], dtype=np.int64)
    mask = np.isin(merged_row_indices, np.asarray(merged_indices, dtype=np.int64))
    return hit_indices[mask].astype(np.int64, copy=False)


def _record_polarity(record: np.void) -> str:
    names = record.dtype.names or ()
    if "polarity" not in names:
        return "negative"
    value = str(record["polarity"])
    return value if value in {"positive", "negative"} else "negative"


def _compute_cluster_features(
    component_hits: np.ndarray,
    records_by_id: dict[int, np.void],
    wave_pool: np.ndarray,
) -> tuple[int, int, int, int, float, float, float, float, float, int, int]:
    abs_starts, abs_ends = _abs_window(component_hits)
    time_start = int(np.min(abs_starts))
    time_end = int(np.max(abs_ends))
    center_time = int((time_start + time_end) // 2)
    width_ns = float((time_end - time_start) / 1e3)

    waveform_by_time: dict[int, float] = {}
    channel_keys: set[tuple[int, int]] = set()
    area = 0.0

    for hit in component_hits:
        record_id = int(hit["record_id"])
        if record_id not in records_by_id:
            raise ValueError(f"peaklets could not resolve record_id={record_id}")
        record = records_by_id[record_id]
        names = record.dtype.names or ()
        offset = int(record["wave_offset"])
        length = int(record["event_length"])
        baseline = float(record["baseline"]) if "baseline" in names else 0.0
        dt_ns = int(record["dt"]) if "dt" in names else int(hit["dt"])
        timestamp = int(record["timestamp"]) if "timestamp" in names else 0
        edge_start = max(0, int(hit["edge_start"]))
        edge_end = min(length, int(hit["edge_end"]))
        if edge_end <= edge_start:
            continue

        raw = wave_pool[offset + edge_start : offset + edge_end].astype(np.float32, copy=False)
        if _record_polarity(record) == "positive":
            signal = raw - np.float32(baseline)
        else:
            signal = np.float32(baseline) - raw
        signal = np.maximum(signal, 0.0)

        board = int(hit["board"]) if "board" in hit.dtype.names else 0
        channel = int(hit["channel"])
        channel_keys.add((board, channel))
        for rel_idx, value in enumerate(signal.tolist()):
            sample = edge_start + rel_idx
            sample_time = int(timestamp + sample * dt_ns * 1000)
            waveform_by_time[sample_time] = waveform_by_time.get(sample_time, 0.0) + float(value)
            area += float(value)

    if waveform_by_time:
        times = np.fromiter(waveform_by_time.keys(), dtype=np.int64)
        values = np.fromiter(waveform_by_time.values(), dtype=np.float32)
        max_idx = int(np.argmax(values))
        max_time = int(times[max_idx])
        height = float(values[max_idx])
    else:
        max_time = center_time
        height = 0.0

    rise_time = float((max_time - time_start) / 1e3)
    fall_time = float((time_end - max_time) / 1e3)
    return (
        time_start,
        time_end,
        center_time,
        max_time,
        float(area),
        height,
        width_ns,
        rise_time,
        fall_time,
        int(len(component_hits)),
        int(len(channel_keys)),
    )


class PeakletPlugin(BatchProcessingPlugin):
    """Build cross-channel local pulse candidates from merged hit intervals."""

    provides = "peaklets"
    depends_on = ["hit_merged", "hit_merged_components", "hit_threshold", "records", "wave_pool"]
    description = "Build cross-channel peaklets and compute pulse-level features."
    version = "0.1.0"
    output_dtype = PEAKLET_DTYPE
    save_when = "always"
    parallel = False

    options = {
        "time_window_ns": Option(default=100.0, type=float, help="跨通道 peaklet 合并时间窗口"),
        "max_total_width_ns": Option(default=10000.0, type=float, help="peaklet 最大总宽度"),
        "use_filtered": Option(
            default=False, type=bool, help="是否使用 wave_pool_filtered 计算特征"
        ),
        "dt": Option(default=None, type=int, help="保留兼容配置；特征优先使用 records/hits 的 dt"),
    }

    def resolve_depends_on(self, context: Any, run_id: str | None = None) -> list[str]:
        deps = ["hit_merged", "hit_merged_components", "hit_threshold", "records"]
        if bool(context.get_config(self, "use_filtered")):
            deps.append("wave_pool_filtered")
        else:
            deps.append("wave_pool")
        return deps

    def compute(self, context: Any, run_id: str, **kwargs) -> np.ndarray:
        return self.compute_array(context, run_id, **kwargs)

    def compute_array(self, context: Any, run_id: str, **_kwargs) -> np.ndarray:
        merged = context.get_data(run_id, "hit_merged")
        if not isinstance(merged, np.ndarray):
            raise ValueError("peaklets expects hit_merged as a structured array")
        if len(merged) == 0:
            return _empty_peaklets()

        component_rows = context.get_data(run_id, "hit_merged_components")
        if component_rows is not None and not isinstance(component_rows, np.ndarray):
            raise ValueError("peaklets expects hit_merged_components as a structured array")

        hits = context.get_data(run_id, "hit_threshold")
        if not isinstance(hits, np.ndarray):
            raise ValueError("peaklets expects hit_threshold as a structured array")

        records = _record_array(context.get_data(run_id, "records"))
        wave_pool_name = (
            "wave_pool_filtered" if bool(context.get_config(self, "use_filtered")) else "wave_pool"
        )
        wave_pool = _wave_pool_array(context.get_data(run_id, wave_pool_name))

        return self._compute_peaklets(
            merged=merged,
            component_rows=component_rows,
            hits=hits,
            records=records,
            wave_pool=wave_pool,
            context=context,
            run_id=run_id,
        )

    def compute_chunk(self, chunk: Chunk, context: Any, run_id: str, **kwargs) -> Chunk:
        data = chunk.data
        context_data = getattr(context, "_data", {})
        local_context = context
        if isinstance(context_data, dict):
            old = context_data.get("hit_merged")
            context_data["hit_merged"] = data
            try:
                peaklets = self.compute_array(local_context, run_id, **kwargs)
            finally:
                if old is None:
                    context_data.pop("hit_merged", None)
                else:
                    context_data["hit_merged"] = old
        else:
            peaklets = _empty_peaklets()
        return Chunk(
            data=peaklets, start=chunk.start, end=chunk.end, run_id=run_id, data_type=self.provides
        )

    def _compute_peaklets(
        self,
        *,
        merged: np.ndarray,
        component_rows: np.ndarray | None,
        hits: np.ndarray,
        records: np.ndarray,
        wave_pool: np.ndarray,
        context: Any,
        run_id: str,
    ) -> np.ndarray:
        time_window_ns = float(context.get_config(self, "time_window_ns"))
        max_total_width_ns = float(context.get_config(self, "max_total_width_ns"))
        resolve_dt_config(context, self, deprecated_keys=("sampling_interval_ns", "dt_ns"))

        clusters = _cluster_merged_hits(
            merged,
            time_window_ns=time_window_ns,
            max_total_width_ns=max_total_width_ns,
        )
        records_by_id = _record_lookup(records)

        rows: list[tuple] = []
        component_offset = 0
        for cluster in clusters:
            hit_indices = _component_hit_indices(cluster, merged, component_rows)
            component_hits = hits[hit_indices]
            features = _compute_cluster_features(component_hits, records_by_id, wave_pool)
            rows.append((*features, component_offset, len(cluster)))
            component_offset += len(cluster)

        if rows:
            return np.array(rows, dtype=PEAKLET_DTYPE)
        return _empty_peaklets()


class PeakletComponentsPlugin(BatchProcessingPlugin):
    """Return flat peaklet-to-hit_merged membership rows."""

    provides = "peaklet_components"
    depends_on = ["peaklets", "hit_merged"]
    description = "Return per-peaklet component hit_merged indices."
    version = "0.1.0"
    output_dtype = PEAKLET_COMPONENTS_DTYPE
    save_when = "always"
    parallel = False

    options = PeakletPlugin.options

    def compute(self, context: Any, run_id: str, **kwargs) -> np.ndarray:
        return self.compute_array(context, run_id, **kwargs)

    def compute_array(self, context: Any, run_id: str, **_kwargs) -> np.ndarray:
        merged = context.get_data(run_id, "hit_merged")
        if not isinstance(merged, np.ndarray):
            raise ValueError("peaklet_components expects hit_merged as a structured array")
        if len(merged) == 0:
            return _empty_components()

        time_window_ns = float(context.get_config(self, "time_window_ns"))
        max_total_width_ns = float(context.get_config(self, "max_total_width_ns"))
        clusters = _cluster_merged_hits(
            merged,
            time_window_ns=time_window_ns,
            max_total_width_ns=max_total_width_ns,
        )
        rows: list[tuple[int, int]] = []
        for peaklet_index, cluster in enumerate(clusters):
            rows.extend((peaklet_index, merged_index) for merged_index in cluster)
        if rows:
            return np.array(rows, dtype=PEAKLET_COMPONENTS_DTYPE)
        return _empty_components()

    def compute_chunk(self, chunk: Chunk, context: Any, run_id: str, **kwargs) -> Chunk:
        components = self.compute_array(context, run_id, **kwargs)
        return Chunk(
            data=components,
            start=chunk.start,
            end=chunk.end,
            run_id=run_id,
            data_type=self.provides,
        )


__all__ = [
    "PEAKLET_COMPONENTS_DTYPE",
    "PEAKLET_DTYPE",
    "PeakletComponentsPlugin",
    "PeakletPlugin",
]
