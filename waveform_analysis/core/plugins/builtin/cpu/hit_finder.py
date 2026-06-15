"""
Hit Finder Plugins - 阈值 Hit 检测插件

本模块包含：
1. HitFinderPlugin: 旧导入路径兼容别名（推荐改为 peak_finding.HitFinderPlugin）
2. ThresholdHitPlugin: 新的纯阈值 hit 插件（provides='hit_threshold'），输出 THRESHOLD_HIT_DTYPE

本版本的主要改动
----------------
1. records 输入路径优先使用 ragged layout：wave_pool + wave_offset + event_length。
2. 对每条 record 先做 min/max record-level prefilter：
   - positive polarity: max(wave) >= baseline + threshold
   - negative polarity: min(wave) <= baseline - threshold
   未通过预筛选的 record 不构造 mask、不找 hit 区间。
3. records 路径不再强制调用 rv.waves(...) 生成 padded 2D matrix，适合不等长波形。
4. waveform matrix 输入路径仍然保留，用于 st_waveforms / filtered_waveforms 等固定窗口数据。
"""

from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
import logging
import os
from typing import Any
import warnings

import numpy as np

from waveform_analysis.core.hardware.channel import resolve_effective_channel_config
from waveform_analysis.core.plugins.builtin.cpu._dt_compat import (
    require_dt_array,
    resolve_dt_config,
)
from waveform_analysis.core.plugins.builtin.cpu._wave_source import (
    WAVE_SOURCE_AUTO,
    WAVE_SOURCE_RECORDS,
    load_wave_input,
    resolve_wave_input_spec,
)
from waveform_analysis.core.plugins.builtin.cpu.peak_finding import (
    HitFinderPlugin as _CanonicalHitFinderPlugin,
)
from waveform_analysis.core.plugins.core.base import Option
from waveform_analysis.core.plugins.core.batch_processing import BatchProcessingPlugin
from waveform_analysis.core.processing.chunk import Chunk

logger = logging.getLogger(__name__)
_NUMBA_AVAILABLE: bool | None = None
_NUMBA_IMPORT_ERROR: Exception | None = None
_numba_count_ragged_hits = None
_numba_fill_ragged_hits = None
_numba_batch_prefilter = None
_numba_contiguous_regions = None

THRESHOLD_HIT_DTYPE = np.dtype(
    [
        ("position", "i8"),  # hit 区间代表位置（采样点索引）
        ("edge_start", "i4"),  # 命中窗口起始边界（record 内安全半开样本起点）
        ("edge_end", "i4"),  # 命中窗口结束边界（record 内安全半开样本终点）
        ("width", "f4"),  # 命中窗口宽度（采样点）
        ("dt", "i4"),  # 采样间隔（ns）
        ("timestamp", "i8"),  # position 对应全局时间戳（ps）
        ("board", "i2"),  # 板卡编号
        ("channel", "i2"),  # 通道号
        ("record_id", "i8"),  # 来源波形/记录的唯一编号
    ]
)


def _empty_hits() -> np.ndarray:
    return np.zeros(0, dtype=THRESHOLD_HIT_DTYPE)


def _build_record_lookup(records: np.ndarray) -> dict[int, tuple[int, int]]:
    return {
        int(rec["record_id"]): (int(rec["wave_offset"]), int(rec["event_length"]))
        for rec in records
    }


def _resolve_source_event_lengths(waveform_data: np.ndarray) -> np.ndarray:
    names = waveform_data.dtype.names or ()
    if "event_length" in names:
        return waveform_data["event_length"].astype(np.int64, copy=False)
    if "wave" in names:
        return np.full(len(waveform_data), waveform_data["wave"].shape[1], dtype=np.int64)
    raise ValueError("waveform source is missing both 'event_length' and 'wave' fields")


