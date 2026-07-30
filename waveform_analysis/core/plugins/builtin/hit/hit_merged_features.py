"""Per-channel waveform features for hit_merged rows."""

from typing import Any

import numba as nb
import numpy as np

from waveform_analysis.core.hardware.channel import (
    get_gain_adc_per_pe,
    resolve_channel_value_map,
    unique_hardware_channels,
)
from waveform_analysis.core.plugins.builtin.cpu._dt_compat import resolve_dt_config
from waveform_analysis.core.plugins.builtin.cpu._record_utils import (
    RecordLookup,
)
from waveform_analysis.core.plugins.builtin.cpu._record_utils import (
    field_or_default as _field_or_default_util,
)
from waveform_analysis.core.plugins.builtin.cpu._record_utils import (
    resolve_record_indices as _resolve_record_indices_util,
)
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
        ("area_pe", "f4"),
        ("height_pe", "f4"),
    ]
)


def _empty_features() -> np.ndarray:
    return np.zeros(0, dtype=HIT_MERGED_FEATURES_DTYPE)


def _field_or_default(arr: np.ndarray, name: str, default, dtype):
    """已弃用：使用 _record_utils.field_or_default 替代。

    保留此函数用于向后兼容。
    """
    return _field_or_default_util(arr, name, default, dtype)


def _resolve_record_indices(records: np.ndarray, record_ids: np.ndarray) -> np.ndarray:
    """已弃用：使用 _record_utils.resolve_record_indices 替代。

    保留此函数用于向后兼容。
    """
    return _resolve_record_indices_util(records, record_ids)


def _polarity_sign_array(records: np.ndarray) -> np.ndarray:
    """
    返回 polarity sign 数组：
    - positive: +1.0 (signal = raw - baseline)
    - negative: -1.0 (signal = baseline - raw)

    Phase 4 优化：向量化比较，消除 Python 循环
    """
    names = records.dtype.names or ()
    sign = np.full(len(records), -1.0, dtype=np.float32)  # 默认 negative

    if "polarity" not in names:
        return sign

    pol = records["polarity"]

    # 向量化路径：直接比较字节串/字符串
    if pol.dtype.kind == "S":  # 字节串 (bytes)
        sign[pol == b"positive"] = 1.0
    elif pol.dtype.kind == "U":  # Unicode 字符串
        sign[pol == "positive"] = 1.0
    else:
        # Fallback：对象数组或其他类型，使用循环
        for i, p in enumerate(pol):
            p_str = p.decode("utf-8") if isinstance(p, bytes) else str(p)
            if p_str == "positive":
                sign[i] = 1.0

    return sign


@nb.njit(cache=True, fastmath=True, parallel=True, nogil=True)
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
    out,
):
    """
    Numba 核心：批量计算主路径（有合法 sample_start/sample_end 的 merged hits）。

    直接写入预分配的输出数组，消除中间临时数组。

    - 使用 max() 替代 if 分支（Numba 优化为无分支 SIMD 指令）
    - 优化 baseline 减法顺序
    - fastmath=True: 激进浮点优化
    - parallel=True: 启用多线程并行
    """
    n = len(rec_indices)

    for i in nb.prange(n):
        rec_i = rec_indices[i]

        start = merged_sample_start[i]
        end = merged_sample_end[i]

        # 跳过无效窗口（留给 fallback）
        if start < 0 or end <= start:
            continue

        length = rec_event_length[rec_i]

        # clip 到 event_length
        clipped_start = max(0, start)
        clipped_end = min(length, end)

        if clipped_end <= clipped_start:
            continue

        offset = rec_wave_offset[rec_i]
        baseline = rec_baseline[rec_i]
        sign = rec_polarity_sign[rec_i]

        # 计算时间窗口
        dt_ps = merged_dt[i] * 1000
        t0 = merged_timestamp[i] + (clipped_start - merged_position[i]) * dt_ps
        t1 = merged_timestamp[i] + (clipped_end - merged_position[i]) * dt_ps

        # 单 pass 计算：area + max
        s = 0.0
        h = 0.0
        max_j = 0

        base = offset + clipped_start
        n_sample = clipped_end - clipped_start

        # 内层循环：优化分支和内存访问
        for j in range(n_sample):
            raw = float(wave_pool[base + j])
            v = sign * (raw - baseline)
            # 使用 max 替代 if（无分支指令）
            v = max(v, 0.0)

            s += v

            if v > h:
                h = v
                max_j = j

        mt = t0 + max_j * dt_ps

        out[i]["time_start"] = t0
        out[i]["time_end"] = t1
        out[i]["center_time"] = (t0 + t1) // 2
        out[i]["max_time"] = mt

        out[i]["area"] = s
        out[i]["height"] = h
        out[i]["width"] = (t1 - t0) / 1000.0
        out[i]["rise_time"] = (mt - t0) / 1000.0
        out[i]["fall_time"] = (t1 - mt) / 1000.0
        out[i]["valid"] = 1


