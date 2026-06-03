"""Per-channel waveform features for hit_merged rows."""

from typing import Any

import numpy as np

from waveform_analysis.core.plugins.builtin.cpu._dt_compat import resolve_dt_config
from waveform_analysis.core.plugins.builtin.cpu._wave_source import (
    WAVE_SOURCE_RECORDS,
    load_wave_input,
    resolve_wave_input_spec,
)
from waveform_analysis.core.plugins.core.base import Option, Plugin

HIT_MERGED_FEATURES_DTYPE = np.dtype(
    [
        ("merged_index", "i8"),
        ("board", "i2"),
        ("channel", "i2"),
        ("record_id", "i8"),
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
        ("valid", "i1"),
    ]
)


def _empty_features() -> np.ndarray:
    return np.zeros(0, dtype=HIT_MERGED_FEATURES_DTYPE)


def _record_lookup(records: np.ndarray) -> dict[int, np.void]:
    names = records.dtype.names or ()
    if "record_id" in names:
        return {int(rec["record_id"]): rec for rec in records}
    return dict(enumerate(records))


def _record_polarity(record: np.void) -> str:
    names = record.dtype.names or ()
    if "polarity" not in names:
        return "negative"
    value = str(record["polarity"])
    return value if value in {"positive", "negative"} else "negative"


def _sample_times(row: np.void, start: int, end: int) -> tuple[int, int, int]:
    dt_ns = int(row["dt"]) if "dt" in row.dtype.names else 1
    timestamp = int(row["timestamp"])
    position = int(row["position"])
    dt_ps = dt_ns * 1000
    time_start = int(timestamp + (start - position) * dt_ps)
    time_end = int(timestamp + (end - position) * dt_ps)
    return time_start, time_end, dt_ps


def _window_signal(
    *,
    record: np.void,
    wave_pool: np.ndarray,
    start: int,
    end: int,
    data_name: str,
) -> np.ndarray:
    names = record.dtype.names or ()
    offset = int(record["wave_offset"])
    length = int(record["event_length"])
    clipped_start = max(0, start)
    clipped_end = min(length, end)
    if clipped_end <= clipped_start:
        record_id = int(record["record_id"]) if "record_id" in names else -1
        raise ValueError(
            f"{data_name} could not integrate record_id={record_id}: empty sample window "
            f"[{start}, {end}) after clipping to event_length={length}"
        )

    baseline = float(record["baseline"]) if "baseline" in names else 0.0
    raw = wave_pool[offset + clipped_start : offset + clipped_end].astype(np.float32, copy=False)
    if _record_polarity(record) == "positive":
        signal = raw - np.float32(baseline)
    else:
        signal = np.float32(baseline) - raw
    return np.maximum(signal, 0.0)


def _window_feature_values(
    *,
    source_row: np.void,
    record: np.void,
    wave_pool: np.ndarray,
    start: int,
    end: int,
    data_name: str,
) -> tuple[int, int, float, float, int]:
    signal = _window_signal(
        record=record,
        wave_pool=wave_pool,
        start=start,
        end=end,
        data_name=data_name,
    )
    time_start, time_end, dt_ps = _sample_times(source_row, start, end)
    max_idx = int(np.argmax(signal))
    max_time = int(time_start + max_idx * dt_ps)
    return time_start, time_end, float(np.sum(signal)), float(signal[max_idx]), max_time


