"""
Basic Features Plugin - 基础特征计算插件

**加速器**: CPU (NumPy)
**功能**: 计算波形的基础特征（height/area）

本模块包含基础特征计算插件，从结构化波形中提取：
- height: 脉冲高度（baseline - min(wave)），信号偏离基线的幅度
- amp: 峰峰值振幅（max - min）
- area: 波形面积（积分）
- max_abs_diff: 波形相邻采样点差分绝对值最大值

支持可选的滤波波形输入，可配置计算范围。

设计原则：
- 逐条处理 record，支持任意长度波形
- 不使用 padding，避免 padding 影响 area 计算
- 内存占用最低，最适合 records streaming
- 通道配置缓存，避免重复解析
"""

from typing import Any

import numpy as np

from waveform_analysis.core.foundation.constants import FeatureDefaults
from waveform_analysis.core.hardware.channel import resolve_effective_channel_config
from waveform_analysis.core.plugins.builtin.cpu._wave_source import (
    WAVE_SOURCE_AUTO,
    load_wave_input,
    resolve_wave_input_spec,
)
from waveform_analysis.core.plugins.core.base import Option, Plugin

try:
    from numba import jit as _numba_jit

    NUMBA_AVAILABLE = True
except Exception:
    _numba_jit = None
    NUMBA_AVAILABLE = False


def _safe_slice(wave: np.ndarray, start: int | None, end: int | None) -> np.ndarray:
    """
    安全切片波形数组，自动处理边界情况

    Args:
        wave: 波形数组
        start: 起始索引（None 表示从头开始）
        end: 结束索引（None 表示到末尾）

    Returns:
        切片后的波形数组（如果范围无效则返回空数组）
    """
    n = len(wave)
    s = 0 if start is None else max(0, int(start))
    e = n if end is None else min(n, int(end))
    if e <= s:
        return wave[:0]  # 返回空数组
    return wave[s:e]


# 输出数据类型定义
BASIC_FEATURES_DTYPE = np.dtype(
    [
        ("height", "f4"),  # baseline - min(wave)，信号偏离基线的幅度
        ("amp", "f4"),  # max - min，峰峰值振幅
        ("area", "f4"),  # 波形积分面积
        ("max_abs_diff", "f4"),  # max(abs(diff(wave)))，最大差分绝对值
        ("timestamp", "i8"),  # ADC 时间戳 (ps)
        ("board", "i2"),  # 板卡编号
        ("channel", "i2"),  # 物理通道号
        ("record_id", "i8"),  # 记录 ID
    ]
)


def _compute_records_pool_kernel_python(
    wave_pool: np.ndarray,
    wave_offsets: np.ndarray,
    wave_lengths: np.ndarray,
    effective_baselines: np.ndarray,
    positive_mask: np.ndarray,
    sp0: int,
    ep_fixed: int,
    sc0: int,
    ec_fixed: int,
    compute_max_abs_diff: bool,
    height_out: np.ndarray,
    amp_out: np.ndarray,
    area_out: np.ndarray,
    maxdiff_out: np.ndarray,
) -> None:
    n_records = len(wave_offsets)
    pool_size = len(wave_pool)
    for idx in range(n_records):
        offset = int(wave_offsets[idx])
        n_wave = int(wave_lengths[idx])
        if offset < 0 or n_wave <= 0 or offset + n_wave > pool_size:
            continue

        baseline = float(effective_baselines[idx])
        is_positive = bool(positive_mask[idx])

        sp = sp0 if sp0 < n_wave else n_wave
        ep = n_wave if ep_fixed < 0 else min(n_wave, ep_fixed)

        if ep > sp:
            cursor = offset + sp
            stop = offset + ep
            w_min = float(wave_pool[cursor])
            w_max = w_min
            cursor += 1
            while cursor < stop:
                value = float(wave_pool[cursor])
                if value < w_min:
                    w_min = value
                if value > w_max:
                    w_max = value
                cursor += 1

            if is_positive:
                height_out[idx] = w_max - baseline
            else:
                height_out[idx] = baseline - w_min
            amp_out[idx] = w_max - w_min

        sc = sc0 if sc0 < n_wave else n_wave
        ec = n_wave if ec_fixed < 0 else min(n_wave, ec_fixed)

        if ec > sc:
            cursor = offset + sc
            stop = offset + ec
            total = 0.0
            while cursor < stop:
                total += float(wave_pool[cursor])
                cursor += 1

            n_area = ec - sc
            if is_positive:
                area_out[idx] = total - n_area * baseline
            else:
                area_out[idx] = n_area * baseline - total

        if compute_max_abs_diff and n_wave > 1:
            cursor = offset + 1
            stop = offset + n_wave
            previous = float(wave_pool[offset])
            max_abs_diff = 0.0
            while cursor < stop:
                current = float(wave_pool[cursor])
                diff = current - previous
                if diff < 0:
                    diff = -diff
                if diff > max_abs_diff:
                    max_abs_diff = diff
                previous = current
                cursor += 1
            maxdiff_out[idx] = max_abs_diff


