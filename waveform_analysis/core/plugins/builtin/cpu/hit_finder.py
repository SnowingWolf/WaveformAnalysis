"""
Hit Finder Plugins - 阈值 Hit 检测插件

本模块包含：
1. HitFinderPlugin: 旧导入路径兼容别名（推荐改为 peak_finding.HitFinderPlugin）
1. ThresholdHitPlugin: 新的纯阈值 hit 插件（provides='hit_threshold'），输出 THRESHOLD_HIT_DTYPE
2. ThresholdHitFinderPlugin: 旧版兼容插件（provides='hits'），输出 PEAK_DTYPE
"""

from typing import Any
import warnings

import numpy as np

from waveform_analysis.core.hardware.channel import (
    iter_hardware_channel_groups,
    resolve_effective_channel_config,
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
from waveform_analysis.core.processing.dtypes import PEAK_DTYPE
from waveform_analysis.core.processing.event_grouping import find_hits

THRESHOLD_HIT_DTYPE = np.dtype(
    [
        ("position", "i8"),  # hit 峰值位置（采样点索引）
        ("height", "f4"),  # hit 高度
        ("integral", "f4"),  # hit 积分
        ("edge_start", "f4"),  # 命中窗口起始边界（采样点）
        ("edge_end", "f4"),  # 命中窗口结束边界（采样点）
        ("width", "f4"),  # 命中窗口宽度（采样点）
        ("timestamp", "i8"),  # 全局时间戳（ps）
        ("board", "i2"),  # 板卡编号
        ("channel", "i2"),  # 通道号
        ("record_id", "i8"),  # 来源波形/记录的唯一编号
    ]
)


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
    version = "0.7.0"
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
        "polarity": Option(
            default="negative",
            type=str,
            choices=["negative", "positive"],
            help="信号极性：negative 表示 baseline-wave；positive 表示 wave-baseline",
        ),
        "left_extension": Option(default=2, type=int, help="Hit 左侧扩展点数"),
        "right_extension": Option(default=2, type=int, help="Hit 右侧扩展点数"),
        "sampling_interval_ns": Option(
            default=2.0,
            type=float,
            help="采样间隔（ns），用于计算 timestamp（内部换算到 ps）",
        ),
        "channel_config": Option(
            default=None,
            type=dict,
            help="按 (board, channel) 的插件通道覆盖配置，可覆盖 polarity/threshold。",
        ),
    }

    def resolve_depends_on(self, context: Any, run_id: str | None = None) -> list[str]:
        source = resolve_wave_source(context, self)
        return resolve_wave_depends_on(source, bool(context.get_config(self, "use_filtered")))

    def compute(self, context: Any, run_id: str, **_kwargs) -> np.ndarray:
        threshold = float(context.get_config(self, "threshold"))
        use_filtered = bool(context.get_config(self, "use_filtered"))
        source = resolve_wave_source(context, self)
        polarity = context.get_config(self, "polarity")
        left_extension = max(0, int(context.get_config(self, "left_extension")))
        right_extension = max(0, int(context.get_config(self, "right_extension")))
        sampling_interval_ns = float(context.get_config(self, "sampling_interval_ns"))
        channel_config_cfg = context.get_config(self, "channel_config")

        if source == WAVE_SOURCE_RECORDS:
            from waveform_analysis.core import records_view

            rv = records_view(context, run_id)
            records = rv.records

            if len(records) == 0:
                return np.zeros(0, dtype=THRESHOLD_HIT_DTYPE)

            records_len = len(records)

            def get_wave(i: int) -> np.ndarray:
                return rv.wave(i)

            def get_signal(i: int) -> np.ndarray:
                return rv.signal(i)

            def get_baseline(i: int) -> float:
                return float(records[i]["baseline"])

            def get_timestamp(i: int) -> int:
                return int(records[i]["timestamp"])

            def get_channel(i: int) -> int:
                if "channel" in records.dtype.names:
                    return int(records[i]["channel"])
                return 0

            def get_board(i: int) -> int:
                if "board" in records.dtype.names:
                    return int(records[i]["board"])
                return 0

            def get_record_id(i: int) -> int:
                if "record_id" in records.dtype.names:
                    return int(records[i]["record_id"])
                return i

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

            records_len = len(waveform_data)

            def get_wave(i: int) -> np.ndarray:
                return np.asarray(waveform_data[i]["wave"])

            def get_baseline(i: int) -> float:
                if "baseline" in waveform_data.dtype.names:
                    return float(waveform_data[i]["baseline"])
                wave = get_wave(i)
                return float(np.mean(wave))

            def get_timestamp(i: int) -> int:
                if "timestamp" in waveform_data.dtype.names:
                    return int(waveform_data[i]["timestamp"])
                return 0

            def get_channel(i: int) -> int:
                if "channel" in waveform_data.dtype.names:
                    return int(waveform_data[i]["channel"])
                return 0

            def get_board(i: int) -> int:
                if "board" in waveform_data.dtype.names:
                    return int(waveform_data[i]["board"])
                return 0

            def get_record_id(i: int) -> int:
                if "record_id" in waveform_data.dtype.names:
                    return int(waveform_data[i]["record_id"])
                return i

        sampling_interval_ps = sampling_interval_ns * 1e3
        hits: list[tuple] = []

        for event_idx in range(records_len):
            wave = get_wave(event_idx)
            if wave.size == 0:
                continue

            baseline = get_baseline(event_idx)
            timestamp = get_timestamp(event_idx)
            board = get_board(event_idx)
            channel = get_channel(event_idx)
            record_id = get_record_id(event_idx)

            effective_rule = resolve_effective_channel_config(
                context=context,
                plugin=self,
                run_id=run_id,
                board=board,
                channel=channel,
                base_values={
                    "polarity": polarity,
                    "threshold": threshold,
                },
                channel_config=channel_config_cfg,
            )

            data_polarity = None
            if source == WAVE_SOURCE_RECORDS and "polarity" in records.dtype.names:
                data_polarity = str(records[event_idx]["polarity"])
            elif source != WAVE_SOURCE_RECORDS and "polarity" in waveform_data.dtype.names:
                data_polarity = str(waveform_data[event_idx]["polarity"])

            effective_polarity = (
                data_polarity
                if data_polarity in ("positive", "negative")
                else effective_rule.get("polarity", polarity)
            )
            effective_threshold = float(effective_rule.get("threshold", threshold))

            if source == WAVE_SOURCE_RECORDS and data_polarity in ("positive", "negative"):
                signal = -get_signal(event_idx).astype(np.float64, copy=False)
            elif effective_polarity == "positive":
                signal = wave.astype(np.float64) - baseline
            else:
                signal = baseline - wave.astype(np.float64)

            regions = self._find_regions(signal, effective_threshold)
            for start, end in regions:
                seg_start = max(0, start - left_extension)
                seg_end = min(len(signal), end + right_extension)
                if seg_end <= seg_start:
                    continue

                segment = signal[seg_start:seg_end]
                if segment.size == 0:
                    continue

                rel_pos = int(np.argmax(segment))
                pos = seg_start + rel_pos
                height = float(segment[rel_pos])
                integral = float(np.sum(np.maximum(segment, 0.0)))
                width = float(seg_end - seg_start)
                global_timestamp = int(timestamp + pos * sampling_interval_ps)

                hits.append(
                    (
                        int(pos),
                        float(height),
                        float(integral),
                        float(seg_start),
                        float(seg_end),
                        float(width),
                        int(global_timestamp),
                        int(board),
                        int(channel),
                        int(record_id),
                    )
                )

        if hits:
            return np.array(hits, dtype=THRESHOLD_HIT_DTYPE)
        return np.zeros(0, dtype=THRESHOLD_HIT_DTYPE)

    def _find_regions(self, signal: np.ndarray, threshold: float) -> list[tuple[int, int]]:
        mask = signal >= threshold
        if not np.any(mask):
            return []

        padded = np.pad(mask, (1, 1), mode="constant", constant_values=False)
        diff = np.diff(padded.astype(np.int8))
        starts = np.where(diff == 1)[0]
        ends = np.where(diff == -1)[0]
        return list(zip(starts.tolist(), ends.tolist(), strict=False))


