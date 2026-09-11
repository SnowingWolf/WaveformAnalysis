"""HitMergedFeaturesPlugin 类实现 - 为每条 hit_merged 行计算单通道波形特征。"""

import logging
import time
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
from waveform_analysis.core.plugins.builtin.shared.canonical_waveform_numba import (
    MAX_CANONICAL_DENSE_SAMPLES_PER_BATCH,
    classify_dense_canonical_groups,
    materialize_dense_canonical_groups,
)
from waveform_analysis.core.plugins.builtin.shared.waveform_merge import merge_waveform_segments
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
    clip_negative_signal,
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
        h = -np.inf
        max_j = 0

        base = offset + clipped_start
        n_sample = clipped_end - clipped_start

        # 内层循环：优化分支和内存访问
        for j in range(n_sample):
            raw = float(wave_pool[base + j])
            v = sign * (raw - baseline)
            if clip_negative_signal and v < 0.0:
                v = 0.0

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


@nb.njit(cache=True, nogil=True, parallel=True)
def _fill_nonoverlap_fallback_pool_kernel(
    wave_pool,
    group_component_offsets,
    group_pool_offsets,
    ordered_record_indices,
    ordered_clipped_starts,
    ordered_clipped_ends,
    ordered_time_starts,
    ordered_dts,
    rec_wave_offset,
    rec_baseline,
    rec_polarity_sign,
    clip_negative_signal,
    values_out,
    times_out,
):
    """Materialize disjoint fallback segments in canonical time order.

    Each group owns a disjoint output range, so this is the only parallel
    layer.  Reduction intentionally stays in NumPy: it preserves the current
    Python canonical ``sum(dtype=float64)`` and first-maximum behaviour.
    """
    n_groups = len(group_pool_offsets) - 1
    for group_index in nb.prange(n_groups):
        component_start = group_component_offsets[group_index]
        component_end = group_component_offsets[group_index + 1]
        pool_index = group_pool_offsets[group_index]

        for component_index in range(component_start, component_end):
            record_index = ordered_record_indices[component_index]
            clipped_start = ordered_clipped_starts[component_index]
            clipped_end = ordered_clipped_ends[component_index]
            sample_time = ordered_time_starts[component_index]
            dt_ps = ordered_dts[component_index] * 1000
            wave_offset = rec_wave_offset[record_index]
            baseline = rec_baseline[record_index]
            polarity_sign = rec_polarity_sign[record_index]

            for sample_index in range(clipped_end - clipped_start):
                raw = np.float32(wave_pool[wave_offset + clipped_start + sample_index])
                value = polarity_sign * (raw - baseline)
                if clip_negative_signal and value < np.float32(0.0):
                    value = np.float32(0.0)
                values_out[pool_index] = value
                times_out[pool_index] = sample_time + sample_index * dt_ps
                pool_index += 1


