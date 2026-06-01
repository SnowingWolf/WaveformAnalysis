"""
Hit Finder Plugins - 阈值 Hit 检测插件

本模块包含：
1. HitFinderPlugin: 旧导入路径兼容别名（推荐改为 peak_finding.HitFinderPlugin）
2. ThresholdHitPlugin: 新的纯阈值 hit 插件（provides='hit_threshold'），输出 THRESHOLD_HIT_DTYPE
"""

import logging
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
    load_wave_input,
    resolve_wave_input_spec,
)
from waveform_analysis.core.plugins.builtin.cpu.peak_finding import (
    HitFinderPlugin as _CanonicalHitFinderPlugin,
)
from waveform_analysis.core.plugins.core.base import Option, Plugin

logger = logging.getLogger(__name__)

THRESHOLD_HIT_DTYPE = np.dtype(
    [
        ("position", "i8"),  # hit 峰值位置（采样点索引）
        ("height", "f4"),  # hit 高度
        ("integral", "f4"),  # hit 积分
        ("edge_start", "i4"),  # 命中窗口起始边界（record 内安全半开样本起点）
        ("edge_end", "i4"),  # 命中窗口结束边界（record 内安全半开样本终点）
        ("width", "f4"),  # 命中窗口宽度（采样点）
        ("dt", "i4"),  # 采样间隔（ns）
        ("rise_time", "f4"),  # 从过阈起点到峰值的时间（ns）
        ("fall_time", "f4"),  # 从峰值到过阈终点的时间（ns）
        ("timestamp", "i8"),  # 全局时间戳（ps）
        ("board", "i2"),  # 板卡编号
        ("channel", "i2"),  # 通道号
        ("record_id", "i8"),  # 来源波形/记录的唯一编号
    ]
)


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


