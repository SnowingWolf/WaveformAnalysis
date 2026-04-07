"""
Hit Finder Plugins - 阈值 Hit 检测插件

本模块包含：
1. HitFinderPlugin: 旧导入路径兼容别名（推荐改为 peak_finding.HitFinderPlugin）
2. ThresholdHitPlugin: 新的纯阈值 hit 插件（provides='hit_threshold'），输出 THRESHOLD_HIT_DTYPE
"""

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
    WAVE_SOURCE_FILTERED,
    WAVE_SOURCE_RECORDS,
    resolve_wave_source,
)
from waveform_analysis.core.plugins.builtin.cpu._wave_source import (
    resolve_depends_on as resolve_wave_depends_on,
)
from waveform_analysis.core.plugins.builtin.cpu.peak_finding import (
    HIT_DTYPE,
)
from waveform_analysis.core.plugins.builtin.cpu.peak_finding import (
    HitFinderPlugin as _CanonicalHitFinderPlugin,
)
from waveform_analysis.core.plugins.core.base import Option, Plugin
from waveform_analysis.core.processing.event_grouping import find_hits

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
    }

    def resolve_depends_on(self, context: Any, run_id: str | None = None) -> list[str]:
        source = resolve_wave_source(context, self)
        # Dynamic dependency: hit_threshold reads from records, st_waveforms,
        # or filtered_waveforms depending on wave_source/use_filtered.
        return resolve_wave_depends_on(source, bool(context.get_config(self, "use_filtered")))

    def compute(self, context: Any, run_id: str, **_kwargs) -> np.ndarray:
        threshold = float(context.get_config(self, "threshold"))
        use_filtered = bool(context.get_config(self, "use_filtered"))
        source = resolve_wave_source(context, self)
        left_extension = max(0, int(context.get_config(self, "left_extension")))
        right_extension = max(0, int(context.get_config(self, "right_extension")))
        explicit_dt = resolve_dt_config(
            context, self, deprecated_keys=("sampling_interval_ns", "dt_ns")
        )
        channel_config_cfg = context.get_config(self, "channel_config")

        if source == WAVE_SOURCE_RECORDS:
            from waveform_analysis.core import records_view

            rv = records_view(context, run_id)
            records = rv.records
            if len(records) == 0:
                return np.zeros(0, dtype=THRESHOLD_HIT_DTYPE)

            record_names = records.dtype.names or ()
            record_ids_for_view = (
                records["record_id"].astype(np.int64, copy=False)
                if "record_id" in record_names
                else np.arange(len(records), dtype=np.int64)
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
            waveform_data = (
                context.get_data(run_id, "filtered_waveforms")
                if source == WAVE_SOURCE_FILTERED or (source == WAVE_SOURCE_AUTO and use_filtered)
                else context.get_data(run_id, "st_waveforms")
            )

            if not isinstance(waveform_data, np.ndarray):
                raise ValueError("hit_threshold expects st_waveforms as a single structured array")
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
                data_name="st_waveforms",
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


__all__ = [
    "HitFinderPlugin",
    "ThresholdHitPlugin",
    "THRESHOLD_HIT_DTYPE",
]
