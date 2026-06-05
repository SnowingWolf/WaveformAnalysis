"""Per-channel waveform features for hit_merged rows."""

from typing import Any

import numba as nb
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


def _field_or_default(arr: np.ndarray, name: str, default, dtype):
    """从 structured array 安全提取字段，不存在时返回默认值数组"""
    names = arr.dtype.names or ()
    if name in names:
        return np.asarray(arr[name], dtype=dtype)
    return np.full(len(arr), default, dtype=dtype)


def _resolve_record_indices(records: np.ndarray, record_ids: np.ndarray) -> np.ndarray:
    """
    把 record_id 转成 records 的行号。
    优先处理 record_id == row index 的快路径。
    """
    record_ids = np.asarray(record_ids, dtype=np.int64)
    names = records.dtype.names or ()

    if "record_id" not in names:
        # records 没有 record_id 字段，假设 record_id == index
        bad_mask = (record_ids < 0) | (record_ids >= len(records))
        if np.any(bad_mask):
            bad_id = record_ids[bad_mask][0]
            raise ValueError(f"hit_merged_features could not resolve record_id={bad_id}")
        return record_ids

    rec_ids = np.asarray(records["record_id"], dtype=np.int64)

    # 快路径：record_id == array index
    if len(rec_ids) == len(records) and np.array_equal(
        rec_ids, np.arange(len(records), dtype=np.int64)
    ):
        bad_mask = (record_ids < 0) | (record_ids >= len(records))
        if np.any(bad_mask):
            bad_id = record_ids[bad_mask][0]
            raise ValueError(f"hit_merged_features could not resolve record_id={bad_id}")
        return record_ids

    # 通用路径：排序 + searchsorted
    order = np.argsort(rec_ids, kind="mergesort")
    rec_ids_sorted = rec_ids[order]

    pos = np.searchsorted(rec_ids_sorted, record_ids)
    bad = (pos >= len(rec_ids_sorted)) | (rec_ids_sorted[pos] != record_ids)
    if np.any(bad):
        bad_id = record_ids[bad][0]
        raise ValueError(f"hit_merged_features could not resolve record_id={bad_id}")

    return order[pos]


def _polarity_sign_array(records: np.ndarray) -> np.ndarray:
    """
    返回 polarity sign 数组：
    - positive: +1.0 (signal = raw - baseline)
    - negative: -1.0 (signal = baseline - raw)
    """
    names = records.dtype.names or ()
    sign = np.full(len(records), -1.0, dtype=np.float32)  # 默认 negative

    if "polarity" not in names:
        return sign

    # polarity 字段可能是字节串或字符串
    for i, p in enumerate(records["polarity"]):
        p_str = p.decode("utf-8") if isinstance(p, bytes) else str(p)
        if p_str == "positive":
            sign[i] = 1.0

    return sign


def _build_component_slices(component_rows: np.ndarray, n_merged: int):
    """
    一次性构建 component 索引映射，避免每次 fallback 都全扫描。
    返回 (component_hits_sorted, comp_starts, comp_ends)
    """
    component_merged = np.asarray(component_rows["merged_index"], dtype=np.int64)
    component_hits = np.asarray(component_rows["hit_index"], dtype=np.int64)

    order = np.argsort(component_merged, kind="mergesort")
    merged_sorted = component_merged[order]
    hits_sorted = component_hits[order]

    keys = np.arange(n_merged, dtype=np.int64)
    starts = np.searchsorted(merged_sorted, keys, side="left")
    ends = np.searchsorted(merged_sorted, keys, side="right")

    return hits_sorted, starts, ends