class HitMergedFeaturesPlugin(Plugin):
    """Compute local single-channel waveform features for every hit_merged row."""

    provides = "hit_merged_features"
    depends_on = ["hit_merged", "hit_merged_components", "hit_threshold", "records", "wave_pool"]
    description = "Compute per-hit_merged local waveform features from records-backed samples."
    version = "0.1.0"
    save_when = "always"
    output_dtype = HIT_MERGED_FEATURES_DTYPE

    options = {
        "wave_source": Option(
            default=WAVE_SOURCE_RECORDS,
            type=str,
            help="波形来源。hit_merged_features 当前正式支持 records。",
        ),
        "use_filtered": Option(
            default=False,
            type=bool,
            help="是否使用 wave_pool_filtered 计算局部特征。",
        ),
        "dt": Option(default=None, type=int, help="保留兼容配置；特征优先使用 records/hits 的 dt"),
    }

    def resolve_depends_on(self, context: Any, run_id: str | None = None) -> list[str]:
        spec = resolve_wave_input_spec(context, self)
        if not spec.is_records:
            raise ValueError("hit_merged_features currently supports wave_source='records' only")
        return ["hit_merged", "hit_merged_components", "hit_threshold", *spec.depends_on]

    def compute(self, context: Any, run_id: str, **_kwargs) -> np.ndarray:
        merged = context.get_data(run_id, "hit_merged")
        if not isinstance(merged, np.ndarray):
            raise ValueError("hit_merged_features expects hit_merged as a structured array")
        if len(merged) == 0:
            return _empty_features()

        component_rows = context.get_data(run_id, "hit_merged_components")
        if not isinstance(component_rows, np.ndarray):
            raise ValueError(
                "hit_merged_features expects hit_merged_components as a structured array"
            )
        hits = context.get_data(run_id, "hit_threshold")
        if not isinstance(hits, np.ndarray):
            raise ValueError("hit_merged_features expects hit_threshold as a structured array")

        loaded = load_wave_input(context, self, run_id)
        if not loaded.spec.is_records or loaded.records is None or loaded.wave_pool is None:
            raise ValueError("hit_merged_features currently supports wave_source='records' only")

        resolve_dt_config(context, self, deprecated_keys=("sampling_interval_ns", "dt_ns"))
        records_by_id = _record_lookup(loaded.records)
        return self._compute_features(
            merged=merged,
            component_rows=component_rows,
            hits=hits,
            records_by_id=records_by_id,
            wave_pool=loaded.wave_pool,
        )

    def _compute_features(
        self,
        *,
        merged: np.ndarray,
        component_rows: np.ndarray,
        hits: np.ndarray,
        records_by_id: dict[int, np.void],
        wave_pool: np.ndarray,
    ) -> np.ndarray:
        rows: list[tuple] = []
        component_merged = np.asarray(component_rows["merged_index"], dtype=np.int64)
        component_hits = np.asarray(component_rows["hit_index"], dtype=np.int64)

        for merged_index, row in enumerate(merged):
            record_id = int(row["record_id"])
            sample_start = int(row["sample_start"])
            sample_end = int(row["sample_end"])
            n_hits = int(row["component_count"]) if "component_count" in row.dtype.names else 1

            if sample_start >= 0 and sample_end > sample_start:
                if record_id not in records_by_id:
                    raise ValueError(f"hit_merged_features could not resolve record_id={record_id}")
                record = records_by_id[record_id]
                time_start, time_end, area, height, max_time = _window_feature_values(
                    source_row=row,
                    record=record,
                    wave_pool=wave_pool,
                    start=sample_start,
                    end=sample_end,
                    data_name=self.provides,
                )
            else:
                hit_indices = component_hits[component_merged == merged_index]
                if len(hit_indices) == 0:
                    raise ValueError(
                        f"hit_merged_features could not resolve components for merged_index="
                        f"{merged_index}"
                    )
                time_start, time_end, area, height, max_time = self._fallback_values(
                    merged_index=merged_index,
                    hits=hits[hit_indices],
                    records_by_id=records_by_id,
                    wave_pool=wave_pool,
                )

            center_time = int((time_start + time_end) // 2)
            width = float((time_end - time_start) / 1e3)
            rise_time = float((max_time - time_start) / 1e3)
            fall_time = float((time_end - max_time) / 1e3)
            rows.append(
                (
                    merged_index,
                    int(row["board"]) if "board" in row.dtype.names else 0,
                    int(row["channel"]),
                    record_id,
                    time_start,
                    time_end,
                    center_time,
                    max_time,
                    area,
                    height,
                    width,
                    rise_time,
                    fall_time,
                    n_hits,
                    1,
                )
            )

        return np.array(rows, dtype=HIT_MERGED_FEATURES_DTYPE) if rows else _empty_features()

    def _fallback_values(
        self,
        *,
        merged_index: int,
        hits: np.ndarray,
        records_by_id: dict[int, np.void],
        wave_pool: np.ndarray,
    ) -> tuple[int, int, float, float, int]:
        time_start: int | None = None
        time_end: int | None = None
        area = 0.0
        height = 0.0
        max_time: int | None = None

        for hit in hits:
            record_id = int(hit["record_id"])
            if record_id not in records_by_id:
                raise ValueError(f"hit_merged_features could not resolve record_id={record_id}")
            start = int(hit["edge_start"])
            end = int(hit["edge_end"])
            if end <= start:
                raise ValueError(
                    f"hit_merged_features could not integrate merged_index={merged_index}: "
                    f"component hit has empty sample window [{start}, {end})"
                )
            hit_start, hit_end, hit_area, hit_height, hit_max_time = _window_feature_values(
                source_row=hit,
                record=records_by_id[record_id],
                wave_pool=wave_pool,
                start=start,
                end=end,
                data_name=self.provides,
            )
            time_start = hit_start if time_start is None else min(time_start, hit_start)
            time_end = hit_end if time_end is None else max(time_end, hit_end)
            area += hit_area
            if hit_height > height or max_time is None:
                height = hit_height
                max_time = hit_max_time

        if time_start is None or time_end is None or max_time is None:
            raise ValueError(
                f"hit_merged_features could not integrate merged_index={merged_index}: "
                "no valid component windows"
            )
        return time_start, time_end, area, height, max_time


__all__ = ["HIT_MERGED_FEATURES_DTYPE", "HitMergedFeaturesPlugin"]
