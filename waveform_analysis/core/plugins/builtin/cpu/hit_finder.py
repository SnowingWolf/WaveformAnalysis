"""
Hit Finder Plugins - 阈值 Hit 检测插件

本模块包含：
1. HitFinderPlugin: 旧导入路径兼容别名（推荐改为 peak_finding.HitFinderPlugin）
1. ThresholdHitPlugin: 新的纯阈值 hit 插件（provides='hit_threshold'），输出 HIT_DTYPE
2. ThresholdHitFinderPlugin: 旧版兼容插件（provides='hits'），输出 PEAK_DTYPE
"""

from typing import Any
import warnings

import numpy as np

from waveform_analysis.core.plugins.builtin.cpu._wave_source import (
    WAVE_SOURCE_AUTO,
    WAVE_SOURCE_FILTERED,
    WAVE_SOURCE_RECORDS,
    resolve_wave_source,
)
from waveform_analysis.core.plugins.builtin.cpu._wave_source import (
    resolve_depends_on as resolve_wave_depends_on,
)
from waveform_analysis.core.plugins.builtin.cpu.channel_metadata import resolve_channel_metadata
from waveform_analysis.core.plugins.builtin.cpu.peak_finding import (
    HIT_DTYPE,
)
from waveform_analysis.core.plugins.builtin.cpu.peak_finding import (
    HitFinderPlugin as _CanonicalHitFinderPlugin,
)
from waveform_analysis.core.plugins.core.base import Option, Plugin
from waveform_analysis.core.processing.dtypes import PEAK_DTYPE
from waveform_analysis.core.processing.event_grouping import find_hits


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
    """Threshold-only hit detector with HIT_DTYPE output."""

    provides = "hit_threshold"
    depends_on = []  # 动态依赖，由 resolve_depends_on 决定
    version = "0.3.0"
    output_dtype = HIT_DTYPE
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
        "channel_metadata": Option(
            default=None,
            type=dict,
            help="每通道元数据映射（支持 run_id 分层），用于按通道覆盖 polarity",
        ),
    }

    def resolve_depends_on(self, context: Any, run_id: str | None = None) -> list[str]:
        source = resolve_wave_source(context, self)
        return resolve_wave_depends_on(source, bool(context.get_config(self, "use_filtered")))

    def compute(self, context: Any, run_id: str, **_kwargs) -> np.ndarray:
        threshold = float(context.get_config(self, "threshold"))
        use_filtered = bool(context.get_config(self, "use_filtered"))
        polarity = context.get_config(self, "polarity")
        left_extension = max(0, int(context.get_config(self, "left_extension")))
        right_extension = max(0, int(context.get_config(self, "right_extension")))
        sampling_interval_ns = float(context.get_config(self, "sampling_interval_ns"))
        channel_metadata_cfg = context.get_config(self, "channel_metadata")

        waveform_data = (
            context.get_data(run_id, "filtered_waveforms")
            if use_filtered
            else context.get_data(run_id, "st_waveforms")
        )

        if not isinstance(waveform_data, np.ndarray):
            raise ValueError("hit_threshold expects st_waveforms as a single structured array")

        if len(waveform_data) == 0:
            return np.zeros(0, dtype=HIT_DTYPE)

        channels = (
            waveform_data["channel"]
            if "channel" in waveform_data.dtype.names
            else np.zeros(len(waveform_data), dtype=np.int16)
        )
        channel_meta = resolve_channel_metadata(
            channel_metadata=channel_metadata_cfg,
            run_id=run_id,
            channels=np.unique(channels).tolist(),
            plugin_name=self.provides,
        )

        sampling_interval_ps = sampling_interval_ns * 1e3
        hits: list[tuple] = []

        for event_idx, record in enumerate(waveform_data):
            wave = np.asarray(record["wave"])
            if wave.size == 0:
                continue

            baseline = (
                float(record["baseline"])
                if "baseline" in record.dtype.names
                else float(np.mean(wave))
            )
            timestamp = int(record["timestamp"]) if "timestamp" in record.dtype.names else 0
            channel = int(record["channel"]) if "channel" in record.dtype.names else 0

            ch_polarity = channel_meta.get(channel, {}).get("polarity", "unknown")
            effective_polarity = (
                ch_polarity if ch_polarity in ("positive", "negative") else polarity
            )

            if effective_polarity == "positive":
                signal = wave.astype(np.float64) - baseline
            else:
                signal = baseline - wave.astype(np.float64)

            regions = self._find_regions(signal, threshold)
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
                global_timestamp = int(timestamp + pos * sampling_interval_ps)

                hits.append(
                    (
                        int(pos),
                        float(height),
                        float(integral),
                        float(seg_start),
                        float(seg_end),
                        int(global_timestamp),
                        int(channel),
                        int(event_idx),
                    )
                )

        if hits:
            return np.array(hits, dtype=HIT_DTYPE)
        return np.zeros(0, dtype=HIT_DTYPE)

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
    version = "2.1.0"  # 版本升级：输出改为单数组
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
        channels = (
            waveform_data["channel"]
            if "channel" in waveform_data.dtype.names
            else np.zeros(len(waveform_data), dtype="i2")
        )

        for ch in np.unique(channels):
            mask = channels == ch
            if not np.any(mask):
                continue
            st_ch = waveform_data[mask]
            waves_2d = np.stack(st_ch["wave"])
            hits = find_hits(waves_2d, st_ch["baseline"], threshold=threshold)
            if len(hits) > 0:
                hits["channel"] = np.int16(ch)
            hits_all.append(hits)

        if not hits_all:
            return np.zeros(0, dtype=PEAK_DTYPE)
        return np.concatenate(hits_all)


__all__ = [
    "HitFinderPlugin",
    "ThresholdHitPlugin",
    "ThresholdHitFinderPlugin",
]