@nb.njit(cache=True, fastmath=True, parallel=True, nogil=True)
def _features_fallback_kernel(
    wave_pool,
    rec_wave_offset,
    rec_event_length,
    rec_baseline,
    rec_polarity_sign,
    fallback_indices,
    comp_offsets,
    comp_counts,
    component_hit_indices,
    hit_edge_start,
    hit_edge_end,
    hit_timestamp,
    hit_dt,
    hit_position,
    hit_rec_indices,
    out,
):
    """
    Numba fallback 核心：批量处理跨 record 或无合法窗口的 merged hits。

    外层 nb.prange 遍历 clusters，内层遍历每个 cluster 的 component hits。
    对每个 component hit 执行波形切片、极性转换、sum 和 argmax，
    然后聚合并写入 out 数组。

    - fastmath=True，parallel=True，nogil=True
    - 使用 max() 替代 if 分支（与主 kernel 风格一致）
    """
    for fi in nb.prange(len(fallback_indices)):
        merged_idx = fallback_indices[fi]
        start = comp_offsets[merged_idx]
        count = comp_counts[merged_idx]
        if count <= 0:
            continue

        t_start = np.int64(0)
        t_end = np.int64(0)
        max_t = np.int64(0)
        # Keep the legacy aggregation precision: each component produces a
        # float32 sum, then cluster area is accumulated as a Python float.
        area = 0.0
        height = np.float32(0.0)
        has_any = False

        for ci in range(count):
            hit_i = component_hit_indices[start + ci]
            rec_i = hit_rec_indices[hit_i]

            edge_s = hit_edge_start[hit_i]
            edge_e = hit_edge_end[hit_i]

            # Clip only the waveform read. Timing fields deliberately retain
            # the original hit edges for compatibility with the Python path.
            cs = max(0, edge_s)
            ce = min(rec_event_length[rec_i], edge_e)

            offset = rec_wave_offset[rec_i]
            baseline = rec_baseline[rec_i]
            sign = rec_polarity_sign[rec_i]

            dt_ps = hit_dt[hit_i] * 1000
            hit_ts = hit_timestamp[hit_i]
            hit_pos = hit_position[hit_i]
            t0 = hit_ts + (edge_s - hit_pos) * dt_ps
            t1 = hit_ts + (edge_e - hit_pos) * dt_ps

            # 单 pass 计算：area + max
            s = np.float32(0.0)
            h = np.float32(0.0)
            max_j = 0
            base = offset + cs
            n_sample = ce - cs

            for j in range(n_sample):
                raw = np.float32(wave_pool[base + j])
                v = sign * (raw - baseline)
                v = max(v, np.float32(0.0))
                s += v
                if v > h:
                    h = v
                    max_j = j

            mt = t0 + max_j * dt_ps

            if not has_any:
                t_start = t0
                t_end = t1
                max_t = mt
                has_any = True
            else:
                if t0 < t_start:
                    t_start = t0
                if t1 > t_end:
                    t_end = t1

            area += float(s)
            if h > height:
                height = h
                max_t = mt

        if has_any:
            out[merged_idx]["time_start"] = t_start
            out[merged_idx]["time_end"] = t_end
            out[merged_idx]["center_time"] = (t_start + t_end) // 2
            out[merged_idx]["max_time"] = max_t
            out[merged_idx]["area"] = area
            out[merged_idx]["height"] = height
            out[merged_idx]["width"] = np.float32(t_end - t_start) / np.float32(1000.0)
            out[merged_idx]["rise_time"] = np.float32(max_t - t_start) / np.float32(1000.0)
            out[merged_idx]["fall_time"] = np.float32(t_end - max_t) / np.float32(1000.0)
            out[merged_idx]["valid"] = 1


@nb.njit(cache=True, nogil=True)
def _validate_fallback_components_kernel(
    fallback_indices,
    comp_offsets,
    comp_counts,
    component_merged_indices,
    component_hit_indices,
    n_hits,
    hit_edge_start,
    hit_edge_end,
    hit_rec_indices,
    rec_event_length,
):
    """Return the first invalid fallback component without entering prange."""
    n_components = len(component_hit_indices)
    for fi in range(len(fallback_indices)):
        merged_idx = fallback_indices[fi]
        start = comp_offsets[merged_idx]
        count = comp_counts[merged_idx]
        if start < 0 or count <= 0 or start + count > n_components:
            return 1, merged_idx, -1, start, count

        for ci in range(count):
            component_row = start + ci
            hit_idx = component_hit_indices[component_row]
            if component_merged_indices[component_row] != merged_idx:
                return 2, merged_idx, hit_idx, start, count
            if hit_idx < 0 or hit_idx >= n_hits:
                return 3, merged_idx, hit_idx, start, count

            edge_start = hit_edge_start[hit_idx]
            edge_end = hit_edge_end[hit_idx]
            if edge_end <= edge_start:
                return 4, merged_idx, hit_idx, edge_start, edge_end

            record_index = hit_rec_indices[hit_idx]
            clipped_start = max(0, edge_start)
            clipped_end = min(rec_event_length[record_index], edge_end)
            if clipped_end <= clipped_start:
                return 5, merged_idx, hit_idx, edge_start, edge_end

    return 0, -1, -1, 0, 0