class ThresholdHitPlugin(Plugin):
    """Threshold-only hit detector with THRESHOLD_HIT_DTYPE output."""

    provides = "hit_threshold"
    depends_on = []  # 动态依赖，由 resolve_depends_on 决定
    description = "Threshold-only hit detector with THRESHOLD_HIT_DTYPE output."
    version = "0.11.0"
    output_dtype = THRESHOLD_HIT_DTYPE
    save_when = "always"

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
        "streaming_chunk_size": Option(
            default=100_000,
            type=int,
            help="流式处理时的 chunk 大小（仅对 RecordsBundleRef 生效）",
        ),
    }

    def resolve_depends_on(self, context: Any, run_id: str | None = None) -> list[str]:
        spec = resolve_wave_input_spec(context, self)
        return list(spec.depends_on)

    def compute(self, context: Any, run_id: str, **_kwargs) -> np.ndarray:
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

        # RecordsBundleRef cannot be loaded through the formal records_view API.
        if wave_input.spec.is_records:
            from waveform_analysis.core.processing.records_builder import RecordsBundleRef

            bundle = wave_input.records
            if isinstance(bundle, RecordsBundleRef):
                logger.info(
                    f"hit_threshold: detected RecordsBundleRef with {bundle.total_records} records, "
                    f"using streaming mode"
                )
                return self._compute_streaming(
                    context,
                    run_id,
                    bundle,
                    threshold,
                    left_extension,
                    right_extension,
                    explicit_dt,
                    channel_config_cfg,
                )

        if wave_input.spec.is_records:
            records = wave_input.records
            rv = wave_input.records_view
            if records is None or rv is None:
                raise ValueError("hit_threshold failed to load records_view for records source")
            if len(records) == 0:
                return np.zeros(0, dtype=THRESHOLD_HIT_DTYPE)

            record_names = records.dtype.names or ()
            record_ids_for_view = (
                records["record_id"].astype(np.int64, copy=False)
                if "record_id" in record_names
                else np.arange(len(records), dtype=np.int64)
            )

            # 使用批处理避免内存溢出
            chunk_size = int(context.get_config(self, "streaming_chunk_size"))
            n_records = len(record_ids_for_view)

            if n_records > chunk_size:
                logger.info(
                    f"hit_threshold: processing {n_records} records in batches of {chunk_size}"
                )
                return self._compute_records_batched(
                    context,
                    run_id,
                    records,
                    rv,
                    threshold,
                    left_extension,
                    right_extension,
                    explicit_dt,
                    channel_config_cfg,
                    chunk_size,
                )

            waves, valid_mask = rv.waves(record_ids_for_view, mask=True, dtype=np.float64)
            record_names = records.dtype.names or ()

            baselines = records["baseline"].astype(np.float64, copy=False)
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
            record_lengths = records["event_length"].astype(np.int64, copy=False)
        else:
            waveform_data = wave_input.waveform_data
            if waveform_data is None:
                raise ValueError(f"hit_threshold failed to load {wave_input.spec.expected_name}")
            if len(waveform_data) == 0:
                return np.zeros(0, dtype=THRESHOLD_HIT_DTYPE)

            waveform_names = waveform_data.dtype.names or ()
            waves = np.asarray(waveform_data["wave"]).astype(np.float64, copy=False)
            valid_mask = None
            baselines = (
                waveform_data["baseline"].astype(np.float64, copy=False)
                if "baseline" in waveform_names
                else waves.mean(axis=1, dtype=np.float64)
            )
            timestamps = (
                waveform_data["timestamp"].astype(np.int64, copy=False)
                if "timestamp" in waveform_names
                else np.zeros(len(waveform_data), dtype=np.int64)
            )
            boards = (
                waveform_data["board"].astype(np.int16, copy=False)
                if "board" in waveform_names
                else np.zeros(len(waveform_data), dtype=np.int16)
            )
            channels = (
                waveform_data["channel"].astype(np.int16, copy=False)
                if "channel" in waveform_names
                else np.zeros(len(waveform_data), dtype=np.int16)
            )
            record_ids = (
                waveform_data["record_id"].astype(np.int64, copy=False)
                if "record_id" in waveform_names
                else np.arange(len(waveform_data), dtype=np.int64)
            )
            data_polarities = (
                np.asarray(waveform_data["polarity"]).astype("U16", copy=False)
                if "polarity" in waveform_names
                else None
            )
            dt_values = require_dt_array(
                waveform_data,
                explicit_dt=explicit_dt,
                plugin_name=self.provides,
                data_name=wave_input.spec.expected_name,
            )
            _wave_offsets, record_lengths = self._resolve_wave_pool_metadata(
                context,
                run_id,
                record_ids=record_ids,
                source_event_lengths=_resolve_source_event_lengths(waveform_data),
            )

        thresholds, positive_mask = self._resolve_thresholds(
            context=context,
            run_id=run_id,
            boards=boards,
            channels=channels,
            threshold=threshold,
            channel_config_cfg=channel_config_cfg,
            data_polarities=data_polarities,
        )
        baseline_2d = baselines[:, np.newaxis]
        signal = np.where(positive_mask[:, np.newaxis], waves - baseline_2d, baseline_2d - waves)

        return self._build_hits_from_signal_matrix(
            signal=signal,
            thresholds=thresholds,
            timestamps=timestamps,
            boards=boards,
            channels=channels,
            record_ids=record_ids,
            left_extension=left_extension,
            right_extension=right_extension,
            dt_values=dt_values,
            valid_mask=valid_mask,
            record_lengths=record_lengths,
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
        """批处理版本的 records 处理，避免一次性加载所有波形到内存

        当 RecordsBundle 的记录数超过 streaming_chunk_size 时使用此方法，
        分批加载波形数据以降低内存峰值。
        """
        n_records = len(records)
        all_hits = []

        for start_idx in range(0, n_records, chunk_size):
            end_idx = min(start_idx + chunk_size, n_records)
            chunk_records = records[start_idx:end_idx]

            # 使用公共方法提取元数据（避免代码重复）
            (
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
            ) = self._extract_records_metadata(chunk_records, rv, explicit_dt)

            # 计算阈值和极性
            thresholds, positive_mask = self._resolve_thresholds(
                context=context,
                run_id=run_id,
                boards=boards,
                channels=channels,
                threshold=threshold,
                channel_config_cfg=channel_config_cfg,
                data_polarities=data_polarities,
            )

            # 计算信号
            baseline_2d = baselines[:, np.newaxis]
            signal = np.where(
                positive_mask[:, np.newaxis], waves - baseline_2d, baseline_2d - waves
            )

            # 构建 hits
            chunk_hits = self._build_hits_from_signal_matrix(
                signal=signal,
                thresholds=thresholds,
                timestamps=timestamps,
                boards=boards,
                channels=channels,
                record_ids=record_ids,
                left_extension=left_extension,
                right_extension=right_extension,
                dt_values=dt_values,
                valid_mask=valid_mask,
                record_lengths=record_lengths,
            )

            if len(chunk_hits) > 0:
                all_hits.append(chunk_hits)

            logger.debug(
                f"hit_threshold: processed batch {start_idx}-{end_idx}, found {len(chunk_hits)} hits"
            )

        if not all_hits:
            return np.zeros(0, dtype=THRESHOLD_HIT_DTYPE)

        return np.concatenate(all_hits)

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
        thresholds = np.full(n_events, threshold, dtype=np.float64)
        positive_mask = np.zeros(n_events, dtype=bool)
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

        if data_polarities is not None:
            valid_override = np.isin(data_polarities, ("positive", "negative"))
            positive_mask = np.where(valid_override, data_polarities == "positive", positive_mask)

        return thresholds, positive_mask

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
        if signal.size == 0:
            return np.zeros(0, dtype=THRESHOLD_HIT_DTYPE)

        mask = signal >= thresholds[:, np.newaxis]
        if valid_mask is not None:
            mask &= valid_mask
        if not np.any(mask):
            return np.zeros(0, dtype=THRESHOLD_HIT_DTYPE)

        mask_padded = np.pad(mask, ((0, 0), (1, 1)), mode="constant", constant_values=False)
        diff = np.diff(mask_padded.astype(np.int8), axis=1)
        start_rows, starts = np.where(diff == 1)
        end_rows, ends = np.where(diff == -1)

        if len(start_rows) == 0:
            return np.zeros(0, dtype=THRESHOLD_HIT_DTYPE)

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

            segment = signal[event_idx, seg_start:seg_end]
            if segment.size == 0:
                continue

            rel_pos = int(np.argmax(segment))
            pos = seg_start + rel_pos
            height = float(segment[rel_pos])
            integral = float(np.sum(np.maximum(segment, 0.0)))
            dt_ns = int(dt_values[event_idx])
            sampling_interval_ps = float(dt_ns) * 1e3
            rise_time = float(max(pos - start, 0) * dt_ns)
            fall_time = float(max((end - 1) - pos, 0) * dt_ns)
            global_timestamp = int(timestamps[event_idx] + pos * sampling_interval_ps)

            record_length = max(int(record_lengths[event_idx]), 0)
            edge_start = min(max(seg_start, 0), record_length)
            edge_end = min(max(seg_end, 0), record_length)
            edge_end = max(edge_end, edge_start)

            hits.append(
                (
                    int(pos),
                    height,
                    integral,
                    edge_start,
                    edge_end,
                    float(edge_end - edge_start),
                    dt_ns,
                    rise_time,
                    fall_time,
                    global_timestamp,
                    int(boards[event_idx]),
                    int(channels[event_idx]),
                    int(record_ids[event_idx]),
                )
            )

        if hits:
            return np.array(hits, dtype=THRESHOLD_HIT_DTYPE)
        return np.zeros(0, dtype=THRESHOLD_HIT_DTYPE)

    def _extract_records_metadata(
        self,
        records: np.ndarray,
        rv: Any,  # RecordsView
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
        """从 records 提取元数据（公共逻辑）

        Returns:
            (waves, valid_mask, baselines, timestamps, boards, channels, record_ids, data_polarities, dt_values, record_lengths)
        """
        if len(records) == 0:
            empty = np.zeros(0, dtype=np.float64)
            return (
                np.zeros((0, 0), dtype=np.float64),  # waves
                np.zeros((0, 0), dtype=bool),  # valid_mask
                empty,
                empty,  # baselines, timestamps
                np.zeros(0, dtype=np.int16),
                np.zeros(0, dtype=np.int16),  # boards, channels
                np.zeros(0, dtype=np.int64),  # record_ids
                None,  # data_polarities
                np.zeros(0, dtype=np.int64),  # dt_values
                np.zeros(0, dtype=np.int64),  # record_lengths
            )

        record_names = records.dtype.names or ()
        record_ids_for_view = (
            records["record_id"].astype(np.int64, copy=False)
            if "record_id" in record_names
            else np.arange(len(records), dtype=np.int64)
        )

        # 加载波形
        waves, valid_mask = rv.waves(record_ids_for_view, mask=True, dtype=np.float64)

        # 提取字段
        baselines = records["baseline"].astype(np.float64, copy=False)
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
        record_lengths = records["event_length"].astype(np.int64, copy=False)

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
        """流式处理 RecordsBundleRef"""
        chunk_size = int(context.get_config(self, "streaming_chunk_size"))
        all_hits = []
        total_processed = 0
        log_interval = chunk_size * 10

        for chunk_bundle in bundle_ref.iter_chunks(chunk_size=chunk_size):
            chunk_hits = self._process_chunk(
                context,
                run_id,
                chunk_bundle,
                threshold,
                left_extension,
                right_extension,
                explicit_dt,
                channel_config_cfg,
            )
            all_hits.append(chunk_hits)
            total_processed += len(chunk_bundle.records)

            # 每处理 10 个 chunk 记录一次进度
            if total_processed % log_interval == 0:
                total_hits = sum(len(h) for h in all_hits)
                logger.info(
                    f"hit_threshold: processed {total_processed}/{bundle_ref.total_records} records, "
                    f"found {total_hits} hits"
                )

        # 合并所有 hits
        if all_hits:
            result = np.concatenate(all_hits)
            logger.info(f"hit_threshold: streaming mode completed, total hits: {len(result)}")
            return result
        return np.zeros(0, dtype=THRESHOLD_HIT_DTYPE)

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
        """处理单个 chunk（复用现有逻辑）"""
        from waveform_analysis.core.data.records_view import RecordsView

        records = chunk_bundle.records
        if len(records) == 0:
            return np.zeros(0, dtype=THRESHOLD_HIT_DTYPE)

        # 从 chunk_bundle 构建 RecordsView
        # 注意：chunk_bundle.records 的 wave_offset 已经是相对偏移（由 iter_chunks 自动调整）
        rv = RecordsView(records, chunk_bundle.wave_pool)

        # 提取元数据（复用公共逻辑）
        (
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
        ) = self._extract_records_metadata(records, rv, explicit_dt)

        # 解析阈值
        thresholds, positive_mask = self._resolve_thresholds(
            context=context,
            run_id=run_id,
            boards=boards,
            channels=channels,
            threshold=threshold,
            channel_config_cfg=channel_config_cfg,
            data_polarities=data_polarities,
        )

        # 构建信号矩阵
        baseline_2d = baselines[:, np.newaxis]
        signal = np.where(positive_mask[:, np.newaxis], waves - baseline_2d, baseline_2d - waves)

        # 构建 hits
        return self._build_hits_from_signal_matrix(
            signal=signal,
            thresholds=thresholds,
            timestamps=timestamps,
            boards=boards,
            channels=channels,
            record_ids=record_ids,
            left_extension=left_extension,
            right_extension=right_extension,
            dt_values=dt_values,
            valid_mask=valid_mask,
            record_lengths=record_lengths,
        )


__all__ = [
    "HitFinderPlugin",
    "ThresholdHitPlugin",
    "THRESHOLD_HIT_DTYPE",
]