def _contiguous_regions_from_indices(indices: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Return half-open contiguous regions represented by sorted sample indices.

    优先使用 Numba 加速版本，fallback 到 NumPy 实现。
    """
    if indices.size == 0:
        return indices, indices

    # 尝试使用 Numba 加速版本
    if _numba_contiguous_regions is not None:
        try:
            return _numba_contiguous_regions(indices)
        except Exception:
            # Fallback 到 NumPy 实现
            pass

    # NumPy fallback 实现
    split_points = np.flatnonzero(np.diff(indices) > 1) + 1
    starts = np.empty(split_points.size + 1, dtype=np.int64)
    ends = np.empty(split_points.size + 1, dtype=np.int64)
    starts[0] = indices[0]
    starts[1:] = indices[split_points]
    ends[:-1] = indices[split_points - 1] + 1
    ends[-1] = indices[-1] + 1
    return starts, ends


def _get_wave_pool_from_object(obj: Any) -> np.ndarray | None:
    """Best-effort extraction of wave_pool from RecordsView / RecordsBundle-like objects."""
    if obj is None:
        return None
    if hasattr(obj, "wave_pool"):
        return np.asarray(obj.wave_pool)
    if hasattr(obj, "_wave_pool"):
        return np.asarray(obj._wave_pool)
    return None


def _ensure_numba_kernels() -> None:
    global _NUMBA_AVAILABLE
    global _NUMBA_IMPORT_ERROR
    global _numba_count_ragged_hits
    global _numba_fill_ragged_hits
    global _numba_batch_prefilter
    global _numba_contiguous_regions

    if _NUMBA_AVAILABLE is False:
        raise RuntimeError("numba is not available") from _NUMBA_IMPORT_ERROR
    if (
        _numba_count_ragged_hits is not None
        and _numba_fill_ragged_hits is not None
        and _numba_batch_prefilter is not None
        and _numba_contiguous_regions is not None
    ):
        return

    try:
        from waveform_analysis.core.plugins.builtin.cpu.hit_threshold_numba import (
            batch_prefilter_records,
            contiguous_regions_numba,
            count_ragged_hits,
            fill_ragged_hits,
        )
    except Exception as exc:  # pragma: no cover - depends on environment import state
        _NUMBA_AVAILABLE = False
        _NUMBA_IMPORT_ERROR = exc
        raise RuntimeError("numba is not available") from exc

    _numba_count_ragged_hits = count_ragged_hits
    _numba_fill_ragged_hits = fill_ragged_hits
    _numba_batch_prefilter = batch_prefilter_records
    _numba_contiguous_regions = contiguous_regions_numba
    _NUMBA_AVAILABLE = True


class HitFinderPlugin(_CanonicalHitFinderPlugin):
    """Deprecated import-path alias for peak_finding.HitFinderPlugin."""

    def __init__(self, *args, **kwargs):
        warnings.warn(
            "Importing HitFinderPlugin from "
            "waveform_analysis.core.plugins.builtin.cpu.hit_finder is deprecated; "
            "use waveform_analysis.core.plugins.builtin.cpu (or .peak_finding) instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        super().__init__(*args, **kwargs)


class ThresholdHitPlugin(BatchProcessingPlugin):
    """Threshold-only hit detector with THRESHOLD_HIT_DTYPE output.

    records 输入路径采用 ragged wave_pool 扫描，避免不等长波形被强制 padding 成二维矩阵。
    """

    provides = "hit_threshold"
    depends_on = []  # 动态依赖，由 resolve_depends_on 决定
    description = "Threshold-only hit detector with THRESHOLD_HIT_DTYPE output."
    version = "1.1.0"
    output_dtype = THRESHOLD_HIT_DTYPE

    # 为了不改变原始缓存语义，这里仍保持 always。
    # 如果 hit_threshold 只是中间产物，可改为 save_when = "target" 进一步减少写盘。
    save_when = "always"

    # 保持原默认值，避免改变框架调度行为。
    # 若 CPU/内存带宽瓶颈明显，可在确认结果一致后尝试 parallel=False, chunk_size=20_000~50_000。
    chunk_size = 10_000
    parallel = True
    executor_type = "thread"

    options = {
        "threshold": Option(default=10.0, type=float, help="Hit 检测阈值"),
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
        "left_extension": Option(default=2, type=int, help="Hit 左侧扩展点数"),
        "right_extension": Option(default=2, type=int, help="Hit 右侧扩展点数"),
        "dt": Option(
            default=None,
            type=int,
            help="采样间隔（ns）。仅在输入数据缺少 dt 字段时作为兼容补充。",
        ),
        "channel_config": Option(
            default=None,
            type=dict,
            help="按 (board, channel) 的插件通道覆盖配置，可覆盖 threshold。",
        ),
        "backend": Option(
            default="auto",
            type=str,
            help=(
                "Hit finding backend: auto|numba|ragged。auto 对 records 在达到 "
                "parallel_min_records 后尝试 numba，否则使用 ragged。"
            ),
        ),
        "chunk_parallel": Option(
            default=True,
            type=bool,
            help="是否对 records ragged numba 后端启用 chunk 级线程并行。",
        ),
        "n_workers": Option(
            default=0,
            type=int,
            help="records ragged chunk 并行 worker 数；<=0 表示自动。",
        ),
        "parallel_chunk_size": Option(
            default=50_000,
            type=int,
            help="records ragged chunk 并行大小（每个任务处理的 record 数）。",
        ),
        "parallel_min_records": Option(
            default=50_000,
            type=int,
            help="触发 records ragged chunk 并行的最小 record 数。",
        ),
        "streaming_chunk_size": Option(
            default=10_000,
            type=int,
            help="流式处理时的 chunk 大小（仅对 RecordsBundleRef 生效）",
        ),
        "asymmetry_cut_enabled": Option(
            default=False,
            type=bool,
            help="是否在 records 路径的 hit 查找前应用 records_asymmetry_mask。",
        ),
    }

    def resolve_depends_on(self, context: Any, run_id: str | None = None) -> list[str]:
        spec = resolve_wave_input_spec(context, self)
        deps = list(spec.depends_on)
        if (
            spec.source == WAVE_SOURCE_RECORDS
            and bool(context.get_config(self, "asymmetry_cut_enabled"))
            and "records_asymmetry_mask" not in deps
        ):
            deps.append("records_asymmetry_mask")
        return deps

    def compute_chunk(self, chunk: Chunk, context: Any, run_id: str, **kwargs) -> Chunk:
        """处理单个 chunk - 由 StreamingPlugin 框架自动调用。"""
        threshold = float(context.get_config(self, "threshold"))
        left_extension = max(0, int(context.get_config(self, "left_extension")))
        right_extension = max(0, int(context.get_config(self, "right_extension")))
        explicit_dt = resolve_dt_config(
            context, self, deprecated_keys=("sampling_interval_ns", "dt_ns")
        )
        channel_config_cfg = context.get_config(self, "channel_config")

        data = chunk.data
        if len(data) == 0:
            return Chunk(
                data=_empty_hits(),
                start=chunk.start,
                end=chunk.end,
                run_id=run_id,
                data_type=self.provides,
            )

        hits = self._process_chunk_data(
            data=data,
            context=context,
            run_id=run_id,
            threshold=threshold,
            left_extension=left_extension,
            right_extension=right_extension,
            explicit_dt=explicit_dt,
            channel_config_cfg=channel_config_cfg,
        )

        if len(hits) > 0:
            hit_start = int(hits["timestamp"].min())
            hit_end = int(hits["timestamp"].max() + hits["dt"].max() * hits["width"].max())
            actual_start = min(chunk.start, hit_start)
            actual_end = max(chunk.end, hit_end)
        else:
            actual_start = chunk.start
            actual_end = chunk.end

        return Chunk(
            data=hits,
            start=actual_start,
            end=actual_end,
            run_id=run_id,
            data_type=self.provides,
        )

    def compute(self, context: Any, run_id: str, **kwargs) -> np.ndarray:
        return self.compute_array(context, run_id, **kwargs)

    def compute_array(self, context: Any, run_id: str, **_kwargs) -> np.ndarray:
        """返回完整 hit interval 数组；BatchProcessing chunk 接口仅作为内部扩展保留。"""
        threshold = float(context.get_config(self, "threshold"))
        left_extension = max(0, int(context.get_config(self, "left_extension")))
        right_extension = max(0, int(context.get_config(self, "right_extension")))
        explicit_dt = resolve_dt_config(
            context, self, deprecated_keys=("sampling_interval_ns", "dt_ns")
        )
        channel_config_cfg = context.get_config(self, "channel_config")
        wave_input = load_wave_input(
            context,
            self,
            run_id,
            needs_wave_samples=True,
            allow_records_bundle_ref=True,
        )

        if wave_input.spec.is_records:
            from waveform_analysis.core.processing.records_builder import RecordsBundleRef

            if isinstance(wave_input.records, RecordsBundleRef):
                return self._compute_streaming(
                    context=context,
                    run_id=run_id,
                    bundle_ref=wave_input.records,
                    threshold=threshold,
                    left_extension=left_extension,
                    right_extension=right_extension,
                    explicit_dt=explicit_dt,
                    channel_config_cfg=channel_config_cfg,
                )
            if wave_input.records is None or wave_input.wave_pool is None:
                raise ValueError(
                    "hit_threshold failed to load records and wave_pool for records source"
                )
            records = wave_input.records
            if bool(context.get_config(self, "asymmetry_cut_enabled")):
                mask = np.asarray(
                    context.get_data(run_id, "records_asymmetry_mask"),
                    dtype=np.bool_,
                )
                if len(mask) != len(records):
                    raise ValueError(
                        "records_asymmetry_mask length mismatch: "
                        f"mask has {len(mask)} entries, records has {len(records)}"
                    )
                records = records[mask]
                if len(records) == 0:
                    return _empty_hits()
            return self._process_records_ragged_input(
                records=records,
                wave_pool=wave_input.wave_pool,
                context=context,
                run_id=run_id,
                threshold=threshold,
                left_extension=left_extension,
                right_extension=right_extension,
                explicit_dt=explicit_dt,
                channel_config_cfg=channel_config_cfg,
            )

        if wave_input.waveform_data is None:
            raise ValueError(f"hit_threshold failed to load {wave_input.spec.expected_name}")
        return self._process_waveform_matrix_input(
            data=wave_input.waveform_data,
            context=context,
            run_id=run_id,
            threshold=threshold,
            left_extension=left_extension,
            right_extension=right_extension,
            explicit_dt=explicit_dt,
            channel_config_cfg=channel_config_cfg,
        )

    # -------------------------------------------------------------------------
    # Public compute paths
    # -------------------------------------------------------------------------

    def _process_chunk_data(
        self,
        data: np.ndarray,
        context: Any,
        run_id: str,
        threshold: float,
        left_extension: int,
        right_extension: int,
        explicit_dt: int | None,
        channel_config_cfg: Any,
    ) -> np.ndarray:
        """处理单个 chunk 的数据并计算 hits。"""
        if len(data) == 0:
            return _empty_hits()

        data_names = data.dtype.names or ()
        is_records = "wave_offset" in data_names

        if is_records:
            from waveform_analysis.core.plugins.builtin.cpu.records import get_records_bundle

            bundle = get_records_bundle(context, run_id)
            wave_pool = _get_wave_pool_from_object(getattr(bundle, "records_view", None))
            if wave_pool is None:
                wave_pool = _get_wave_pool_from_object(bundle)
            if wave_pool is None:
                raise ValueError(
                    "hit_threshold records input requires a wave_pool, but none was found"
                )

            return self._process_records_ragged_input(
                records=data,
                wave_pool=wave_pool,
                context=context,
                run_id=run_id,
                threshold=threshold,
                left_extension=left_extension,
                right_extension=right_extension,
                explicit_dt=explicit_dt,
                channel_config_cfg=channel_config_cfg,
            )

        return self._process_waveform_matrix_input(
            data=data,
            context=context,
            run_id=run_id,
            threshold=threshold,
            left_extension=left_extension,
            right_extension=right_extension,
            explicit_dt=explicit_dt,
            channel_config_cfg=channel_config_cfg,
        )

    def _compute_records_batched(
        self,
        context: Any,
        run_id: str,
        records: np.ndarray,
        rv: Any,
        threshold: float,
        left_extension: int,
        right_extension: int,
        explicit_dt: int | None,
        channel_config_cfg: Any,
        chunk_size: int,
    ) -> np.ndarray:
        """批处理 records；每批直接用 wave_pool ragged 扫描，不构造 padded matrix。"""
        n_records = len(records)
        if n_records == 0:
            return _empty_hits()

        wave_pool = _get_wave_pool_from_object(rv)
        if wave_pool is None:
            raise ValueError("hit_threshold records batched path requires rv.wave_pool")

        all_hits = []
        for start_idx in range(0, n_records, chunk_size):
            end_idx = min(start_idx + chunk_size, n_records)
            chunk_records = records[start_idx:end_idx]

            chunk_hits = self._process_records_ragged_input(
                records=chunk_records,
                wave_pool=wave_pool,
                context=context,
                run_id=run_id,
                threshold=threshold,
                left_extension=left_extension,
                right_extension=right_extension,
                explicit_dt=explicit_dt,
                channel_config_cfg=channel_config_cfg,
            )

            if len(chunk_hits) > 0:
                all_hits.append(chunk_hits)

            logger.debug(
                "hit_threshold: processed ragged batch %s-%s, found %s hits",
                start_idx,
                end_idx,
                len(chunk_hits),
            )

        if not all_hits:
            return _empty_hits()
        return np.concatenate(all_hits)

    def _compute_streaming(
        self,
        context: Any,
        run_id: str,
        bundle_ref: Any,  # RecordsBundleRef
        threshold: float,
        left_extension: int,
        right_extension: int,
        explicit_dt: int | None,
        channel_config_cfg: Any,
    ) -> np.ndarray:
        """流式处理 RecordsBundleRef。"""
        chunk_size = int(context.get_config(self, "streaming_chunk_size"))
        all_hits = []
        total_processed = 0
        log_interval = chunk_size * 10

        for chunk_bundle in bundle_ref.iter_chunks(chunk_size=chunk_size):
            chunk_hits = self._process_chunk(
                context=context,
                run_id=run_id,
                chunk_bundle=chunk_bundle,
                threshold=threshold,
                left_extension=left_extension,
                right_extension=right_extension,
                explicit_dt=explicit_dt,
                channel_config_cfg=channel_config_cfg,
            )
            if len(chunk_hits) > 0:
                all_hits.append(chunk_hits)
            total_processed += len(chunk_bundle.records)

            if total_processed % log_interval == 0:
                total_hits = sum(len(h) for h in all_hits)
                logger.info(
                    "hit_threshold: processed %s/%s records, found %s hits",
                    total_processed,
                    bundle_ref.total_records,
                    total_hits,
                )

        if all_hits:
            result = np.concatenate(all_hits)
            logger.info("hit_threshold: streaming mode completed, total hits: %s", len(result))
            return result
        return _empty_hits()

    def _process_chunk(
        self,
        context: Any,
        run_id: str,
        chunk_bundle: Any,  # RecordsBundle
        threshold: float,
        left_extension: int,
        right_extension: int,
        explicit_dt: int | None,
        channel_config_cfg: Any,
    ) -> np.ndarray:
        """处理 RecordsBundle chunk；chunk_bundle.records 的 wave_offset 通常已相对 chunk wave_pool。"""
        records = chunk_bundle.records
        if len(records) == 0:
            return _empty_hits()

        wave_pool = _get_wave_pool_from_object(chunk_bundle)
        if wave_pool is None:
            raise ValueError("hit_threshold streaming chunk requires chunk_bundle.wave_pool")

        return self._process_records_ragged_input(
            records=records,
            wave_pool=wave_pool,
            context=context,
            run_id=run_id,
            threshold=threshold,
            left_extension=left_extension,
            right_extension=right_extension,
            explicit_dt=explicit_dt,
            channel_config_cfg=channel_config_cfg,
        )

    # -------------------------------------------------------------------------
    # Metadata extraction
    # -------------------------------------------------------------------------

    def _extract_records_ragged_metadata(
        self,
        records: np.ndarray,
        explicit_dt: int | None,
    ) -> tuple[
        np.ndarray,  # wave_offsets
        np.ndarray,  # record_lengths
        np.ndarray,  # baselines
        np.ndarray,  # timestamps
        np.ndarray,  # boards
        np.ndarray,  # channels
        np.ndarray,  # record_ids
        np.ndarray | None,  # data_polarities
        np.ndarray,  # dt_values
    ]:
        if len(records) == 0:
            return (
                np.zeros(0, dtype=np.int64),
                np.zeros(0, dtype=np.int64),
                np.zeros(0, dtype=np.float32),
                np.zeros(0, dtype=np.int64),
                np.zeros(0, dtype=np.int16),
                np.zeros(0, dtype=np.int16),
                np.zeros(0, dtype=np.int64),
                None,
                np.zeros(0, dtype=np.int64),
            )

        record_names = records.dtype.names or ()
        required = ("wave_offset", "event_length", "baseline", "timestamp")
        missing = [name for name in required if name not in record_names]
        if missing:
            raise ValueError(f"hit_threshold records input missing required fields: {missing}")

        wave_offsets = records["wave_offset"].astype(np.int64, copy=False)
        record_lengths = records["event_length"].astype(np.int64, copy=False)
        baselines = records["baseline"].astype(np.float32, copy=False)
        timestamps = records["timestamp"].astype(np.int64, copy=False)
        boards = (
            records["board"].astype(np.int16, copy=False)
            if "board" in record_names
            else np.zeros(len(records), dtype=np.int16)
        )
        channels = (
            records["channel"].astype(np.int16, copy=False)
            if "channel" in record_names
            else np.zeros(len(records), dtype=np.int16)
        )
        record_ids = (
            records["record_id"].astype(np.int64, copy=False)
            if "record_id" in record_names
            else np.arange(len(records), dtype=np.int64)
        )
        data_polarities = (
            np.asarray(records["polarity"]).astype("U16", copy=False)
            if "polarity" in record_names
            else None
        )
        dt_values = require_dt_array(
            records,
            explicit_dt=explicit_dt,
            plugin_name=self.provides,
            data_name="records",
        )

        return (
            wave_offsets,
            record_lengths,
            baselines,
            timestamps,
            boards,
            channels,
            record_ids,
            data_polarities,
            dt_values,
        )

    def _extract_records_metadata(
        self,
        records: np.ndarray,
        rv: Any,
        explicit_dt: int | None,
    ) -> tuple[
        np.ndarray,
        np.ndarray,
        np.ndarray,
        np.ndarray,
        np.ndarray,
        np.ndarray,
        np.ndarray,
        np.ndarray | None,
        np.ndarray,
        np.ndarray,
    ]:
        """保留旧 matrix metadata 提取接口，便于回归比较或未来 bucketed matrix backend 使用。"""
        if len(records) == 0:
            empty = np.zeros(0, dtype=np.float32)
            return (
                np.zeros((0, 0), dtype=np.float32),
                np.zeros((0, 0), dtype=bool),
                empty,
                np.zeros(0, dtype=np.int64),
                np.zeros(0, dtype=np.int16),
                np.zeros(0, dtype=np.int16),
                np.zeros(0, dtype=np.int64),
                None,
                np.zeros(0, dtype=np.int64),
                np.zeros(0, dtype=np.int64),
            )

        record_names = records.dtype.names or ()
        record_ids_for_view = (
            records["record_id"].astype(np.int64, copy=False)
            if "record_id" in record_names
            else np.arange(len(records), dtype=np.int64)
        )

        waves, valid_mask = rv.waves(record_ids_for_view, mask=True, dtype=np.float32)
        (
            _wave_offsets,
            record_lengths,
            baselines,
            timestamps,
            boards,
            channels,
            record_ids,
            data_polarities,
            dt_values,
        ) = self._extract_records_ragged_metadata(records, explicit_dt)

        return (
            waves,
            valid_mask,
            baselines,
            timestamps,
            boards,
            channels,
            record_ids,
            data_polarities,
            dt_values,
            record_lengths,
        )

    # -------------------------------------------------------------------------
    # Core backends
    # -------------------------------------------------------------------------

    def _process_records_ragged_input(
        self,
        records: np.ndarray,
        wave_pool: np.ndarray,
        context: Any,
        run_id: str,
        threshold: float,
        left_extension: int,
        right_extension: int,
        explicit_dt: int | None,
        channel_config_cfg: Any,
    ) -> np.ndarray:
        """records 输入的 ragged 核心路径。"""
        if len(records) == 0:
            return _empty_hits()

        (
            wave_offsets,
            record_lengths,
            baselines,
            timestamps,
            boards,
            channels,
            record_ids,
            data_polarities,
            dt_values,
        ) = self._extract_records_ragged_metadata(records, explicit_dt)

        thresholds, positive_mask = self._resolve_thresholds(
            context=context,
            run_id=run_id,
            boards=boards,
            channels=channels,
            threshold=threshold,
            channel_config_cfg=channel_config_cfg,
            data_polarities=data_polarities,
        )

        backend = str(context.get_config(self, "backend") or "auto").lower()
        if backend == "numpy":
            logger.warning("hit_threshold backend='numpy' is deprecated; using backend='ragged'")
            backend = "ragged"
        if backend not in {"auto", "numba", "ragged"}:
            raise ValueError(
                "hit_threshold backend must be one of 'auto', 'numba', or 'ragged', "
                f"got {backend!r}"
            )

        parallel_min_records = int(context.get_config(self, "parallel_min_records"))
        if backend == "auto" and len(records) < max(1, parallel_min_records):
            backend = "ragged"

        if backend in {"auto", "numba"}:
            try:
                return self._build_hits_from_ragged_records_numba(
                    wave_pool=wave_pool,
                    wave_offsets=wave_offsets,
                    record_lengths=record_lengths,
                    baselines=baselines,
                    thresholds=thresholds,
                    positive_mask=positive_mask,
                    timestamps=timestamps,
                    boards=boards,
                    channels=channels,
                    record_ids=record_ids,
                    left_extension=left_extension,
                    right_extension=right_extension,
                    dt_values=dt_values,
                    chunk_parallel=bool(context.get_config(self, "chunk_parallel")),
                    n_workers=int(context.get_config(self, "n_workers")),
                    parallel_chunk_size=int(context.get_config(self, "parallel_chunk_size")),
                    parallel_min_records=parallel_min_records,
                )
            except Exception as exc:
                if backend == "numba":
                    raise RuntimeError("hit_threshold backend='numba' failed") from exc
                logger.warning(
                    "hit_threshold backend='auto' failed to use numba; falling back to ragged: %s",
                    exc,
                )

        return self._build_hits_from_ragged_records(
            wave_pool=wave_pool,
            wave_offsets=wave_offsets,
            record_lengths=record_lengths,
            baselines=baselines,
            thresholds=thresholds,
            positive_mask=positive_mask,
            timestamps=timestamps,
            boards=boards,
            channels=channels,
            record_ids=record_ids,
            left_extension=left_extension,
            right_extension=right_extension,
            dt_values=dt_values,
        )

    def _build_hits_from_ragged_records_numba(
        self,
        wave_pool: np.ndarray,
        wave_offsets: np.ndarray,
        record_lengths: np.ndarray,
        baselines: np.ndarray,
        thresholds: np.ndarray,
        positive_mask: np.ndarray,
        timestamps: np.ndarray,
        boards: np.ndarray,
        channels: np.ndarray,
        record_ids: np.ndarray,
        left_extension: int,
        right_extension: int,
        dt_values: np.ndarray,
        chunk_parallel: bool,
        n_workers: int,
        parallel_chunk_size: int,
        parallel_min_records: int,
    ) -> np.ndarray:
        if _NUMBA_AVAILABLE is False:
            raise RuntimeError("numba is not available")
        _ensure_numba_kernels()
        if len(record_lengths) == 0:
            return _empty_hits()

        wave_pool = np.asarray(wave_pool)
        self._validate_ragged_wave_slices(wave_pool, wave_offsets, record_lengths, record_ids)

        n_records = len(record_lengths)
        chunk_size = max(1, int(parallel_chunk_size))
        ranges = [
            (start, min(start + chunk_size, n_records)) for start in range(0, n_records, chunk_size)
        ]
        use_parallel = (
            bool(chunk_parallel)
            and n_records >= max(1, int(parallel_min_records))
            and len(ranges) > 1
        )
        workers = self._resolve_chunk_workers(n_workers, len(ranges))

        if use_parallel and workers > 1:
            with ThreadPoolExecutor(max_workers=workers) as executor:
                parts = list(
                    executor.map(
                        lambda bounds: self._build_hits_from_ragged_records_numba_range(
                            wave_pool=wave_pool,
                            wave_offsets=wave_offsets,
                            record_lengths=record_lengths,
                            baselines=baselines,
                            thresholds=thresholds,
                            positive_mask=positive_mask,
                            timestamps=timestamps,
                            boards=boards,
                            channels=channels,
                            record_ids=record_ids,
                            left_extension=left_extension,
                            right_extension=right_extension,
                            dt_values=dt_values,
                            start_idx=bounds[0],
                            end_idx=bounds[1],
                        ),
                        ranges,
                    )
                )
            non_empty = [part for part in parts if len(part) > 0]
            if not non_empty:
                return _empty_hits()
            return np.concatenate(non_empty)

        return self._build_hits_from_ragged_records_numba_range(
            wave_pool=wave_pool,
            wave_offsets=wave_offsets,
            record_lengths=record_lengths,
            baselines=baselines,
            thresholds=thresholds,
            positive_mask=positive_mask,
            timestamps=timestamps,
            boards=boards,
            channels=channels,
            record_ids=record_ids,
            left_extension=left_extension,
            right_extension=right_extension,
            dt_values=dt_values,
            start_idx=0,
            end_idx=n_records,
        )

    def _build_hits_from_ragged_records_numba_range(
        self,
        wave_pool: np.ndarray,
        wave_offsets: np.ndarray,
        record_lengths: np.ndarray,
        baselines: np.ndarray,
        thresholds: np.ndarray,
        positive_mask: np.ndarray,
        timestamps: np.ndarray,
        boards: np.ndarray,
        channels: np.ndarray,
        record_ids: np.ndarray,
        left_extension: int,
        right_extension: int,
        dt_values: np.ndarray,
        start_idx: int,
        end_idx: int,
    ) -> np.ndarray:
        counts = _numba_count_ragged_hits(
            wave_pool,
            wave_offsets,
            record_lengths,
            baselines,
            thresholds,
            positive_mask,
            int(start_idx),
            int(end_idx),
        )
        chunk_offsets = np.empty(len(counts) + 1, dtype=np.int64)
        chunk_offsets[0] = 0
        np.cumsum(counts, out=chunk_offsets[1:])
        n_hits = int(chunk_offsets[-1])
        if n_hits == 0:
            return _empty_hits()

        positions = np.empty(n_hits, dtype=np.int64)
        edge_starts = np.empty(n_hits, dtype=np.int32)
        edge_ends = np.empty(n_hits, dtype=np.int32)
        widths = np.empty(n_hits, dtype=np.float32)
        dts = np.empty(n_hits, dtype=np.int32)
        hit_timestamps = np.empty(n_hits, dtype=np.int64)
        hit_boards = np.empty(n_hits, dtype=np.int16)
        hit_channels = np.empty(n_hits, dtype=np.int16)
        hit_record_ids = np.empty(n_hits, dtype=np.int64)

        _numba_fill_ragged_hits(
            wave_pool,
            wave_offsets,
            record_lengths,
            baselines,
            thresholds,
            positive_mask,
            timestamps,
            boards,
            channels,
            record_ids,
            dt_values,
            int(left_extension),
            int(right_extension),
            int(start_idx),
            int(end_idx),
            chunk_offsets,
            positions,
            edge_starts,
            edge_ends,
            widths,
            dts,
            hit_timestamps,
            hit_boards,
            hit_channels,
            hit_record_ids,
        )
        return self._build_threshold_hit_array(
            positions=positions,
            edge_starts=edge_starts,
            edge_ends=edge_ends,
            widths=widths,
            dts=dts,
            timestamps=hit_timestamps,
            boards=hit_boards,
            channels=hit_channels,
            record_ids=hit_record_ids,
        )

    def _build_threshold_hit_array(
        self,
        positions: np.ndarray,
        edge_starts: np.ndarray,
        edge_ends: np.ndarray,
        widths: np.ndarray,
        dts: np.ndarray,
        timestamps: np.ndarray,
        boards: np.ndarray,
        channels: np.ndarray,
        record_ids: np.ndarray,
    ) -> np.ndarray:
        hits = np.empty(len(positions), dtype=THRESHOLD_HIT_DTYPE)
        hits["position"] = positions
        hits["edge_start"] = edge_starts
        hits["edge_end"] = edge_ends
        hits["width"] = widths
        hits["dt"] = dts
        hits["timestamp"] = timestamps
        hits["board"] = boards
        hits["channel"] = channels
        hits["record_id"] = record_ids
        return hits

    def _validate_ragged_wave_slices(
        self,
        wave_pool: np.ndarray,
        wave_offsets: np.ndarray,
        record_lengths: np.ndarray,
        record_ids: np.ndarray,
    ) -> None:
        active = record_lengths > 0
        if not np.any(active):
            return
        offsets = wave_offsets[active]
        lengths = record_lengths[active]
        end_offsets = offsets + lengths
        invalid = (offsets < 0) | (end_offsets > len(wave_pool))
        if np.any(invalid):
            bad_active_idx = int(np.flatnonzero(active)[np.flatnonzero(invalid)[0]])
            raise ValueError(
                "hit_threshold invalid wave slice: "
                f"record_index={bad_active_idx}, record_id={int(record_ids[bad_active_idx])}, "
                f"offset={int(wave_offsets[bad_active_idx])}, "
                f"length={int(record_lengths[bad_active_idx])}, "
                f"wave_pool_length={len(wave_pool)}"
            )

    def _resolve_chunk_workers(self, n_workers: int, n_chunks: int) -> int:
        if n_workers > 0:
            return min(max(1, int(n_workers)), max(1, n_chunks))
        return min(max(1, os.cpu_count() or 1), max(1, n_chunks))

    def _process_waveform_matrix_input(
        self,
        data: np.ndarray,
        context: Any,
        run_id: str,
        threshold: float,
        left_extension: int,
        right_extension: int,
        explicit_dt: int | None,
        channel_config_cfg: Any,
    ) -> np.ndarray:
        """waveforms / filtered_waveforms / st_waveforms 的矩阵路径。"""
        data_names = data.dtype.names or ()
        if "wave" not in data_names:
            raise ValueError("hit_threshold waveform input requires a 'wave' field")

        waves = np.asarray(data["wave"]).astype(np.float32, copy=False)
        if waves.ndim != 2:
            raise ValueError(
                f"hit_threshold waveform input expects 2D wave array, got shape={waves.shape}"
            )

        baselines = (
            data["baseline"].astype(np.float32, copy=False)
            if "baseline" in data_names
            else waves.mean(axis=1, dtype=np.float32)
        )
        timestamps = (
            data["timestamp"].astype(np.int64, copy=False)
            if "timestamp" in data_names
            else np.zeros(len(data), dtype=np.int64)
        )
        boards = (
            data["board"].astype(np.int16, copy=False)
            if "board" in data_names
            else np.zeros(len(data), dtype=np.int16)
        )
        channels = (
            data["channel"].astype(np.int16, copy=False)
            if "channel" in data_names
            else np.zeros(len(data), dtype=np.int16)
        )
        record_ids = (
            data["record_id"].astype(np.int64, copy=False)
            if "record_id" in data_names
            else np.arange(len(data), dtype=np.int64)
        )
        data_polarities = (
            np.asarray(data["polarity"]).astype("U16", copy=False)
            if "polarity" in data_names
            else None
        )
        dt_values = require_dt_array(
            data,
            explicit_dt=explicit_dt,
            plugin_name=self.provides,
            data_name="waveforms",
        )
        record_lengths = np.full(len(data), waves.shape[1], dtype=np.int64)

        thresholds, positive_mask = self._resolve_thresholds(
            context=context,
            run_id=run_id,
            boards=boards,
            channels=channels,
            threshold=threshold,
            channel_config_cfg=channel_config_cfg,
            data_polarities=data_polarities,
        )

        valid_mask = None
        n_samples = waves.shape[1]
        if not np.all(record_lengths == n_samples):
            sample_idx = np.arange(n_samples, dtype=np.int64)[None, :]
            valid_mask = sample_idx < record_lengths[:, None]

        mask = self._build_threshold_mask_from_waves(
            waves=waves,
            baselines=baselines,
            thresholds=thresholds,
            positive_mask=positive_mask,
            valid_mask=valid_mask,
        )

        return self._build_hits_from_waves_and_mask(
            waves=waves,
            mask=mask,
            baselines=baselines,
            positive_mask=positive_mask,
            timestamps=timestamps,
            boards=boards,
            channels=channels,
            record_ids=record_ids,
            left_extension=left_extension,
            right_extension=right_extension,
            dt_values=dt_values,
            record_lengths=record_lengths,
        )

    # -------------------------------------------------------------------------
    # Threshold / polarity resolution
    # -------------------------------------------------------------------------

    def _resolve_thresholds(
        self,
        context: Any,
        run_id: str,
        boards: np.ndarray,
        channels: np.ndarray,
        threshold: float,
        channel_config_cfg: Any,
        data_polarities: np.ndarray | None,
    ) -> tuple[np.ndarray, np.ndarray]:
        n_events = len(boards)
        thresholds = np.full(n_events, threshold, dtype=np.float32)
        positive_mask = np.zeros(n_events, dtype=bool)

        if data_polarities is not None:
            data_polarities = np.asarray(data_polarities).astype("U16", copy=False)
            valid_override = np.isin(data_polarities, ("positive", "negative"))
            positive_mask = np.where(valid_override, data_polarities == "positive", positive_mask)

        if not isinstance(channel_config_cfg, Mapping):
            return thresholds, positive_mask

        channel_rule_cache: dict[tuple[int, int], Any] = {}
        base_values = {"threshold": threshold}

        for board, channel in zip(boards.tolist(), channels.tolist(), strict=False):
            channel_key = (int(board), int(channel))
            if channel_key in channel_rule_cache:
                continue
            rule = resolve_effective_channel_config(
                context=context,
                plugin=self,
                run_id=run_id,
                board=channel_key[0],
                channel=channel_key[1],
                base_values=base_values,
                channel_config=channel_config_cfg,
            )
            channel_rule_cache[channel_key] = rule

        for channel_key, rule in channel_rule_cache.items():
            selector = (boards == channel_key[0]) & (channels == channel_key[1])
            thresholds[selector] = float(rule.get("threshold", threshold))

        return thresholds, positive_mask

    # -------------------------------------------------------------------------
    # Ragged hit finding
    # -------------------------------------------------------------------------

    def _build_hits_from_ragged_records(
        self,
        wave_pool: np.ndarray,
        wave_offsets: np.ndarray,
        record_lengths: np.ndarray,
        baselines: np.ndarray,
        thresholds: np.ndarray,
        positive_mask: np.ndarray,
        timestamps: np.ndarray,
        boards: np.ndarray,
        channels: np.ndarray,
        record_ids: np.ndarray,
        left_extension: int,
        right_extension: int,
        dt_values: np.ndarray,
    ) -> np.ndarray:
        """基于 wave_pool + offsets + lengths 的 ragged hit finder。

        关键优化：
        1. 使用 Numba 批量预筛选，快速识别可能包含 hit 的 records
        2. 只对通过预筛选的 records 进行详细的 hit 查找
        3. 使用 Numba 加速的连续区域查找
        """
        if len(record_lengths) == 0:
            return _empty_hits()

        wave_pool = np.asarray(wave_pool)
        n_pool = len(wave_pool)

        # 批量预筛选：使用 Numba 快速识别可能包含 hit 的 records
        if _numba_batch_prefilter is not None:
            try:
                pass_mask = _numba_batch_prefilter(
                    wave_pool,
                    wave_offsets,
                    record_lengths,
                    baselines,
                    thresholds,
                    positive_mask,
                )
                # 只处理通过预筛选的 records
                pass_indices = np.flatnonzero(pass_mask)
                if len(pass_indices) == 0:
                    return _empty_hits()
            except Exception:
                # Fallback：处理所有 records
                pass_indices = np.arange(len(record_lengths), dtype=np.int64)
        else:
            # 没有 Numba：处理所有 records
            pass_indices = np.arange(len(record_lengths), dtype=np.int64)

        hits: list[tuple] = []

        for i in pass_indices:
            offset = int(wave_offsets[i])
            length = int(record_lengths[i])
            if length <= 0:
                continue

            end_offset = offset + length
            if offset < 0 or end_offset > n_pool:
                raise ValueError(
                    "hit_threshold invalid wave slice: "
                    f"record_index={i}, record_id={int(record_ids[i])}, "
                    f"offset={offset}, length={length}, wave_pool_length={n_pool}"
                )

            wave = wave_pool[offset:end_offset]
            baseline = float(baselines[i])
            threshold = float(thresholds[i])
            positive = bool(positive_mask[i])

            # -------------------------
            # 找到过阈样本
            # -------------------------
            if positive:
                threshold_level = baseline + threshold
                hit_indices = np.flatnonzero(wave >= threshold_level)
            else:
                threshold_level = baseline - threshold
                hit_indices = np.flatnonzero(wave <= threshold_level)

            if len(hit_indices) == 0:
                continue

            # 使用优化的连续区域查找
            starts, ends = _contiguous_regions_from_indices(hit_indices)

            for start_raw, end_raw in zip(starts, ends, strict=False):
                start = int(start_raw)
                end = int(end_raw)
                seg_start = max(0, start - left_extension)
                seg_end = min(length, end + right_extension)
                if seg_end <= seg_start:
                    continue

                pos = (start + end - 1) // 2
                dt_ns = int(dt_values[i])
                global_timestamp = int(timestamps[i] + pos * dt_ns * 1000)

                edge_start = min(max(seg_start, 0), length)
                edge_end = min(max(seg_end, 0), length)
                edge_end = max(edge_end, edge_start)

                hits.append(
                    (
                        int(pos),
                        int(edge_start),
                        int(edge_end),
                        float(edge_end - edge_start),
                        dt_ns,
                        global_timestamp,
                        int(boards[i]),
                        int(channels[i]),
                        int(record_ids[i]),
                    )
                )

        if not hits:
            return _empty_hits()
        return np.array(hits, dtype=THRESHOLD_HIT_DTYPE)

    # -------------------------------------------------------------------------
    # Matrix compatibility backend
    # -------------------------------------------------------------------------

    # -------------------------------------------------------------------------
    # Matrix compatibility backend
    # -------------------------------------------------------------------------

    def _build_threshold_mask_from_waves(
        self,
        waves: np.ndarray,
        baselines: np.ndarray,
        thresholds: np.ndarray,
        positive_mask: np.ndarray,
        valid_mask: np.ndarray | None,
    ) -> np.ndarray:
        """直接从原始 wave 构造过阈 mask，避免先构造完整 signal 矩阵。"""
        if waves.size == 0:
            return np.zeros(waves.shape, dtype=bool)

        baseline_2d = baselines[:, None]
        threshold_2d = thresholds[:, None]

        if np.all(positive_mask):
            mask = waves >= baseline_2d + threshold_2d
        elif not np.any(positive_mask):
            mask = waves <= baseline_2d - threshold_2d
        else:
            mask = np.empty(waves.shape, dtype=bool)
            pos = positive_mask
            neg = ~positive_mask
            if np.any(pos):
                mask[pos] = waves[pos] >= baselines[pos, None] + thresholds[pos, None]
            if np.any(neg):
                mask[neg] = waves[neg] <= baselines[neg, None] - thresholds[neg, None]

        if valid_mask is not None:
            mask &= valid_mask
        return mask

    def _build_hits_from_waves_and_mask(
        self,
        waves: np.ndarray,
        mask: np.ndarray,
        baselines: np.ndarray,
        positive_mask: np.ndarray,
        timestamps: np.ndarray,
        boards: np.ndarray,
        channels: np.ndarray,
        record_ids: np.ndarray,
        left_extension: int,
        right_extension: int,
        dt_values: np.ndarray,
        record_lengths: np.ndarray,
    ) -> np.ndarray:
        """矩阵输入路径的 hit 构造；只在 hit segment 上临时计算 signal。"""
        if waves.size == 0 or mask.size == 0 or not np.any(mask):
            return _empty_hits()

        mask_padded = np.pad(mask, ((0, 0), (1, 1)), mode="constant", constant_values=False)
        diff = np.diff(mask_padded.astype(np.int8), axis=1)
        start_rows, starts = np.where(diff == 1)
        end_rows, ends = np.where(diff == -1)

        if len(start_rows) == 0:
            return _empty_hits()
        if not np.array_equal(start_rows, end_rows):
            raise RuntimeError("hit_threshold matrix region alignment failed")

        hits: list[tuple] = []
        n_samples = waves.shape[1]

        for hit_idx, event_idx in enumerate(start_rows.tolist()):
            start = int(starts[hit_idx])
            end = int(ends[hit_idx])
            record_length = max(int(record_lengths[event_idx]), 0)
            effective_len = min(record_length, n_samples)

            seg_start = max(0, start - left_extension)
            seg_end = min(effective_len, end + right_extension)
            if seg_end <= seg_start:
                continue

            pos = (start + end - 1) // 2
            dt_ns = int(dt_values[event_idx])
            global_timestamp = int(timestamps[event_idx] + pos * dt_ns * 1000)

            edge_start = min(max(seg_start, 0), record_length)
            edge_end = min(max(seg_end, 0), record_length)
            edge_end = max(edge_end, edge_start)

            hits.append(
                (
                    int(pos),
                    int(edge_start),
                    int(edge_end),
                    float(edge_end - edge_start),
                    dt_ns,
                    global_timestamp,
                    int(boards[event_idx]),
                    int(channels[event_idx]),
                    int(record_ids[event_idx]),
                )
            )

        if not hits:
            return _empty_hits()
        return np.array(hits, dtype=THRESHOLD_HIT_DTYPE)

    def _build_hits_from_signal_matrix(
        self,
        signal: np.ndarray,
        thresholds: np.ndarray,
        timestamps: np.ndarray,
        boards: np.ndarray,
        channels: np.ndarray,
        record_ids: np.ndarray,
        left_extension: int,
        right_extension: int,
        dt_values: np.ndarray,
        valid_mask: np.ndarray | None,
        record_lengths: np.ndarray,
    ) -> np.ndarray:
        """兼容旧接口：保留以便外部测试或旧代码调用。"""
        if signal.size == 0:
            return _empty_hits()

        mask = signal >= thresholds[:, np.newaxis]
        if valid_mask is not None:
            mask &= valid_mask
        if not np.any(mask):
            return _empty_hits()

        mask_padded = np.pad(mask, ((0, 0), (1, 1)), mode="constant", constant_values=False)
        diff = np.diff(mask_padded.astype(np.int8), axis=1)
        start_rows, starts = np.where(diff == 1)
        end_rows, ends = np.where(diff == -1)

        if len(start_rows) == 0:
            return _empty_hits()
        if not np.array_equal(start_rows, end_rows):
            raise RuntimeError("hit_threshold region alignment failed")

        hits: list[tuple] = []
        n_samples = signal.shape[1]

        for hit_idx, event_idx in enumerate(start_rows.tolist()):
            start = int(starts[hit_idx])
            end = int(ends[hit_idx])
            seg_start = max(0, start - left_extension)
            seg_end = min(n_samples, end + right_extension)
            if seg_end <= seg_start:
                continue

            pos = (start + end - 1) // 2
            dt_ns = int(dt_values[event_idx])
            global_timestamp = int(timestamps[event_idx] + pos * dt_ns * 1000)

            record_length = max(int(record_lengths[event_idx]), 0)
            edge_start = min(max(seg_start, 0), record_length)
            edge_end = min(max(seg_end, 0), record_length)
            edge_end = max(edge_end, edge_start)

            hits.append(
                (
                    int(pos),
                    int(edge_start),
                    int(edge_end),
                    float(edge_end - edge_start),
                    dt_ns,
                    global_timestamp,
                    int(boards[event_idx]),
                    int(channels[event_idx]),
                    int(record_ids[event_idx]),
                )
            )

        if not hits:
            return _empty_hits()
        return np.array(hits, dtype=THRESHOLD_HIT_DTYPE)

    # -------------------------------------------------------------------------
    # Legacy helper retained
    # -------------------------------------------------------------------------

    def _resolve_wave_pool_metadata(
        self,
        context: Any,
        run_id: str,
        record_ids: np.ndarray,
        source_event_lengths: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray]:
        from waveform_analysis.core.plugins.builtin.cpu.records import get_records_bundle

        bundle = get_records_bundle(context, run_id)
        records = bundle.records
        lookup = _build_record_lookup(records)
        wave_offsets = np.zeros(len(record_ids), dtype=np.int64)
        record_lengths = np.zeros(len(record_ids), dtype=np.int64)

        for idx, record_id in enumerate(record_ids.tolist()):
            if int(record_id) not in lookup:
                raise ValueError(
                    f"hit_threshold could not resolve record_id={int(record_id)} into records/wave_pool"
                )
            wave_offset, record_length = lookup[int(record_id)]
            source_length = int(source_event_lengths[idx])
            if source_length != int(record_length):
                raise ValueError(
                    "hit_threshold waveform source length does not match records/wave_pool length for "
                    f"record_id={int(record_id)}: source={source_length}, records={int(record_length)}"
                )
            wave_offsets[idx] = wave_offset
            record_lengths[idx] = record_length
        return wave_offsets, record_lengths


__all__ = [
    "HitFinderPlugin",
    "ThresholdHitPlugin",
    "THRESHOLD_HIT_DTYPE",
]