_FALLBACK_GROUPS_PER_BATCH = 4_096


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
    version = "1.1.3"
    save_when = "always"
    output_dtype = HIT_MERGED_FEATURES_DTYPE
    uses_run_config = True
    agent_doc = {
        "overview": (
            "为每条 `hit_merged` 计算单硬件通道的局部波形特征。直接窗口由 Numba "
            "并行计算；cross-record fallback 先按安全性分流，非重叠片段按绝对时间在 "
            "Numba 中物化，再用与 Python canonical 相同的 NumPy 归约生成特征。"
        ),
        "workflow_steps": [
            "读取 hit_merged、component 映射、threshold hits、records 与所选波形池。",
            "直接窗口走 Numba 单遍 area/height 计算；无效窗口展开为 component 片段。",
            "同通道、同 dt 且绝对时间不重叠的 fallback 片段走 Numba compact 路径；可能重叠或不安全的行保留 Python canonical 合并。",
            "将 canonical 顺序的 float32 样本以 NumPy float64 求面积，并写入固定输出 dtype。",
        ],
        "behavior_notes": [
            "默认积分有符号的 baseline/polarity 转换后波形；clip_negative_signal=True 在积分前裁剪负采样。",
            "fallback 保留同通道重叠的去重和 WaveformOverlapConflictError 语义，不用直接 component 求和替代。",
            "feature_num_threads 只控制 Numba 路径；log_feature_diagnostics 仅记录运行时统计，不参与 cache lineage。",
        ],
        "failure_modes": [
            "缺失 record、无效 component 映射或空的裁剪后窗口会显式失败。",
            "同一硬件通道同一绝对时间的位级不同采样会抛出 WaveformOverlapConflictError。",
        ],
        "config_notes": {
            "feature_num_threads": "设置 Numba 路径线程数；None 使用 Numba 默认，且不改变 cache lineage。",
            "log_feature_diagnostics": "记录 direct/Numba canonical/Python canonical 的行数、样本数和耗时。",
        },
        "downstream_notes": [
            "peaklet_channels、peaklets 与后续峰特征消费本插件的 area、height 和时间字段。",
            "版本 1.1.0 更换 fallback 执行路径，缓存会因 lineage 自动重建。",
        ],
        "agent_change_notes": [
            "修改 fallback 时必须对照 Python canonical，保持 signed、clipped、重叠去重和冲突错误语义。",
            "性能回归同时报告 Numba compute 和波形 pool 的 cache-save I/O，避免将持久化误判为重算。",
        ],
    }

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
        "clip_negative_signal": Option(
            default=False,
            type=bool,
            help=(
                "是否在积分前把负的基线扣除采样裁剪为 0。默认 False，"
                "area 直接积分有符号波形；True 仅用于兼容旧行为。"
            ),
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
        "log_feature_diagnostics": Option(
            default=False,
            type=bool,
            help="记录 direct、Numba canonical 与 Python canonical fallback 的数量和耗时。",
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

        loaded = load_wave_input(context, self, run_id, needs_records_view=False)
        if not loaded.spec.is_records or loaded.records is None or loaded.wave_pool is None:
            raise ValueError("hit_merged_features currently supports wave_source='records' only")

        resolve_dt_config(context, self, deprecated_keys=("sampling_interval_ns", "dt_ns"))

        num_threads = context.get_config(self, "feature_num_threads")
        clip_negative_signal = bool(context.get_config(self, "clip_negative_signal"))
        log_diagnostics = bool(context.get_config(self, "log_feature_diagnostics"))

        result = self._compute_features(
            merged=merged,
            component_rows=component_rows,
            hits=hits,
            records=loaded.records,
            wave_pool=loaded.wave_pool,
            num_threads=num_threads,
            clip_negative_signal=clip_negative_signal,
            log_diagnostics=log_diagnostics,
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
        clip_negative_signal: bool = False,
        log_diagnostics: bool = False,
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

        diagnostics = {
            "direct_rows": 0,
            "numba_canonical_rows": 0,
            "python_canonical_rows": 0,
            "fallback_components": 0,
            "numba_canonical_samples": 0,
            "classify_seconds": 0.0,
            "numba_canonical_seconds": 0.0,
            "python_canonical_seconds": 0.0,
        }

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
                clip_negative_signal,
                out,
            )
            # Only invalid direct windows need component expansion.
            bad = np.flatnonzero(out["valid"] == 0)
            diagnostics["direct_rows"] = int(n_merged - len(bad))

            if len(bad) > 0:
                classify_started_at = time.perf_counter()
                comp_offsets = np.asarray(merged["component_offset"], dtype=np.int64)
                comp_counts = np.asarray(merged["component_count"], dtype=np.int32)
                component_merged_indices = np.asarray(
                    component_rows["merged_index"], dtype=np.int64
                )
                component_hit_indices = np.asarray(component_rows["hit_index"], dtype=np.int64)
                hit_record_id = _field_or_default(hits, "record_id", -1, np.int64)
                hit_edge_start = _field_or_default(hits, "edge_start", 0, np.int64)
                hit_edge_end = _field_or_default(hits, "edge_end", 0, np.int64)
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
                diagnostics["fallback_components"] = int(np.sum(comp_counts[bad]))
                numba_bad = self._compute_nonoverlap_fallback_features(
                    bad=bad,
                    comp_offsets=comp_offsets,
                    comp_counts=comp_counts,
                    component_hit_indices=component_hit_indices,
                    hits=hits,
                    wave_pool=wave_pool,
                    record_lookup=record_lookup,
                    rec_wave_offset=rec_wave_offset,
                    rec_event_length=rec_event_length,
                    rec_baseline=rec_baseline,
                    rec_polarity_sign=rec_polarity_sign,
                    clip_negative_signal=clip_negative_signal,
                    out=out,
                    diagnostics=diagnostics,
                )
                diagnostics["classify_seconds"] = time.perf_counter() - classify_started_at
                if len(numba_bad) > 0:
                    python_started_at = time.perf_counter()
                    self._compute_fallback_features(
                        bad=numba_bad,
                        comp_offsets=comp_offsets,
                        comp_counts=comp_counts,
                        component_hit_indices=component_hit_indices,
                        hits=hits,
                        records=records,
                        wave_pool=wave_pool,
                        record_lookup=record_lookup,
                        clip_negative_signal=clip_negative_signal,
                        out=out,
                    )
                    diagnostics["python_canonical_seconds"] = (
                        time.perf_counter() - python_started_at
                    )
                    diagnostics["python_canonical_rows"] = int(len(numba_bad))
        finally:
            if old_threads is not None:
                nb.set_num_threads(old_threads)

        if log_diagnostics:
            logging.getLogger(__name__).info(
                "hit_merged_features diagnostics: "
                f"direct={diagnostics['direct_rows']} "
                f"numba_canonical={diagnostics['numba_canonical_rows']} "
                f"python_canonical={diagnostics['python_canonical_rows']} "
                f"fallback_components={diagnostics['fallback_components']} "
                f"numba_samples={diagnostics['numba_canonical_samples']} "
                f"classify={diagnostics['classify_seconds']:.3f}s "
                f"numba={diagnostics['numba_canonical_seconds']:.3f}s "
                f"python={diagnostics['python_canonical_seconds']:.3f}s "
                f"jit_signatures={len(materialize_dense_canonical_groups.signatures)}"
            )

        return out

    @staticmethod
    def _compute_nonoverlap_fallback_features(
        *,
        bad: np.ndarray,
        comp_offsets: np.ndarray,
        comp_counts: np.ndarray,
        component_hit_indices: np.ndarray,
        hits: np.ndarray,
        wave_pool: np.ndarray,
        record_lookup: RecordLookup,
        rec_wave_offset: np.ndarray,
        rec_event_length: np.ndarray,
        rec_baseline: np.ndarray,
        rec_polarity_sign: np.ndarray,
        clip_negative_signal: bool,
        out: np.ndarray,
        diagnostics: dict[str, Any],
    ) -> np.ndarray:
        """Materialize bounded canonical axes for all safe fallback groups.

        Unlike the previous compact path, overlapping component observations
        are handled in Numba as well.  The occupancy map is keyed by the
        absolute-time bin, so output naturally has the stable time ordering
        that ``merge_waveform_segments(..., dense=False)`` returns.
        """
        python_merged_indices: list[int] = []
        hit_record_id = _field_or_default(hits, "record_id", -1, np.int64)
        hit_edge_start_all = _field_or_default(hits, "edge_start", 0, np.int64)
        hit_edge_end_all = _field_or_default(hits, "edge_end", 0, np.int64)
        hit_timestamp_all = _field_or_default(hits, "timestamp", 0, np.int64)
        hit_dt_all = _field_or_default(hits, "dt", 1, np.int64)
        hit_position_all = _field_or_default(hits, "position", 0, np.int64)
        hit_board_all = _field_or_default(hits, "board", 0, np.int16)
        hit_channel_all = _field_or_default(hits, "channel", 0, np.int16)

        for bad_start in range(0, len(bad), _FALLBACK_GROUPS_PER_BATCH):
            batch_merged = bad[bad_start : bad_start + _FALLBACK_GROUPS_PER_BATCH]
            group_component_offsets = np.empty(len(batch_merged) + 1, dtype=np.int64)
            group_component_offsets[0] = 0
            for group_index, merged_index in enumerate(batch_merged):
                group_component_offsets[group_index + 1] = (
                    group_component_offsets[group_index] + comp_counts[merged_index]
                )
            n_components = int(group_component_offsets[-1])
            if n_components == 0:
                python_merged_indices.extend(map(int, batch_merged))
                continue

            flat_hit_indices = np.empty(n_components, dtype=np.int64)
            for group_index, merged_index in enumerate(batch_merged):
                source_start = int(comp_offsets[merged_index])
                source_end = source_start + int(comp_counts[merged_index])
                target_start = int(group_component_offsets[group_index])
                flat_hit_indices[target_start : target_start + (source_end - source_start)] = (
                    component_hit_indices[source_start:source_end]
                )

            hit_record_indices = record_lookup.get_indices(hit_record_id[flat_hit_indices])
            clipped_starts = np.maximum(hit_edge_start_all[flat_hit_indices], 0)
            clipped_ends = np.minimum(
                hit_edge_end_all[flat_hit_indices], rec_event_length[hit_record_indices]
            )
            component_lengths = clipped_ends - clipped_starts
            component_times = (
                hit_timestamp_all[flat_hit_indices]
                + (clipped_starts - hit_position_all[flat_hit_indices])
                * hit_dt_all[flat_hit_indices]
                * 1000
            )
            component_ends = (
                component_times + component_lengths * hit_dt_all[flat_hit_indices] * 1000
            )
            component_dts = hit_dt_all[flat_hit_indices]
            component_boards = hit_board_all[flat_hit_indices]
            component_channels = hit_channel_all[flat_hit_indices]
            component_baselines = rec_baseline[hit_record_indices]

            group_time_starts = np.zeros(len(batch_merged), dtype=np.int64)
            group_spans = np.zeros(len(batch_merged), dtype=np.int64)
            group_status = np.zeros(len(batch_merged), dtype=np.int8)
            classify_dense_canonical_groups(
                group_component_offsets,
                component_times,
                component_ends,
                component_dts,
                component_boards,
                component_channels,
                component_baselines,
                group_time_starts,
                group_spans,
                group_status,
            )
            python_merged_indices.extend(map(int, batch_merged[group_status != 0]))

            safe_groups = np.flatnonzero(group_status == 0)
            safe_cursor = 0
            while safe_cursor < len(safe_groups):
                safe_spans = group_spans[safe_groups[safe_cursor:]]
                cumulative_spans = np.cumsum(safe_spans, dtype=np.int64)
                local_count = int(
                    np.searchsorted(
                        cumulative_spans,
                        MAX_CANONICAL_DENSE_SAMPLES_PER_BATCH,
                        side="right",
                    )
                )
                local_count = max(local_count, 1)
                selected_groups = safe_groups[safe_cursor : safe_cursor + local_count]
                selected_spans = group_spans[selected_groups]
                pool_offsets = np.empty(len(selected_groups) + 1, dtype=np.int64)
                pool_offsets[0] = 0
                np.cumsum(selected_spans, out=pool_offsets[1:])
                pool_size = int(pool_offsets[-1])
                # ``occupied`` guards every read, so the dense value buffer
                # does not need an eager zero fill for long windows.
                values = np.empty(pool_size, dtype=np.float32)
                values_bits = values.view(np.uint32)
                occupied = np.zeros(pool_size, dtype=np.uint8)
                conflicts = np.zeros(len(selected_groups), dtype=np.uint8)

                started_at = time.perf_counter()
                materialize_dense_canonical_groups(
                    wave_pool,
                    selected_groups,
                    group_component_offsets,
                    pool_offsets,
                    group_time_starts[selected_groups],
                    hit_record_indices,
                    clipped_starts,
                    clipped_ends,
                    component_times,
                    component_dts,
                    rec_wave_offset,
                    rec_baseline,
                    rec_polarity_sign,
                    clip_negative_signal,
                    values,
                    values_bits,
                    occupied,
                    conflicts,
                )
                diagnostics["numba_canonical_seconds"] += time.perf_counter() - started_at

                for local_index, group_index in enumerate(selected_groups):
                    merged_index = int(batch_merged[group_index])
                    if conflicts[local_index]:
                        # Re-enter the existing oracle to retain its precise
                        # public conflict provenance and exception wording.
                        python_merged_indices.append(merged_index)
                        continue
                    pool_start = int(pool_offsets[local_index])
                    pool_end = int(pool_offsets[local_index + 1])
                    occupied_indices = np.flatnonzero(occupied[pool_start:pool_end])
                    if len(occupied_indices) == 0:
                        python_merged_indices.append(merged_index)
                        continue
                    wave = values[pool_start:pool_end][occupied_indices]
                    dt_ps = int(component_dts[group_component_offsets[group_index]]) * 1000
                    time_start = int(group_time_starts[group_index] + occupied_indices[0] * dt_ps)
                    time_end = int(
                        group_time_starts[group_index] + (occupied_indices[-1] + 1) * dt_ps
                    )
                    max_index = int(np.argmax(wave))
                    max_time = int(
                        group_time_starts[group_index] + occupied_indices[max_index] * dt_ps
                    )
                    out[merged_index]["time_start"] = time_start
                    out[merged_index]["time_end"] = time_end
                    out[merged_index]["center_time"] = (time_start + time_end) // 2
                    out[merged_index]["max_time"] = max_time
                    out[merged_index]["area"] = np.sum(wave, dtype=np.float64)
                    out[merged_index]["height"] = wave[max_index]
                    out[merged_index]["width"] = (time_end - time_start) / 1000.0
                    out[merged_index]["rise_time"] = (max_time - time_start) / 1000.0
                    out[merged_index]["fall_time"] = (time_end - max_time) / 1000.0
                    out[merged_index]["valid"] = 1
                    diagnostics["numba_canonical_rows"] += 1
                    diagnostics["numba_canonical_samples"] += len(occupied_indices)
                safe_cursor += local_count

        return np.asarray(python_merged_indices, dtype=np.int64)

    @staticmethod
    def _compute_fallback_features(
        *,
        bad: np.ndarray,
        comp_offsets: np.ndarray,
        comp_counts: np.ndarray,
        component_hit_indices: np.ndarray,
        hits: np.ndarray,
        records: np.ndarray,
        wave_pool: np.ndarray,
        record_lookup: RecordLookup,
        clip_negative_signal: bool,
        out: np.ndarray,
    ) -> None:
        """Compute cross-record features from the canonical absolute-time waveform."""
        for merged_index in bad:
            segments: list[dict[str, Any]] = []
            start = int(comp_offsets[merged_index])
            count = int(comp_counts[merged_index])
            for component_row in range(start, start + count):
                hit_index = int(component_hit_indices[component_row])
                hit = hits[hit_index]
                record_index = int(record_lookup.get_indices(np.array([hit["record_id"]]))[0])
                record = records[record_index]
                edge_start = int(hit["edge_start"])
                edge_end = int(hit["edge_end"])
                clipped_start = max(0, edge_start)
                clipped_end = min(int(record["event_length"]), edge_end)
                offset = int(record["wave_offset"])
                raw = wave_pool[offset + clipped_start : offset + clipped_end].astype(
                    np.float32, copy=False
                )
                sign = float(_polarity_sign_array(records[record_index : record_index + 1])[0])
                signal = sign * (raw - np.float32(record["baseline"]))
                if clip_negative_signal:
                    signal = np.maximum(signal, np.float32(0.0))
                dt_ns = int(hit["dt"])
                dt_ps = dt_ns * 1000
                sample_time_start = (
                    int(hit["timestamp"]) + (clipped_start - int(hit["position"])) * dt_ps
                )
                segments.append(
                    {
                        "waveform": signal,
                        "abs_time_ps": sample_time_start
                        + np.arange(len(signal), dtype=np.int64) * dt_ps,
                        "dt": dt_ns,
                        "board": int(hit["board"]),
                        "channel": int(hit["channel"]),
                        "record_id": int(hit["record_id"]),
                        "merged_index": int(merged_index),
                    }
                )

            merged_wave = merge_waveform_segments(
                segments,
                sum_channels=False,
                dense=False,
                context=f"hit_merged_features merged_index={int(merged_index)}",
            )
            wave = merged_wave["waveform"]
            times = merged_wave["abs_time_ps"]
            if len(wave) == 0:
                continue
            max_index = int(np.argmax(wave))
            time_start = int(times[0])
            time_end = int(times[-1]) + int(merged_wave["dt"]) * 1000
            max_time = int(times[max_index])
            out[merged_index]["time_start"] = time_start
            out[merged_index]["time_end"] = time_end
            out[merged_index]["center_time"] = (time_start + time_end) // 2
            out[merged_index]["max_time"] = max_time
            out[merged_index]["area"] = np.sum(wave, dtype=np.float64)
            out[merged_index]["height"] = wave[max_index]
            out[merged_index]["width"] = (time_end - time_start) / 1000.0
            out[merged_index]["rise_time"] = (max_time - time_start) / 1000.0
            out[merged_index]["fall_time"] = (time_end - max_time) / 1000.0
            out[merged_index]["valid"] = 1

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