class ThresholdHitFinderPlugin(Plugin):
    """Example implementation of the legacy HitFinder as a plugin."""

    provides = "hits"
    depends_on = []  # 动态依赖，由 resolve_depends_on 决定
    version = "2.2.0"  # 版本升级：按 (board, channel) 分组
    output_dtype = np.dtype(PEAK_DTYPE)

    options = {
        "threshold": Option(default=10.0, type=float, help="Hit 检测阈值"),
        "use_filtered": Option(
            default=False,
            type=bool,
            help="是否使用 filtered_waveforms（需要先注册 FilteredWaveformsPlugin）",
        ),
    }

    def resolve_depends_on(self, context: Any, run_id: str | None = None) -> list[str]:
        if context.get_config(self, "use_filtered"):
            return ["filtered_waveforms"]
        return ["st_waveforms"]

    def compute(self, context: Any, run_id: str, **_kwargs) -> np.ndarray:
        threshold = context.get_config(self, "threshold")
        use_filtered = context.get_config(self, "use_filtered")

        waveform_data = (
            context.get_data(run_id, "filtered_waveforms")
            if use_filtered
            else context.get_data(run_id, "st_waveforms")
        )

        if not isinstance(waveform_data, np.ndarray):
            raise ValueError("hits expects st_waveforms as a single structured array")

        if len(waveform_data) == 0:
            return np.zeros(0, dtype=PEAK_DTYPE)

        hits_all: list[np.ndarray] = []
        for hw_channel, st_ch in iter_hardware_channel_groups(waveform_data):
            waves_2d = np.stack(st_ch["wave"])
            hits = find_hits(waves_2d, st_ch["baseline"], threshold=threshold)
            if len(hits) > 0:
                hits["board"] = np.int16(hw_channel.board)
                hits["channel"] = np.int16(hw_channel.channel)
            hits_all.append(hits)

        if not hits_all:
            return np.zeros(0, dtype=PEAK_DTYPE)
        return np.concatenate(hits_all)


__all__ = [
    "HitFinderPlugin",
    "ThresholdHitPlugin",
    "ThresholdHitFinderPlugin",
    "THRESHOLD_HIT_DTYPE",
]