if NUMBA_AVAILABLE:
    _compute_records_pool_kernel_numba = _numba_jit(nopython=True, cache=True)(
        _compute_records_pool_kernel_python
    )
else:
    _compute_records_pool_kernel_numba = None


class BasicFeaturesPlugin(Plugin):
    """Plugin to compute basic height/area features from structured waveforms."""

    provides = "basic_features"
    depends_on = []  # 动态依赖，由 resolve_depends_on 决定
    description = (
        "Compute basic height, amplitude, area, and max-abs-diff features from waveform data."
    )
    version = "4.1.0"  # 优化版本：逐条处理 + 通道配置缓存 + 适合 streaming
    save_when = "always"
    output_dtype = BASIC_FEATURES_DTYPE
    options = {
        "height_range": Option(
            default=FeatureDefaults.PEAK_RANGE, type=tuple, help="高度计算范围 (start, end)"
        ),
        "area_range": Option(
            default=(0, None),
            type=tuple,
            help="面积计算范围 (start, end)，end=None 表示积分到波形末端",
        ),
        "use_filtered": Option(
            default=False,
            type=bool,
            help="是否使用 filtered_waveforms（需要先注册 FilteredWaveformsPlugin）",
        ),
        "wave_source": Option(
            default=WAVE_SOURCE_AUTO,
            type=str,
            help="波形数据源: auto|records|st_waveforms|filtered_waveforms",
        ),
        "fixed_baseline": Option(
            default=None,
            type=dict,
            help="已废弃；按硬件通道固定 baseline 请改用 channel_config。",
        ),
        "channel_config": Option(
            default=None,
            type=dict,
            help="按 (board, channel) 的插件通道覆盖配置，可覆盖 fixed_baseline。",
        ),
        "compute_max_abs_diff": Option(
            default=True,
            type=bool,
            help="是否计算 max_abs_diff（关闭可减少一次全波形扫描，提升性能）",
        ),
        "batch_size": Option(
            default=10_000,
            type=int,
            help="批处理大小：当 records 数量超过此值时，分批处理以降低内存峰值",
        ),
    }

    def resolve_depends_on(self, context: Any, run_id: str | None = None) -> list[str]:
        """动态解析依赖项"""
        _ = run_id  # 参数保留用于接口一致性
        spec = resolve_wave_input_spec(context, self)
        return list(spec.depends_on)

    def compute(self, context: Any, run_id: str, **_kwargs) -> np.ndarray:
        """
        计算基础特征（height/amp/area/max_abs_diff）

        使用逐条处理模式，支持任意长度波形，不使用 padding。

        height = baseline - min(wave)  (信号偏离基线的幅度)
        amp = max - min  (峰峰值振幅)
        area = sum(baseline - wave)  (不包含 padding)
        max_abs_diff = max(abs(diff(wave)))

        Returns:
            np.ndarray: 结构化数组，包含 height/amp/area/max_abs_diff 字段
        """
        # 加载配置参数
        channel_config_cfg = context.get_config(self, "channel_config")
        height_range = context.get_config(self, "height_range")
        area_range = context.get_config(self, "area_range")
        compute_max_abs_diff = context.get_config(self, "compute_max_abs_diff")
        batch_size = int(context.get_config(self, "batch_size"))

        # 加载波形输入数据
        wave_input = load_wave_input(context, self, run_id, needs_wave_samples=True)

        # 解析计算范围
        start_p, end_p = height_range
        start_c, end_c = area_range

        # 处理 records 数据源（records-backed 波形）
        if wave_input.spec.is_records:
            records = wave_input.records
            rv = wave_input.records_view
            if records is None or rv is None:
                raise ValueError("basic_features failed to load records_view for records source")
            if len(records) == 0:
                return np.zeros(0, dtype=BASIC_FEATURES_DTYPE)

            record_names = records.dtype.names or ()
            boards = (
                records["board"]
                if "board" in record_names
                else np.zeros(len(records), dtype=np.int16)
            )
            channels = (
                records["channel"]
                if "channel" in record_names
                else np.zeros(len(records), dtype=np.int16)
            )
            channel_rule_cache = self._build_channel_rule_cache(
                context=context,
                run_id=run_id,
                boards=boards,
                channels=channels,
                channel_config_cfg=channel_config_cfg,
            )

            if (
                wave_input.wave_pool is not None
                and wave_input.wave_offsets is not None
                and wave_input.wave_lengths is not None
            ):
                return self._compute_records_pool_fast(
                    records=records,
                    wave_pool=wave_input.wave_pool,
                    wave_offsets=wave_input.wave_offsets,
                    wave_lengths=wave_input.wave_lengths,
                    start_p=start_p,
                    end_p=end_p,
                    start_c=start_c,
                    end_c=end_c,
                    channel_rule_cache=channel_rule_cache,
                    compute_max_abs_diff=compute_max_abs_diff,
                )

            # 大数据集使用批处理模式
            if len(records) > batch_size:
                return self._compute_records_batched(
                    context=context,
                    run_id=run_id,
                    records=records,
                    rv=rv,
                    start_p=start_p,
                    end_p=end_p,
                    start_c=start_c,
                    end_c=end_c,
                    channel_config_cfg=channel_config_cfg,
                    compute_max_abs_diff=compute_max_abs_diff,
                    batch_size=batch_size,
                )

            # 小数据集直接处理
            return self._compute_records_ragged_fast(
                records=records,
                rv=rv,
                start_p=start_p,
                end_p=end_p,
                start_c=start_c,
                end_c=end_c,
                channel_rule_cache=channel_rule_cache,
                compute_max_abs_diff=compute_max_abs_diff,
            )

        # 处理 waveform_data 数据源（st_waveforms / filtered_waveforms）
        return self._compute_from_waveform_data(
            context=context,
            run_id=run_id,
            wave_input=wave_input,
            start_p=start_p,
            end_p=end_p,
            start_c=start_c,
            end_c=end_c,
            channel_config_cfg=channel_config_cfg,
            compute_max_abs_diff=compute_max_abs_diff,
        )

    def _compute_records_pool_fast(
        self,
        records: np.ndarray,
        wave_pool: np.ndarray,
        wave_offsets: np.ndarray,
        wave_lengths: np.ndarray,
        start_p: int | None,
        end_p: int | None,
        start_c: int | None,
        end_c: int | None,
        channel_rule_cache: dict[tuple[int, int], dict],
        compute_max_abs_diff: bool,
    ) -> np.ndarray:
        """
        Compute records-backed features by scanning the contiguous wave_pool directly.

        This avoids RecordsView.waves() materialization and keeps Numba optional.
        """
        n_records = len(records)
        if n_records == 0:
            return np.zeros(0, dtype=BASIC_FEATURES_DTYPE)
        if len(wave_offsets) != n_records or len(wave_lengths) != n_records:
            raise ValueError("records wave_pool metadata length does not match records length")

        record_names = records.dtype.names or ()
        channels = (
            records["channel"].astype(np.int16, copy=False)
            if "channel" in record_names
            else np.zeros(n_records, dtype=np.int16)
        )
        boards = (
            records["board"].astype(np.int16, copy=False)
            if "board" in record_names
            else np.zeros(n_records, dtype=np.int16)
        )
        record_ids = (
            records["record_id"].astype(np.int64, copy=False)
            if "record_id" in record_names
            else np.arange(n_records, dtype=np.int64)
        )
        timestamps = (
            records["timestamp"].astype(np.int64, copy=False)
            if "timestamp" in record_names
            else np.zeros(n_records, dtype=np.int64)
        )
        baselines = (
            records["baseline"].astype(np.float64, copy=False)
            if "baseline" in record_names
            else np.zeros(n_records, dtype=np.float64)
        )

        effective_baselines = baselines.copy()
        for (board, ch), rule in channel_rule_cache.items():
            fixed_baseline = rule.get("fixed_baseline")
            if fixed_baseline is None:
                continue
            mask = (boards == int(board)) & (channels == int(ch))
            if np.any(mask):
                effective_baselines[mask] = float(fixed_baseline)

        if "polarity" in record_names:
            polarities = records["polarity"]
            if polarities.dtype.kind == "S":
                positive_mask = polarities == b"positive"
            else:
                positive_mask = np.asarray(polarities).astype("U16", copy=False) == "positive"
        else:
            positive_mask = np.zeros(n_records, dtype=bool)

        features = np.empty(n_records, dtype=BASIC_FEATURES_DTYPE)
        height_out = features["height"]
        amp_out = features["amp"]
        area_out = features["area"]
        maxdiff_out = features["max_abs_diff"]
        height_out.fill(0.0)
        amp_out.fill(0.0)
        area_out.fill(0.0)
        maxdiff_out.fill(0.0)
        features["timestamp"] = timestamps
        features["board"] = boards
        features["channel"] = channels
        features["record_id"] = record_ids

        sp0 = 0 if start_p is None else max(0, int(start_p))
        sc0 = 0 if start_c is None else max(0, int(start_c))
        ep_fixed = -1 if end_p is None else max(0, int(end_p))
        ec_fixed = -1 if end_c is None else max(0, int(end_c))

        kernel = _compute_records_pool_kernel_python
        if NUMBA_AVAILABLE and _compute_records_pool_kernel_numba is not None:
            kernel = _compute_records_pool_kernel_numba

        try:
            kernel(
                wave_pool,
                np.asarray(wave_offsets, dtype=np.int64),
                np.asarray(wave_lengths, dtype=np.int64),
                effective_baselines,
                np.asarray(positive_mask, dtype=np.bool_),
                sp0,
                ep_fixed,
                sc0,
                ec_fixed,
                bool(compute_max_abs_diff),
                height_out,
                amp_out,
                area_out,
                maxdiff_out,
            )
        except Exception:
            _compute_records_pool_kernel_python(
                wave_pool,
                np.asarray(wave_offsets, dtype=np.int64),
                np.asarray(wave_lengths, dtype=np.int64),
                effective_baselines,
                np.asarray(positive_mask, dtype=np.bool_),
                sp0,
                ep_fixed,
                sc0,
                ec_fixed,
                bool(compute_max_abs_diff),
                height_out,
                amp_out,
                area_out,
                maxdiff_out,
            )

        return features

    def _compute_records_ragged_fast(
        self,
        records: np.ndarray,
        rv: Any,
        start_p: int,
        end_p: int | None,
        start_c: int,
        end_c: int | None,
        channel_rule_cache: dict[tuple[int, int], dict],
        compute_max_abs_diff: bool,
        wave_query_batch_size: int = 512,
    ) -> np.ndarray:
        """
        从 records 数据源计算基础特征。

        特点
        ----
        - ragged-safe：支持不等长波形；
        - 按 record_id chunk 批量查询 wave，减少 rv.waves 调用次数；
        - 不假设 waves 是二维等长数组；
        - 不构造 baseline - wave 的完整临时数组；
        - fixed_baseline 按 channel 缓存，但普通 baseline 保持逐 record；
        - 输出 record_id 保留原始 records["record_id"]。
        """
        n_records = len(records)
        if n_records == 0:
            return np.zeros(0, dtype=BASIC_FEATURES_DTYPE)

        record_names = records.dtype.names or ()

        # ---------- metadata 预处理 ----------
        channels = (
            records["channel"].astype(np.int16, copy=False)
            if "channel" in record_names
            else np.zeros(n_records, dtype=np.int16)
        )

        boards = (
            records["board"].astype(np.int16, copy=False)
            if "board" in record_names
            else np.zeros(n_records, dtype=np.int16)
        )

        record_ids = (
            records["record_id"].astype(np.int64, copy=False)
            if "record_id" in record_names
            else np.arange(n_records, dtype=np.int64)
        )

        timestamps = (
            records["timestamp"].astype(np.int64, copy=False)
            if "timestamp" in record_names
            else np.zeros(n_records, dtype=np.int64)
        )

        baselines = (
            records["baseline"].astype(np.float64, copy=False)
            if "baseline" in record_names
            else np.zeros(n_records, dtype=np.float64)
        )

        # 如果 records 里有真实长度，后面可用于避免 padding 污染
        lengths = None
        for length_name in ("event_length", "length", "n_samples", "data_length"):
            if length_name in record_names:
                lengths = records[length_name].astype(np.int64, copy=False)
                break

        # ---------- effective baseline 预计算 ----------
        # 注意：只有 fixed_baseline 可以按 channel 覆盖。
        # 如果 fixed_baseline is None，必须保留每条 record 自己的 baseline。
        effective_baselines = baselines.copy()

        for (board, ch), rule in channel_rule_cache.items():
            fixed_baseline = rule.get("fixed_baseline")
            if fixed_baseline is None:
                continue

            mask = (boards == int(board)) & (channels == int(ch))
            if np.any(mask):
                effective_baselines[mask] = float(fixed_baseline)

        # ---------- polarity 预计算 ----------
        if "polarity" in record_names:
            polarities = records["polarity"]

            if polarities.dtype.kind == "S":
                positive_mask = polarities == b"positive"
            else:
                positive_mask = np.asarray(polarities).astype("U16", copy=False) == "positive"
        else:
            positive_mask = np.zeros(n_records, dtype=bool)

        # ---------- 输出预分配 ----------
        # 使用 empty 也可以，但必须显式初始化 feature 字段，否则短波形会留下随机值。
        features = np.empty(n_records, dtype=BASIC_FEATURES_DTYPE)

        height_out = features["height"]
        amp_out = features["amp"]
        area_out = features["area"]
        maxdiff_out = features["max_abs_diff"]

        height_out.fill(0.0)
        amp_out.fill(0.0)
        area_out.fill(0.0)
        maxdiff_out.fill(0.0)

        features["timestamp"] = timestamps
        features["board"] = boards
        features["channel"] = channels
        features["record_id"] = record_ids

        # ---------- 切片参数预处理 ----------
        # 这里默认 range 使用非负索引。若你需要支持负索引，需要额外处理。
        sp0 = 0 if start_p is None else max(0, int(start_p))
        sc0 = 0 if start_c is None else max(0, int(start_c))

        ep_fixed = None if end_p is None else max(0, int(end_p))
        ec_fixed = None if end_c is None else max(0, int(end_c))

        # 本地变量绑定，减少循环内属性查找
        waves_get = rv.waves
        baselines_arr = effective_baselines
        pos_arr = positive_mask
        ids_arr = record_ids

        if wave_query_batch_size <= 0:
            wave_query_batch_size = 1

        # ---------- 主循环：按 chunk 批量取 wave，逐条计算 ----------
        for b0 in range(0, n_records, wave_query_batch_size):
            b1 = min(b0 + wave_query_batch_size, n_records)
            ids_chunk = ids_arr[b0:b1]

            # records.waves 支持 record_id list / array，因此这里批量查询
            try:
                waves_chunk = waves_get(ids_chunk)
            except Exception:
                # 兜底：如果某些 RecordsView 实现不接受 ndarray
                waves_chunk = [waves_get(int(rid)) for rid in ids_chunk]

            # 如果返回单个 ndarray 且是一维，说明 batch_size 可能为 1 或接口返回异常形态
            if (
                isinstance(waves_chunk, np.ndarray)
                and waves_chunk.ndim == 1
                and len(ids_chunk) == 1
            ):
                waves_iter = (waves_chunk,)
            else:
                waves_iter = waves_chunk

            for local_idx, wave in enumerate(waves_iter):
                idx = b0 + local_idx

                # 防御：如果 waves_chunk 比 ids_chunk 短，避免越界
                if idx >= b1:
                    break

                wave = np.asarray(wave)
                if wave.size == 0:
                    continue

                # 如果有真实长度字段，用真实长度裁剪，避免 padding 污染。
                if lengths is not None:
                    n_wave = int(lengths[idx])
                    if n_wave < 0:
                        n_wave = 0
                    elif n_wave > wave.size:
                        n_wave = wave.size
                else:
                    n_wave = wave.size

                if n_wave <= 0:
                    continue

                baseline = baselines_arr[idx]
                is_positive = pos_arr[idx]

                # ---------- height / amp ----------
                sp = sp0 if sp0 < n_wave else n_wave
                ep = n_wave if ep_fixed is None else min(n_wave, ep_fixed)

                if ep > sp:
                    wave_p = wave[sp:ep]
                    w_min = float(np.min(wave_p))
                    w_max = float(np.max(wave_p))

                    if is_positive:
                        height_out[idx] = w_max - baseline
                    else:
                        height_out[idx] = baseline - w_min

                    amp_out[idx] = w_max - w_min

                # ---------- area ----------
                sc = sc0 if sc0 < n_wave else n_wave
                ec = n_wave if ec_fixed is None else min(n_wave, ec_fixed)

                if ec > sc:
                    wave_c = wave[sc:ec]
                    sum_c = np.sum(wave_c, dtype=np.float64)
                    n_c = ec - sc

                    if is_positive:
                        area_out[idx] = sum_c - n_c * baseline
                    else:
                        area_out[idx] = n_c * baseline - sum_c

                # ---------- max_abs_diff ----------
                if compute_max_abs_diff and n_wave > 1:
                    wave_d = wave[:n_wave]

                    # ADC 常见 uint16/int16。统一转 int32，避免 uint 下溢或 int16 溢出。
                    if np.issubdtype(wave_d.dtype, np.integer):
                        wave_d = wave_d.astype(np.int32, copy=False)

                    diff = wave_d[1:] - wave_d[:-1]

                    # 对整数 diff 可原地 abs，少一个临时数组
                    if np.issubdtype(diff.dtype, np.integer):
                        np.abs(diff, out=diff)
                        maxdiff_out[idx] = np.max(diff)
                    else:
                        maxdiff_out[idx] = np.max(np.abs(diff))

        return features

    def _compute_records_batched(
        self,
        context: Any,
        run_id: str,
        records: np.ndarray,
        rv: Any,
        start_p: int,
        end_p: int | None,
        start_c: int,
        end_c: int | None,
        channel_config_cfg: Any,
        compute_max_abs_diff: bool,
        batch_size: int,
    ) -> np.ndarray:
        """
        批处理模式处理 records 数据源

        使用预分配 + 分段填入，避免 concatenate 开销。

        Args:
            context: 上下文对象
            run_id: 运行 ID
            records: 记录数组
            rv: RecordsView 对象
            start_p, end_p: height 计算范围
            start_c, end_c: area 计算范围
            channel_config_cfg: 通道配置
            compute_max_abs_diff: 是否计算 max_abs_diff
            batch_size: 批处理大小

        Returns:
            特征数组
        """
        n_records = len(records)

        # 预分配完整输出数组
        features = np.empty(n_records, dtype=BASIC_FEATURES_DTYPE)

        # 构建通道配置缓存（只构建一次）
        record_names = records.dtype.names or ()
        boards = (
            records["board"] if "board" in record_names else np.zeros(n_records, dtype=np.int16)
        )
        channels = (
            records["channel"] if "channel" in record_names else np.zeros(n_records, dtype=np.int16)
        )

        channel_rule_cache = self._build_channel_rule_cache(
            context=context,
            run_id=run_id,
            boards=boards,
            channels=channels,
            channel_config_cfg=channel_config_cfg,
        )

        # 分批处理，直接填入预分配的数组
        for start_idx in range(0, n_records, batch_size):
            end_idx = min(start_idx + batch_size, n_records)
            chunk_records = records[start_idx:end_idx]

            # 处理当前批次
            chunk_features = self._compute_records_ragged_fast(
                records=chunk_records,
                rv=rv,
                start_p=start_p,
                end_p=end_p,
                start_c=start_c,
                end_c=end_c,
                channel_rule_cache=channel_rule_cache,
                compute_max_abs_diff=compute_max_abs_diff,
            )

            # 直接填入预分配的数组（避免 concatenate）
            features[start_idx:end_idx] = chunk_features

        return features

    def _compute_from_waveform_data(
        self,
        context: Any,
        run_id: str,
        wave_input: Any,
        start_p: int,
        end_p: int | None,
        start_c: int,
        end_c: int | None,
        channel_config_cfg: Any,
        compute_max_abs_diff: bool,
    ) -> np.ndarray:
        """
        从 waveform_data 数据源计算特征（逐条处理模式）

        注意：waveform_data 通常是等长的二维数组，但这里仍使用逐条处理
        以保持与 records 分支的一致性。

        Args:
            context: 上下文对象
            run_id: 运行 ID
            wave_input: 波形输入对象
            start_p, end_p: height 计算范围
            start_c, end_c: area 计算范围
            channel_config_cfg: 通道配置
            compute_max_abs_diff: 是否计算 max_abs_diff

        Returns:
            特征数组
        """
        waveform_data = wave_input.waveform_data
        if waveform_data is None:
            raise ValueError(f"basic_features failed to load {wave_input.spec.expected_name}")
        if len(waveform_data) == 0:
            return np.zeros(0, dtype=BASIC_FEATURES_DTYPE)

        waveform_names = waveform_data.dtype.names or ()
        n_events = len(waveform_data)

        # 提取元数据字段
        waves = waveform_data["wave"]
        baselines = waveform_data["baseline"] if "baseline" in waveform_names else None
        timestamps = (
            waveform_data["timestamp"].astype(np.int64, copy=False)
            if "timestamp" in waveform_names
            else np.zeros(n_events, dtype=np.int64)
        )
        boards = (
            waveform_data["board"].astype(np.int16, copy=False)
            if "board" in waveform_names
            else np.zeros(n_events, dtype=np.int16)
        )
        channels = (
            waveform_data["channel"].astype(np.int16, copy=False)
            if "channel" in waveform_names
            else np.zeros(n_events, dtype="i2")
        )
        record_ids = (
            waveform_data["record_id"].astype(np.int64, copy=False)
            if "record_id" in waveform_names
            else np.arange(n_events, dtype=np.int64)
        )
        polarities = waveform_data["polarity"] if "polarity" in waveform_names else None

        # 构建通道配置缓存
        channel_rule_cache = self._build_channel_rule_cache(
            context=context,
            run_id=run_id,
            boards=boards,
            channels=channels,
            channel_config_cfg=channel_config_cfg,
        )

        # 初始化输出数组
        features = np.zeros(n_events, dtype=BASIC_FEATURES_DTYPE)

        # 逐条处理每个事件
        for idx in range(n_events):
            wave = waves[idx]
            board = int(boards[idx])
            ch = int(channels[idx])
            rid = int(record_ids[idx])
            timestamp = int(timestamps[idx])
            baseline = float(baselines[idx]) if baselines is not None else float(np.mean(wave))

            # 从缓存中获取通道配置
            channel_key = (board, ch)
            rule = channel_rule_cache.get(channel_key, {})
            fixed_baseline = rule.get("fixed_baseline")
            if fixed_baseline is not None:
                baseline = float(fixed_baseline)

            # 确定极性
            polarity = str(polarities[idx]) if polarities is not None else "negative"
            if polarity not in ("positive", "negative"):
                polarity = "negative"

            # 安全切片：height/amp 计算范围
            wave_p = _safe_slice(wave, start_p, end_p)
            if wave_p.size > 0:
                w_min = float(np.min(wave_p))
                w_max = float(np.max(wave_p))

                if polarity == "positive":
                    features["height"][idx] = w_max - baseline
                else:
                    features["height"][idx] = baseline - w_min

                features["amp"][idx] = w_max - w_min

            # 安全切片：area 计算范围
            wave_c = _safe_slice(wave, start_c, end_c)
            if wave_c.size > 0:
                sum_c = np.sum(wave_c, dtype=np.float64)
                n_c = wave_c.size

                if polarity == "positive":
                    features["area"][idx] = sum_c - n_c * baseline
                else:
                    features["area"][idx] = n_c * baseline - sum_c

            # 可选计算 max_abs_diff
            if compute_max_abs_diff and wave.size > 1:
                wave_i = wave.astype(np.int32, copy=False)
                features["max_abs_diff"][idx] = np.max(np.abs(np.diff(wave_i)))

            # 填充元数据
            features["timestamp"][idx] = timestamp
            features["board"][idx] = board
            features["channel"][idx] = ch
            features["record_id"][idx] = rid

        return features

    def _build_channel_rule_cache(
        self,
        context: Any,
        run_id: str,
        boards: np.ndarray,
        channels: np.ndarray,
        channel_config_cfg: Any,
    ) -> dict[tuple[int, int], dict]:
        """
        构建通道配置缓存

        避免对相同的 (board, channel) 重复调用 resolve_effective_channel_config。

        Args:
            context: 上下文对象
            run_id: 运行 ID
            boards: 板卡编号数组
            channels: 通道编号数组
            channel_config_cfg: 通道配置

        Returns:
            通道配置缓存字典 {(board, channel): rule_values}
        """
        channel_rule_cache: dict[tuple[int, int], dict] = {}
        base_values = {"fixed_baseline": None}

        # 获取所有唯一的 (board, channel) 组合
        unique_channels = set(zip(boards.tolist(), channels.tolist(), strict=False))

        # 为每个唯一通道解析配置
        for board, channel in unique_channels:
            channel_key = (int(board), int(channel))
            rule = resolve_effective_channel_config(
                context=context,
                plugin=self,
                run_id=run_id,
                board=channel_key[0],
                channel=channel_key[1],
                base_values=base_values,
                channel_config=channel_config_cfg,
            )
            channel_rule_cache[channel_key] = rule.values

        return channel_rule_cache


__all__ = ["BasicFeaturesPlugin", "BASIC_FEATURES_DTYPE"]
