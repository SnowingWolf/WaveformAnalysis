"""Peaklet clustering, ragged waveforms, features, and final peaks."""

from typing import Any

import numpy as np

from waveform_analysis.core.plugins.builtin.cpu._dt_compat import resolve_dt_config
from waveform_analysis.core.plugins.builtin.cpu._record_utils import RecordLookup
from waveform_analysis.core.plugins.core.base import Option, Plugin
from waveform_analysis.core.plugins.core.batch_processing import BatchProcessingPlugin
from waveform_analysis.core.processing.chunk import Chunk

PEAKLET_DTYPE = np.dtype(
    [
        ("time_start", "i8"),
        ("time_end", "i8"),
        ("center_time", "i8"),
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

PEAKLET_WAVEFORMS_DTYPE = np.dtype(
    [
        ("peaklet_index", "i8"),
        ("time_start", "i8"),
        ("time_end", "i8"),
        ("dt", "i4"),
        ("wave_offset", "i8"),
        ("wave_length", "i4"),
    ]
)

PEAKLET_FEATURES_DTYPE = np.dtype(
    [
        ("peaklet_index", "i8"),
        ("time_left", "i8"),
        ("time_right", "i8"),
        ("time_peak", "i8"),
        ("center_time", "i8"),
        ("rise_time", "f4"),
        ("fall_time", "f4"),
        ("width_25_75", "f4"),
        ("range_50p_area", "f4"),
        ("range_90p_area", "f4"),
        ("area", "f4"),
        ("height", "f4"),
        ("width", "f4"),
    ]
)

PEAKS_DTYPE = np.dtype(
    [
        ("time_left", "i8"),
        ("time_right", "i8"),
        ("time_peak", "i8"),
        ("center_time", "i8"),
        ("rise_time", "f4"),
        ("fall_time", "f4"),
        ("width_25_75", "f4"),
        ("range_50p_area", "f4"),
        ("range_90p_area", "f4"),
        ("area", "f4"),
        ("height", "f4"),
        ("width", "f4"),
        ("n_hits", "i4"),
        ("n_channels", "i4"),
    ]
)


def _empty_peaklets() -> np.ndarray:
    return np.zeros(0, dtype=PEAKLET_DTYPE)


def _empty_components() -> np.ndarray:
    return np.zeros(0, dtype=PEAKLET_COMPONENTS_DTYPE)


def _empty_waveforms() -> np.ndarray:
    return np.zeros(0, dtype=PEAKLET_WAVEFORMS_DTYPE)


def _empty_waveform_pool() -> np.ndarray:
    return np.zeros(0, dtype=np.float32)


def _empty_features() -> np.ndarray:
    return np.zeros(0, dtype=PEAKLET_FEATURES_DTYPE)


def _empty_peaks() -> np.ndarray:
    return np.zeros(0, dtype=PEAKS_DTYPE)


def _compute_area_quantiles(
    wave: np.ndarray,
    time_start: int,
    dt_ns: int,
    quantiles: tuple[float, ...] = (0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95),
) -> dict[float, int]:
    """Return cumulative-area quantile times in ps for a baseline-corrected waveform."""
    if len(wave) == 0:
        return {q: time_start for q in quantiles}

    total_area = float(np.sum(wave, dtype=np.float64))
    if total_area <= 0:
        return {q: time_start for q in quantiles}

    cumsum = np.cumsum(wave, dtype=np.float64) / total_area
    dt_ps = int(dt_ns) * 1000

    result = {}
    for q in quantiles:
        idx = int(np.searchsorted(cumsum, q, side="left"))

        if idx >= len(cumsum):
            result[q] = int(time_start + (len(wave) - 1) * dt_ps)
            continue

        if idx == 0:
            i_interp = 0.0
        elif cumsum[idx] == q:
            i_interp = float(idx)
        else:
            c0 = cumsum[idx - 1] if idx > 0 else 0.0
            c1 = cumsum[idx]
            if c1 > c0:
                fraction = (q - c0) / (c1 - c0)
                i_interp = (idx - 1 if idx > 0 else 0) + fraction
            else:
                i_interp = float(idx)

        result[q] = int(time_start + i_interp * dt_ps)

    return result


def _record_array(obj: Any) -> np.ndarray:
    if isinstance(obj, np.ndarray):
        return obj
    if hasattr(obj, "records"):
        return np.asarray(obj.records)
    raise ValueError("peaklet waveform plugins expect records as a structured array")


def _wave_pool_array(obj: Any) -> np.ndarray:
    if obj is None:
        raise ValueError("peaklet waveform plugins require wave_pool or wave_pool_filtered")
    return np.asarray(obj)


def _field_or_default(row: np.void, name: str, default: int) -> int:
    return int(row[name]) if name in (row.dtype.names or ()) else int(default)


def _record_polarity(record: np.void) -> str:
    names = record.dtype.names or ()
    if "polarity" not in names:
        return "negative"
    value = record["polarity"]
    if isinstance(value, bytes):
        value = value.decode(errors="ignore")
    else:
        value = str(value)
    return value if value in {"positive", "negative"} else "negative"


def _hit_sample_window(row: np.void) -> tuple[int, int]:
    names = row.dtype.names or ()
    if {"sample_start", "sample_end"}.issubset(names):
        return int(row["sample_start"]), int(row["sample_end"])
    if {"edge_start", "edge_end"}.issubset(names):
        return int(row["edge_start"]), int(row["edge_end"])
    raise KeyError("peaklet inputs require sample_start/sample_end or edge_start/edge_end")


def _hit_abs_window(row: np.void) -> tuple[int, int]:
    sample_start, sample_end = _hit_sample_window(row)
    dt_ps = int(row["dt"]) * 1000
    timestamp = _field_or_default(row, "timestamp", 0)
    position = _field_or_default(row, "position", 0)
    return (
        timestamp + (sample_start - position) * dt_ps,
        timestamp + (sample_end - position) * dt_ps,
    )


def _abs_window(rows: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    starts = np.zeros(len(rows), dtype=np.float64)
    ends = np.zeros(len(rows), dtype=np.float64)
    for i, row in enumerate(rows):
        start, end = _hit_abs_window(row)
        starts[i] = start
        ends[i] = end
    return starts, ends


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
    gap_ps = time_window_ns * 1000.0
    max_width_ps = max_total_width_ns * 1000.0

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


def _components_by_peaklet(components: np.ndarray, n_peaklets: int) -> list[np.ndarray]:
    out: list[list[int]] = [[] for _ in range(n_peaklets)]
    for row in components:
        peaklet_index = int(row["peaklet_index"])
        if 0 <= peaklet_index < n_peaklets:
            out[peaklet_index].append(int(row["merged_index"]))
    return [np.asarray(rows, dtype=np.int64) for rows in out]


def _merged_wave_piece(
    *,
    hit: np.void,
    records: np.ndarray,
    record_lookup: RecordLookup,
    wave_pool: np.ndarray,
) -> tuple[int, int, int, np.ndarray]:
    record = record_lookup.get(int(hit["record_id"]))
    names = record.dtype.names or ()
    start, end = _hit_sample_window(hit)
    length = int(record["event_length"])
    start = max(0, start)
    end = min(length, end)
    if end <= start:
        return (
            0,
            0,
            int(record["dt"]) if "dt" in names else int(hit["dt"]),
            np.zeros(0, dtype=np.float32),
        )

    dt_ns = int(record["dt"]) if "dt" in names else int(hit["dt"])
    dt_ps = dt_ns * 1000
    timestamp = (
        int(record["timestamp"]) if "timestamp" in names else _field_or_default(hit, "timestamp", 0)
    )
    time_start = timestamp + start * dt_ps
    time_end = timestamp + end * dt_ps

    offset = int(record["wave_offset"])
    baseline = float(record["baseline"]) if "baseline" in names else 0.0
    raw = wave_pool[offset + start : offset + end].astype(np.float32, copy=False)
    if _record_polarity(record) == "positive":
        signal = raw - np.float32(baseline)
    else:
        signal = np.float32(baseline) - raw
    return time_start, time_end, dt_ns, np.maximum(signal, 0.0).astype(np.float32, copy=False)


class PeakletPlugin(BatchProcessingPlugin):
    """Build lightweight cross-channel peaklet candidates from hit_merged rows."""

    provides = "peaklets"
    depends_on = ["hit_merged"]
    description = "Build lightweight cross-channel peaklets from hit_merged intervals."
    version = "1.0.0"
    output_dtype = PEAKLET_DTYPE
    save_when = "always"
    parallel = False

    options = {
        "time_window_ns": Option(default=100.0, type=float, help="跨通道 peaklet 合并时间窗口"),
        "max_total_width_ns": Option(default=10000.0, type=float, help="peaklet 最大总宽度"),
        "dt": Option(default=None, type=int, help="保留兼容配置；优先使用输入 hit_merged 的 dt"),
    }

    def compute(self, context: Any, run_id: str, **kwargs) -> np.ndarray:
        return self.compute_array(context, run_id, **kwargs)

    def compute_array(self, context: Any, run_id: str, **_kwargs) -> np.ndarray:
        merged = context.get_data(run_id, "hit_merged")
        if not isinstance(merged, np.ndarray):
            raise ValueError("peaklets expects hit_merged as a structured array")
        if len(merged) == 0:
            return _empty_peaklets()

        return self._compute_peaklets(merged=merged, context=context)

    def compute_chunk(self, chunk: Chunk, context: Any, run_id: str, **kwargs) -> Chunk:
        peaklets = self._compute_peaklets(merged=chunk.data, context=context)
        return Chunk(
            data=peaklets,
            start=chunk.start,
            end=chunk.end,
            run_id=run_id,
            data_type=self.provides,
        )

    def _compute_peaklets(self, *, merged: np.ndarray, context: Any) -> np.ndarray:
        time_window_ns = float(context.get_config(self, "time_window_ns"))
        max_total_width_ns = float(context.get_config(self, "max_total_width_ns"))
        resolve_dt_config(context, self, deprecated_keys=("sampling_interval_ns", "dt_ns"))
        clusters = _cluster_merged_hits(
            merged,
            time_window_ns=time_window_ns,
            max_total_width_ns=max_total_width_ns,
        )

        rows: list[tuple[int, int, int, int, int, int, int]] = []
        component_offset = 0
        for cluster in clusters:
            cluster_indices = np.asarray(cluster, dtype=np.int64)
            cluster_rows = merged[cluster_indices]
            starts, ends = _abs_window(cluster_rows)
            time_start = int(np.min(starts))
            time_end = int(np.max(ends))
            channels = {
                (
                    int(row["board"]) if "board" in (row.dtype.names or ()) else 0,
                    int(row["channel"]),
                )
                for row in cluster_rows
            }
            n_hits = (
                int(np.sum(cluster_rows["component_count"], dtype=np.int64))
                if "component_count" in (merged.dtype.names or ())
                else len(cluster)
            )
            rows.append(
                (
                    time_start,
                    time_end,
                    int((time_start + time_end) // 2),
                    n_hits,
                    len(channels),
                    component_offset,
                    len(cluster),
                )
            )
            component_offset += len(cluster)

        return np.array(rows, dtype=PEAKLET_DTYPE) if rows else _empty_peaklets()


class PeakletComponentsPlugin(BatchProcessingPlugin):
    """Return flat peaklet-to-hit_merged membership rows."""

    provides = "peaklet_components"
    depends_on = ["peaklets", "hit_merged"]
    description = "Return per-peaklet component hit_merged indices."
    version = "1.0.0"
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
        return np.array(rows, dtype=PEAKLET_COMPONENTS_DTYPE) if rows else _empty_components()

    def compute_chunk(self, chunk: Chunk, context: Any, run_id: str, **kwargs) -> Chunk:
        components = self.compute_array(context, run_id, **kwargs)
        return Chunk(
            data=components,
            start=chunk.start,
            end=chunk.end,
            run_id=run_id,
            data_type=self.provides,
        )


class PeakletWaveformPlugin(Plugin):
    """Build ragged waveform index rows for peaklets and cache the signal pool."""

    provides = "peaklet_waveforms"
    depends_on = []  # 使用 resolve_depends_on() 动态解析
    description = "Build peaklet waveform index rows from records-backed hit_merged samples."
    version = "1.0.0"
    output_dtype = PEAKLET_WAVEFORMS_DTYPE
    save_when = "always"

    options = {
        "use_filtered": Option(
            default=False, type=bool, help="是否使用 wave_pool_filtered 构建 peaklet 波形"
        ),
    }

    def resolve_depends_on(self, context: Any, run_id: str | None = None) -> list[str]:
        deps = ["peaklets", "peaklet_components", "hit_merged", "records"]
        deps.append(
            "wave_pool_filtered" if bool(context.get_config(self, "use_filtered")) else "wave_pool"
        )
        return deps

    def compute(self, context: Any, run_id: str, **_kwargs) -> np.ndarray:
        waveforms, pool = self._compute_waveforms_and_pool(context, run_id)
        self._store_pool(context, run_id, pool)
        return waveforms

    def _store_pool(self, context: Any, run_id: str, pool: np.ndarray) -> None:
        data = getattr(context, "_data", None)
        if isinstance(data, dict):
            data["peaklet_waveform_pool"] = pool

    def _compute_waveforms_and_pool(
        self, context: Any, run_id: str
    ) -> tuple[np.ndarray, np.ndarray]:
        peaklets = context.get_data(run_id, "peaklets")
        if not isinstance(peaklets, np.ndarray):
            raise ValueError("peaklet_waveforms expects peaklets as a structured array")
        if len(peaklets) == 0:
            return _empty_waveforms(), _empty_waveform_pool()

        components = context.get_data(run_id, "peaklet_components")
        if not isinstance(components, np.ndarray):
            raise ValueError("peaklet_waveforms expects peaklet_components as a structured array")
        merged = context.get_data(run_id, "hit_merged")
        if not isinstance(merged, np.ndarray):
            raise ValueError("peaklet_waveforms expects hit_merged as a structured array")
        records = _record_array(context.get_data(run_id, "records"))
        wave_pool_name = (
            "wave_pool_filtered" if bool(context.get_config(self, "use_filtered")) else "wave_pool"
        )
        wave_pool = _wave_pool_array(context.get_data(run_id, wave_pool_name))

        return self._build(
            peaklets=peaklets,
            components=components,
            merged=merged,
            records=records,
            wave_pool=wave_pool,
        )

    def _build(
        self,
        *,
        peaklets: np.ndarray,
        components: np.ndarray,
        merged: np.ndarray,
        records: np.ndarray,
        wave_pool: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray]:
        record_lookup = RecordLookup(records)
        component_groups = _components_by_peaklet(components, len(peaklets))
        rows: list[tuple[int, int, int, int, int, int]] = []
        pools: list[np.ndarray] = []
        wave_offset = 0

        for peaklet_index, merged_indices in enumerate(component_groups):
            if len(merged_indices) == 0:
                rows.append((peaklet_index, 0, 0, 0, wave_offset, 0))
                continue

            pieces: list[tuple[int, int, np.ndarray]] = []
            dt_ns: int | None = None
            time_start: int | None = None
            time_end: int | None = None

            for merged_index in merged_indices:
                hit = merged[int(merged_index)]
                start, end, piece_dt_ns, signal = _merged_wave_piece(
                    hit=hit,
                    records=records,
                    record_lookup=record_lookup,
                    wave_pool=wave_pool,
                )
                if len(signal) == 0:
                    continue
                if dt_ns is None:
                    dt_ns = piece_dt_ns
                elif piece_dt_ns != dt_ns:
                    raise ValueError(
                        f"peaklet_waveforms does not support mixed dt in peaklet_index={peaklet_index}"
                    )
                pieces.append((start, end, signal))
                time_start = start if time_start is None else min(time_start, start)
                time_end = end if time_end is None else max(time_end, end)

            if not pieces or dt_ns is None or time_start is None or time_end is None:
                rows.append((peaklet_index, 0, 0, 0, wave_offset, 0))
                continue

            dt_ps = dt_ns * 1000
            wave_length = int((time_end - time_start) // dt_ps)
            summed = np.zeros(wave_length, dtype=np.float32)
            for start, _end, signal in pieces:
                i0 = int((start - time_start) // dt_ps)
                summed[i0 : i0 + len(signal)] += signal

            rows.append((peaklet_index, time_start, time_end, dt_ns, wave_offset, wave_length))
            pools.append(summed)
            wave_offset += wave_length

        pool = (
            np.concatenate(pools).astype(np.float32, copy=False)
            if pools
            else _empty_waveform_pool()
        )
        return np.array(rows, dtype=PEAKLET_WAVEFORMS_DTYPE) if rows else _empty_waveforms(), pool


class PeakletWaveformPoolPlugin(Plugin):
    """Return the flattened peaklet waveform signal pool."""

    provides = "peaklet_waveform_pool"
    depends_on = []  # 使用 resolve_depends_on() 动态解析
    description = "Return flattened float32 peaklet waveform signal pool."
    version = "1.0.0"
    output_dtype = np.dtype("f4")
    save_when = "always"

    options = PeakletWaveformPlugin.options

    def resolve_depends_on(self, context: Any, run_id: str | None = None) -> list[str]:
        return PeakletWaveformPlugin().resolve_depends_on(context, run_id)

    def compute(self, context: Any, run_id: str, **_kwargs) -> np.ndarray:
        data = getattr(context, "_data", None)
        if isinstance(data, dict) and "peaklet_waveform_pool" in data:
            return np.asarray(data["peaklet_waveform_pool"], dtype=np.float32)
        waveforms, pool = PeakletWaveformPlugin()._compute_waveforms_and_pool(context, run_id)
        if isinstance(data, dict):
            data["peaklet_waveforms"] = waveforms
            data["peaklet_waveform_pool"] = pool
        return pool


class PeakletFeaturesPlugin(Plugin):
    """Compute waveform-derived features from ragged peaklet waveforms."""

    provides = "peaklet_features"
    depends_on = ["peaklet_waveforms", "peaklet_waveform_pool", "peaklets"]
    description = "Compute peaklet waveform features from ragged signal pools."
    version = "3.0.0"
    output_dtype = PEAKLET_FEATURES_DTYPE
    save_when = "always"

    def compute(self, context: Any, run_id: str, **_kwargs) -> np.ndarray:
        waveforms = context.get_data(run_id, "peaklet_waveforms")
        if not isinstance(waveforms, np.ndarray):
            raise ValueError("peaklet_features expects peaklet_waveforms as a structured array")
        if len(waveforms) == 0:
            return _empty_features()
        pool = context.get_data(run_id, "peaklet_waveform_pool")
        if not isinstance(pool, np.ndarray):
            raise ValueError("peaklet_features expects peaklet_waveform_pool as a numpy array")
        peaklets = context.get_data(run_id, "peaklets")
        if not isinstance(peaklets, np.ndarray):
            raise ValueError("peaklet_features expects peaklets as a structured array")

        rows: list[
            tuple[int, int, int, int, int, float, float, float, float, float, float, float, float]
        ] = []
        for row in waveforms:
            peaklet_index = int(row["peaklet_index"])
            offset = int(row["wave_offset"])
            length = int(row["wave_length"])
            time_left = int(row["time_start"])
            time_right = int(row["time_end"])
            dt_ns = int(row["dt"])

            if length <= 0:
                rows.append(
                    (
                        peaklet_index,
                        time_left,
                        time_right,
                        time_left,
                        time_left,
                        0.0,  # rise_time
                        0.0,  # fall_time
                        0.0,  # width_25_75
                        0.0,  # range_50p_area
                        0.0,  # range_90p_area
                        0.0,  # area
                        0.0,  # height
                        0.0,  # width
                    )
                )
                continue

            wave = pool[offset : offset + length].astype(np.float32, copy=False)
            if len(wave) != length:
                raise ValueError("peaklet_features found out-of-bounds waveform slice")

            quantiles = _compute_area_quantiles(wave, time_left, dt_ns)
            t05 = quantiles[0.05]
            t10 = quantiles[0.10]
            t25 = quantiles[0.25]
            t50 = quantiles[0.50]
            t75 = quantiles[0.75]
            t90 = quantiles[0.90]
            t95 = quantiles[0.95]

            max_idx = int(np.argmax(wave))
            time_peak = int(time_left + max_idx * dt_ns * 1000)

            rise_time = float((time_peak - t10) / 1000.0)
            fall_time = float((t90 - time_peak) / 1000.0)
            width_25_75 = float((t75 - t25) / 1000.0)
            range_50p_area = float((t75 - t25) / 1000.0)
            range_90p_area = float((t95 - t05) / 1000.0)

            area = float(np.sum(wave, dtype=np.float64))
            height = float(wave[max_idx])
            width = float((time_right - time_left) / 1000.0)

            rows.append(
                (
                    peaklet_index,
                    time_left,
                    time_right,
                    time_peak,
                    t50,
                    rise_time,
                    fall_time,
                    width_25_75,
                    range_50p_area,
                    range_90p_area,
                    area,
                    height,
                    width,
                )
            )

        return np.array(rows, dtype=PEAKLET_FEATURES_DTYPE) if rows else _empty_features()


class PeaksPlugin(Plugin):
    """Build the final user-facing peaks table from peaklet metadata and features."""

    provides = "peaks"
    depends_on = ["peaklets", "peaklet_features", "peaklet_channels"]
    description = "Build final peaks table from peaklets and waveform-derived features."
    version = "3.0.0"
    output_dtype = PEAKS_DTYPE
    save_when = "always"

    def compute(self, context: Any, run_id: str, **_kwargs) -> np.ndarray:
        peaklets = context.get_data(run_id, "peaklets")
        if not isinstance(peaklets, np.ndarray):
            raise ValueError("peaks expects peaklets as a structured array")
        if len(peaklets) == 0:
            return _empty_peaks()
        features = context.get_data(run_id, "peaklet_features")
        if not isinstance(features, np.ndarray):
            raise ValueError("peaks expects peaklet_features as a structured array")

        features_by_peaklet = {int(row["peaklet_index"]): row for row in features}
        rows: list[tuple] = []
        for peaklet_index, peaklet in enumerate(peaklets):
            feature = features_by_peaklet.get(peaklet_index)
            if feature is None:
                raise ValueError(
                    f"peaks could not resolve peaklet_features for peaklet_index={peaklet_index}"
                )
            rows.append(
                (
                    int(feature["time_left"]),
                    int(feature["time_right"]),
                    int(feature["time_peak"]),
                    int(feature["center_time"]),
                    float(feature["rise_time"]),
                    float(feature["fall_time"]),
                    float(feature["width_25_75"]),
                    float(feature["range_50p_area"]),
                    float(feature["range_90p_area"]),
                    float(feature["area"]),
                    float(feature["height"]),
                    float(feature["width"]),
                    int(peaklet["n_hits"]),
                    int(peaklet["n_channels"]),
                )
            )

        return np.array(rows, dtype=PEAKS_DTYPE) if rows else _empty_peaks()


__all__ = [
    "PEAKLET_COMPONENTS_DTYPE",
    "PEAKLET_DTYPE",
    "PEAKLET_FEATURES_DTYPE",
    "PEAKLET_WAVEFORMS_DTYPE",
    "PEAKS_DTYPE",
    "PeakletComponentsPlugin",
    "PeakletFeaturesPlugin",
    "PeakletPlugin",
    "PeakletWaveformPlugin",
    "PeakletWaveformPoolPlugin",
    "PeaksPlugin",
]