def _raise_fallback_validation_error(
    error_code: int,
    merged_index: int,
    hit_index: int,
    first_value: int,
    second_value: int,
) -> None:
    if error_code == 1:
        raise ValueError(
            "hit_merged_features could not resolve components for "
            f"merged_index={merged_index}: invalid component slice "
            f"offset={first_value}, count={second_value}"
        )
    if error_code == 2:
        raise ValueError(
            "hit_merged_features component rows are not aligned with "
            f"merged_index={merged_index}"
        )
    if error_code == 3:
        raise ValueError(
            "hit_merged_features component hit index is outside hit_threshold: "
            f"merged_index={merged_index}, hit_index={hit_index}"
        )
    if error_code == 4:
        raise ValueError(
            f"hit_merged_features could not integrate merged_index={merged_index}: "
            f"component hit has empty sample window [{first_value}, {second_value})"
        )
    if error_code == 5:
        raise ValueError(
            f"hit_merged_features could not integrate merged_index={merged_index}: "
            f"component hit has empty sample window [{first_value}, {second_value}) after clipping"
        )
    raise RuntimeError(f"Unknown fallback component validation error: {error_code}")


class HitMergedFeaturesPlugin(Plugin):
    """Compute local single-channel waveform features for every hit_merged row."""

    provides = "hit_merged_features"
    lineage_virtual = True
    depends_on = []  # 使用 resolve_depends_on() 动态解析
    description = "Compute per-hit_merged local waveform features from records-backed samples."
    version = "0.5.1"
    save_when = "always"
    output_dtype = HIT_MERGED_FEATURES_DTYPE
    uses_run_config = True

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
        "gain_adc_per_pe": Option(
            default=None,
            type=dict,
            help=(
                '按硬件通道配置 ADC/PE 增益，键请使用 "board:channel"，'
                '例如 {"0:0": 12.5, "0:1": 13.2}。'
                "设置后会新增 area_pe/height_pe 列。"
            ),
        ),
        "normalize_to_pe": Option(
            default=False,
            type=bool,
            help=(
                "是否将 area/height 直接归一化为 PE 单位。"
                "False (默认): area/height 保持 ADC 单位，area_pe/height_pe 输出 PE 单位。"
                "True: area/height 归一化为 PE 单位，area_pe/height_pe 为 NaN。"
            ),
        ),
        "feature_num_threads": Option(
            default=None,
            type=int,
            help="Numba kernel 线程数；None 使用 Numba 默认。",
            track=False,
        ),
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

        num_threads = context.get_config(self, "feature_num_threads")

        result = self._compute_features(
            merged=merged,
            component_rows=component_rows,
            hits=hits,
            records=loaded.records,
            wave_pool=loaded.wave_pool,
            num_threads=num_threads,
        )

        # 应用增益校准
        result = self._apply_gain_calibration(context, run_id, result)

        return result

    def _compute_features(
        self,
        *,
        merged: np.ndarray,
        component_rows: np.ndarray,
        hits: np.ndarray,
        records: np.ndarray,
        wave_pool: np.ndarray,
        num_threads: int | None = None,
    ) -> np.ndarray:
        n_merged = len(merged)
        if n_merged == 0:
            return _empty_features()

        # 预分配输出数组
        out = np.zeros(n_merged, dtype=HIT_MERGED_FEATURES_DTYPE)

        # Build the potentially expensive record-id index once and reuse it
        # for the direct and cross-record paths.
        record_lookup = RecordLookup(records)
        rec_indices = record_lookup.get_indices(merged["record_id"])

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

        # 批量填充输出数组（非 kernel 计算的字段）
        out["merged_index"] = np.arange(n_merged, dtype=np.int64)
        out["board"] = _field_or_default(merged, "board", 0, np.int16)
        out["channel"] = np.asarray(merged["channel"], dtype=np.int16)
        out["record_id"] = np.asarray(merged["record_id"], dtype=np.int64)

        if "component_count" in (merged.dtype.names or ()):
            out["n_hits"] = np.asarray(merged["component_count"], dtype=np.int32)
        else:
            out["n_hits"] = 1

        # Numba 主路径：直接写入 out 数组
        if num_threads is not None and num_threads <= 0:
            raise ValueError("feature_num_threads must be positive when set")

        old_threads = None
        if num_threads is not None:
            old_threads = nb.get_num_threads()
            nb.set_num_threads(num_threads)
        try:
            _features_fast_kernel(
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
                out,
            )
            # Only invalid direct windows need component expansion.
            bad = np.flatnonzero(out["valid"] == 0)

            if len(bad) > 0:
                comp_offsets = np.asarray(merged["component_offset"], dtype=np.int64)
                comp_counts = np.asarray(merged["component_count"], dtype=np.int32)
                component_merged_indices = np.asarray(
                    component_rows["merged_index"], dtype=np.int64
                )
                component_hit_indices = np.asarray(component_rows["hit_index"], dtype=np.int64)
                hit_record_id = _field_or_default(hits, "record_id", -1, np.int64)
                hit_edge_start = _field_or_default(hits, "edge_start", 0, np.int64)
                hit_edge_end = _field_or_default(hits, "edge_end", 0, np.int64)
                hit_timestamp = _field_or_default(hits, "timestamp", 0, np.int64)
                hit_dt = _field_or_default(hits, "dt", 1, np.int64)
                hit_position = _field_or_default(hits, "position", 0, np.int64)
                hit_rec_indices = record_lookup.get_indices(hit_record_id)

                validation = _validate_fallback_components_kernel(
                    bad,
                    comp_offsets,
                    comp_counts,
                    component_merged_indices,
                    component_hit_indices,
                    len(hits),
                    hit_edge_start,
                    hit_edge_end,
                    hit_rec_indices,
                    rec_event_length,
                )
                if validation[0] != 0:
                    _raise_fallback_validation_error(*validation)

                _features_fallback_kernel(
                    wave_pool,
                    rec_wave_offset,
                    rec_event_length,
                    rec_baseline,
                    rec_polarity_sign,
                    bad,
                    comp_offsets,
                    comp_counts,
                    component_hit_indices,
                    hit_edge_start,
                    hit_edge_end,
                    hit_timestamp,
                    hit_dt,
                    hit_position,
                    hit_rec_indices,
                    out,
                )
        finally:
            if old_threads is not None:
                nb.set_num_threads(old_threads)

        return out

    def _apply_gain_calibration(
        self, context: Any, run_id: str, features: np.ndarray
    ) -> np.ndarray:
        """应用增益校准，支持两种模式：

        1. normalize_to_pe=False (默认): area/height 保持 ADC，area_pe/height_pe 输出 PE
        2. normalize_to_pe=True: area/height 归一化为 PE，area_pe/height_pe 为 NaN
        """
        if len(features) == 0:
            return features

        # 获取配置
        gain_adc_per_pe = context.get_config(self, "gain_adc_per_pe")
        normalize_to_pe = context.get_config(self, "normalize_to_pe")

        # 没有配置增益，全部填充 NaN
        if gain_adc_per_pe is None or not isinstance(gain_adc_per_pe, dict):
            features["area_pe"] = np.nan
            features["height_pe"] = np.nan
            return features

        # 获取所有唯一通道
        boards = features["board"]
        channels = features["channel"]
        hw_channels = unique_hardware_channels(boards, channels)

        # 解析增益映射
        gain_map = resolve_channel_value_map(
            channel_config=gain_adc_per_pe,
            run_id=run_id,
            channels=hw_channels,
            plugin_name=self.provides,
            value_name="gain_adc_per_pe",
        )

        if not gain_map:
            # 没有有效的增益值
            features["area_pe"] = np.nan
            features["height_pe"] = np.nan
            return features

        # 模式 1: normalize_to_pe=True，直接归一化 area/height
        if normalize_to_pe:
            for idx in range(len(features)):
                gain = get_gain_adc_per_pe(gain_map, int(boards[idx]), int(channels[idx]))
                if gain is not None and gain > 0:
                    features["area"][idx] /= gain
                    features["height"][idx] /= gain
            # area_pe/height_pe 填充 NaN（因为 area/height 已经是 PE 单位）
            features["area_pe"] = np.nan
            features["height_pe"] = np.nan
        else:
            # 模式 2: normalize_to_pe=False (默认)，保持 area/height 为 ADC，计算 area_pe/height_pe
            area_pe = np.full(len(features), np.nan, dtype=np.float32)
            height_pe = np.full(len(features), np.nan, dtype=np.float32)

            for idx in range(len(features)):
                gain = get_gain_adc_per_pe(gain_map, int(boards[idx]), int(channels[idx]))
                if gain is not None and gain > 0:
                    area_pe[idx] = features["area"][idx] / gain
                    height_pe[idx] = features["height"][idx] / gain

            features["area_pe"] = area_pe
            features["height_pe"] = height_pe

        return features


__all__ = ["HIT_MERGED_FEATURES_DTYPE", "HitMergedFeaturesPlugin"]