@nb.njit(cache=True)
def _features_fast_kernel(
    wave_pool,
    rec_indices,
    rec_wave_offset,
    rec_event_length,
    rec_baseline,
    rec_polarity_sign,
    merged_sample_start,
    merged_sample_end,
    merged_timestamp,
    merged_dt,
    merged_position,
):
    """
    Numba 核心：批量计算主路径（有合法 sample_start/sample_end 的 merged hits）。

    对每个窗口做单 pass：遍历一次波形，同时累加 area 和找 max。
    """
    n = len(rec_indices)

    time_start = np.zeros(n, dtype=np.int64)
    time_end = np.zeros(n, dtype=np.int64)
    center_time = np.zeros(n, dtype=np.int64)
    max_time = np.zeros(n, dtype=np.int64)

    area = np.zeros(n, dtype=np.float32)
    height = np.zeros(n, dtype=np.float32)
    width = np.zeros(n, dtype=np.float32)
    rise_time = np.zeros(n, dtype=np.float32)
    fall_time = np.zeros(n, dtype=np.float32)
    valid = np.zeros(n, dtype=np.int8)

    for i in range(n):
        rec_i = rec_indices[i]

        start = merged_sample_start[i]
        end = merged_sample_end[i]

        # 跳过无效窗口（留给 fallback）
        if start < 0 or end <= start:
            continue

        length = rec_event_length[rec_i]

        # clip 到 event_length
        if start < 0:
            start = 0
        if end > length:
            end = length

        if end <= start:
            continue

        offset = rec_wave_offset[rec_i]
        baseline = rec_baseline[rec_i]
        sign = rec_polarity_sign[rec_i]

        # 计算时间窗口
        dt_ps = merged_dt[i] * 1000
        t0 = merged_timestamp[i] + (start - merged_position[i]) * dt_ps
        t1 = merged_timestamp[i] + (end - merged_position[i]) * dt_ps

        # 单 pass 计算：area + max
        s = 0.0
        h = 0.0
        max_j = 0

        base = offset + start
        n_sample = end - start

        for j in range(n_sample):
            v = sign * (float(wave_pool[base + j]) - baseline)
            if v < 0.0:
                v = 0.0

            s += v

            if v > h:
                h = v
                max_j = j

        mt = t0 + max_j * dt_ps

        time_start[i] = t0
        time_end[i] = t1
        center_time[i] = (t0 + t1) // 2
        max_time[i] = mt

        area[i] = s
        height[i] = h
        width[i] = (t1 - t0) / 1000.0
        rise_time[i] = (mt - t0) / 1000.0
        fall_time[i] = (t1 - mt) / 1000.0
        valid[i] = 1

    return (
        time_start,
        time_end,
        center_time,
        max_time,
        area,
        height,
        width,
        rise_time,
        fall_time,
        valid,
    )


def _record_lookup(records: np.ndarray) -> dict[int, np.void]:
    """为 fallback 路径构建 record_id -> record 映射（仅在需要时调用）"""
    names = records.dtype.names or ()
    if "record_id" in names:
        return {int(rec["record_id"]): rec for rec in records}
    return dict(enumerate(records))


def _record_polarity(record: np.void) -> str:
    """从单个 record 获取 polarity（fallback 路径使用）"""
    names = record.dtype.names or ()
    if "polarity" not in names:
        return "negative"
    value = record["polarity"]
    value_str = value.decode("utf-8") if isinstance(value, bytes) else str(value)
    return value_str if value_str in {"positive", "negative"} else "negative"


def _sample_times(row: np.void, start: int, end: int) -> tuple[int, int, int]:
    """计算窗口的时间边界（fallback 路径使用）"""
    names = row.dtype.names or ()
    dt_ns = int(row["dt"]) if "dt" in names else 1
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
    """生成 signal 数组（fallback 路径使用）"""
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
    """计算单个窗口的特征（fallback 路径使用）"""
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
    version = "0.3.0"
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

        return self._compute_features(
            merged=merged,
            component_rows=component_rows,
            hits=hits,
            records=loaded.records,
            wave_pool=loaded.wave_pool,
        )

    def _compute_features(
        self,
        *,
        merged: np.ndarray,
        component_rows: np.ndarray,
        hits: np.ndarray,
        records: np.ndarray,
        wave_pool: np.ndarray,
    ) -> np.ndarray:
        n_merged = len(merged)
        if n_merged == 0:
            return _empty_features()

        # 预分配输出数组
        out = np.zeros(n_merged, dtype=HIT_MERGED_FEATURES_DTYPE)

        # 解析 record_id -> records 行号
        rec_indices = _resolve_record_indices(records, merged["record_id"])

        # 提取 records 字段为普通数组（Numba 可以高效访问）
        rec_wave_offset = np.asarray(records["wave_offset"], dtype=np.int64)
        rec_event_length = np.asarray(records["event_length"], dtype=np.int64)
        rec_baseline = _field_or_default(records, "baseline", 0.0, np.float32)
        rec_polarity_sign = _polarity_sign_array(records)

        # 提取 merged 字段
        merged_sample_start = np.asarray(merged["sample_start"], dtype=np.int64)
        merged_sample_end = np.asarray(merged["sample_end"], dtype=np.int64)
        merged_timestamp = _field_or_default(merged, "timestamp", 0, np.int64)
        merged_dt = _field_or_default(merged, "dt", 1, np.int64)
        merged_position = _field_or_default(merged, "position", 0, np.int64)

        # Numba 批量计算主路径
        (
            time_start,
            time_end,
            center_time,
            max_time,
            area,
            height,
            width,
            rise_time,
            fall_time,
            valid,
        ) = _features_fast_kernel(
            wave_pool,
            rec_indices,
            rec_wave_offset,
            rec_event_length,
            rec_baseline,
            rec_polarity_sign,
            merged_sample_start,
            merged_sample_end,
            merged_timestamp,
            merged_dt,
            merged_position,
        )

        # 批量填充输出数组
        out["merged_index"] = np.arange(n_merged, dtype=np.int64)
        out["board"] = _field_or_default(merged, "board", 0, np.int16)
        out["channel"] = np.asarray(merged["channel"], dtype=np.int16)
        out["record_id"] = np.asarray(merged["record_id"], dtype=np.int64)

        out["time_start"] = time_start
        out["time_end"] = time_end
        out["center_time"] = center_time
        out["max_time"] = max_time

        out["area"] = area
        out["height"] = height
        out["width"] = width
        out["rise_time"] = rise_time
        out["fall_time"] = fall_time

        if "component_count" in (merged.dtype.names or ()):
            out["n_hits"] = np.asarray(merged["component_count"], dtype=np.int32)
        else:
            out["n_hits"] = 1

        out["valid"] = valid

        # fallback：只处理 Numba 主路径没处理成功的行
        bad = np.flatnonzero(valid == 0)

        if len(bad):
            # 为 fallback 构建快速索引
            component_hits_sorted, comp_starts, comp_ends = _build_component_slices(
                component_rows,
                n_merged=n_merged,
            )

            # fallback 路径仍然需要 dict（因为跨 record）
            records_by_id = _record_lookup(records)

            for merged_index in bad:
                hit_indices = component_hits_sorted[
                    comp_starts[merged_index] : comp_ends[merged_index]
                ]

                if len(hit_indices) == 0:
                    raise ValueError(
                        f"hit_merged_features could not resolve components for merged_index="
                        f"{merged_index}"
                    )

                ts, te, a, h, mt = self._fallback_values(
                    merged_index=int(merged_index),
                    hits=hits[hit_indices],
                    records_by_id=records_by_id,
                    wave_pool=wave_pool,
                )

                out[merged_index]["time_start"] = ts
                out[merged_index]["time_end"] = te
                out[merged_index]["center_time"] = int((ts + te) // 2)
                out[merged_index]["max_time"] = mt
                out[merged_index]["area"] = a
                out[merged_index]["height"] = h
                out[merged_index]["width"] = float((te - ts) / 1e3)
                out[merged_index]["rise_time"] = float((mt - ts) / 1e3)
                out[merged_index]["fall_time"] = float((te - mt) / 1e3)
                out[merged_index]["valid"] = 1

        return out

    def _fallback_values(
        self,
        *,
        merged_index: int,
        hits: np.ndarray,
        records_by_id: dict[int, np.void],
        wave_pool: np.ndarray,
    ) -> tuple[int, int, float, float, int]:
        """处理跨 record 或无合法 sample window 的 merged hits"""
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
