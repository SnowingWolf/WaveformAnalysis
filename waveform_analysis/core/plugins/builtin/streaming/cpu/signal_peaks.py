# -*- coding: utf-8 -*-
"""
CPU Streaming Signal Peaks Plugin.

基于滤波后的波形流式检测峰值，并返回峰值特征的 chunk 流。
时间字段使用事件的 timestamp（统一为 ps）。
"""

import logging
from typing import Any, Iterator, List, Optional, Union

import numpy as np
from scipy.signal import find_peaks

from waveform_analysis.core.foundation.utils import exporter
from waveform_analysis.core.plugins.builtin.cpu.peak_finding import ADVANCED_PEAK_DTYPE
from waveform_analysis.core.plugins.core import Option, StreamingPlugin
from waveform_analysis.core.processing.chunk import (
    EVENT_LENGTH_FIELD,
    TIMESTAMP_FIELD,
    Chunk,
    get_endtime,
)

export, __all__ = exporter()

logger = logging.getLogger(__name__)


@export
class SignalPeaksStreamPlugin(StreamingPlugin):
    """
    流式峰值检测插件（CPU）。

    - 输入: filtered_waveforms + st_waveforms（静态）
    - 输出: 峰值特征 chunk 流（时间字段使用 timestamp）
    """

    provides = "signal_peaks_stream"
    depends_on = ["filtered_waveforms", "st_waveforms"]
    description = "Stream peak detection from filtered waveforms."
    version = "1.0.2"
    save_when = "never"  # 流式 chunk 不做缓存保存
    output_dtype = None
    
    output_time_field = TIMESTAMP_FIELD
    output_endtime_field = "endtime"
    output_data_kind = "peaks"
    required_halo_ns = 0
    clip_strict = False
    is_stateful = False
    chunk_size = 4096
    parallel = True
    executor_type = "process"
    max_workers = None

    options = {
        "use_derivative": Option(
            default=True,
            type=bool,
            help="是否使用一阶导数进行峰值检测（True: 检测导数峰值, False: 检测波形峰值）",
        ),
        "height": Option(default=30.0, type=float, help="峰值的最小高度阈值"),
        "distance": Option(default=2, type=int, help="峰值之间的最小距离（采样点数）"),
        "prominence": Option(default=0.7, type=float, help="峰值的最小显著性（prominence）"),
        "width": Option(default=4, type=int, help="峰值的最小宽度（采样点数）"),
        "threshold": Option(default=None, help="峰值的阈值条件（可选）"),
        "height_method": Option(
            default="diff",
            type=str,
            help="峰高计算方法: 'diff' (积分差分) 或 'minmax' (最大最小值差)",
        ),
        "sampling_interval_ns": Option(
            default=2.0,
            type=float,
            help="采样间隔（纳秒），用于计算全局时间戳。默认 2.0 ns",
        ),
    }

    def compute(self, context: Any, run_id: str, **kwargs) -> Iterator[Chunk]:
        self._load_config(context)
        return super().compute(context, run_id, **kwargs)

    def _load_config(self, context: Any) -> None:
        self.use_derivative = context.get_config(self, "use_derivative")
        self.height = context.get_config(self, "height")
        self.distance = context.get_config(self, "distance")
        self.prominence = context.get_config(self, "prominence")
        self.width = context.get_config(self, "width")
        self.threshold = context.get_config(self, "threshold")
        self.height_method = context.get_config(self, "height_method")
        self.sampling_interval_ns = context.get_config(self, "sampling_interval_ns")
        daq_adapter = self._get_global_daq_adapter(context)
        if not self._has_config(context, "sampling_interval_ns"):
            self.sampling_interval_ns = self._get_sampling_interval_from_adapter(
                daq_adapter,
                self.sampling_interval_ns,
            )
        # st_waveforms 的 timestamp 已统一为 ps
        self._timestamp_unit = "ps"

        self.time_field = TIMESTAMP_FIELD
        self.length_field = EVENT_LENGTH_FIELD
        self.dt_field = "dt"
        self.endtime_field = "endtime"

        self.dt = None

    def _get_input_chunks(self, context: Any, run_id: str, **kwargs) -> Iterator[Chunk]:
        filtered_waveforms = context.get_data(run_id, "filtered_waveforms")
        st_waveforms = context.get_data(run_id, "st_waveforms")

        if len(filtered_waveforms) != len(st_waveforms):
            logger.warning(
                "filtered_waveforms 与 st_waveforms 通道数不一致: %s vs %s",
                len(filtered_waveforms),
                len(st_waveforms),
            )

        self._set_chunk_dt(st_waveforms)

        for ch_idx, (filtered_ch, st_ch) in enumerate(zip(filtered_waveforms, st_waveforms)):
            if len(st_ch) == 0 or len(filtered_ch) == 0:
                continue

            if TIMESTAMP_FIELD not in st_ch.dtype.names:
                raise KeyError(f"st_waveforms 缺少时间字段: {TIMESTAMP_FIELD}")

            n_events = min(len(filtered_ch), len(st_ch))
            if n_events == 0:
                continue

            times = st_ch[TIMESTAMP_FIELD]
            if self.break_threshold_ps and self.break_threshold_ps > 0 and n_events > 1:
                endtime_all = get_endtime(
                    st_ch,
                    time_field=TIMESTAMP_FIELD,
                    length_field=EVENT_LENGTH_FIELD,
                    dt=self.dt,
                )
                gaps = times[1:].astype(np.int64) - endtime_all[:-1].astype(np.int64)
                break_indices = np.where(gaps > self.break_threshold_ps)[0] + 1
                boundaries = np.concatenate([[0], break_indices, [n_events]])
            else:
                boundaries = np.array([0, n_events], dtype=np.int64)

            segment_id = 0
            for seg_start, seg_end in zip(boundaries[:-1], boundaries[1:]):
                if seg_end <= seg_start:
                    segment_id += 1
                    continue

                for start in range(seg_start, seg_end, self.chunk_size):
                    end = min(seg_end, start + self.chunk_size)
                    st_chunk = st_ch[start:end]
                    if len(st_chunk) == 0:
                        continue

                    filtered_chunk = filtered_ch[start:end]
                    time_values = st_chunk[TIMESTAMP_FIELD]
                    main_start = int(np.min(time_values))
                    if self.dt is not None:
                        endtime = get_endtime(
                            st_chunk,
                            time_field=TIMESTAMP_FIELD,
                            length_field=EVENT_LENGTH_FIELD,
                            dt=self.dt,
                        )
                        main_end = int(np.max(endtime))
                    else:
                        main_end = int(np.max(time_values))

                    yield Chunk(
                        data=st_chunk,
                        start=main_start,
                        end=main_end,
                        run_id=run_id,
                        data_type=self.provides,
                        time_field=TIMESTAMP_FIELD,
                        length_field=EVENT_LENGTH_FIELD,
                        dt=self.dt,
                        metadata={
                            "filtered_waveforms": filtered_chunk,
                            "event_offset": start,
                            "channel_index": ch_idx,
                            "main_start": main_start,
                            "main_end": main_end,
                            "segment_id": segment_id,
                        },
                    )
                segment_id += 1

    def compute_chunk(self, chunk: Chunk, context: Any, run_id: str, **kwargs) -> Optional[Chunk]:
        st_chunk = chunk.data
        filtered_chunk = chunk.metadata.get("filtered_waveforms")
        if filtered_chunk is None or len(st_chunk) == 0:
            return None

        peaks: List[tuple] = []
        event_offset = int(chunk.metadata.get("event_offset", 0))

        for local_idx, (filtered_waveform, st_waveform) in enumerate(zip(filtered_chunk, st_chunk)):
            timestamp = int(st_waveform[TIMESTAMP_FIELD])
            channel = int(st_waveform["channel"])
            baseline = st_waveform["baseline"] if "baseline" in st_waveform.dtype.names else None
            event_index = event_offset + local_idx

            event_peaks = self._find_peaks_in_waveform(
                filtered_waveform,
                baseline,
                timestamp,
                channel,
                event_index,
                self.use_derivative,
                self.height,
                self.distance,
                self.prominence,
                self.width,
                self.threshold,
                self.height_method,
            )

            if event_peaks:
                peaks.extend(event_peaks)

        if not peaks:
            return None

        peaks_array = np.array(peaks, dtype=ADVANCED_PEAK_DTYPE)
        start_time = int(np.min(peaks_array["timestamp"]))
        end_time = int(np.max(peaks_array["timestamp"]))

        return Chunk(
            data=peaks_array,
            start=start_time,
            end=end_time,
            run_id=run_id,
            data_type=self.provides,
            data_kind=self.output_data_kind,
            time_field=TIMESTAMP_FIELD,
        )

    def _find_peaks_in_waveform(
        self,
        waveform: np.ndarray,
        baseline: Union[float, None],
        timestamp: int,
        channel: int,
        event_index: int,
        use_derivative: bool,
        height: float,
        distance: int,
        prominence: float,
        width: int,
        threshold: Union[float, None],
        height_method: str,
    ) -> List[tuple]:
        if use_derivative:
            detection_signal = -np.diff(waveform)
        else:
            if baseline is not None:
                detection_signal = baseline - waveform
            else:
                baseline_approx = np.mean(waveform)
                detection_signal = baseline_approx - waveform

        peak_positions, properties = find_peaks(
            detection_signal,
            height=height,
            distance=distance,
            prominence=prominence,
            width=width,
            threshold=threshold,
        )

        if len(peak_positions) == 0:
            return []

        edges_start = properties["left_ips"]
        edges_end = properties["right_ips"]

        peak_heights = self._calculate_peak_heights(waveform, edges_start, edges_end, height_method)

        sampling_interval = self._get_sampling_interval(timestamp)

        peaks = []
        for pos, edge_start, edge_end, peak_height in zip(
            peak_positions, edges_start, edges_end, peak_heights
        ):
            global_timestamp = int(timestamp + pos * sampling_interval)

            peaks.append(
                (
                    int(pos),
                    float(peak_height),
                    0.0,
                    float(edge_start),
                    float(edge_end),
                    int(global_timestamp),
                    int(channel),
                    int(event_index),
                )
            )

        return peaks

    def _calculate_peak_heights(
        self,
        waveform: np.ndarray,
        edges_start: np.ndarray,
        edges_end: np.ndarray,
        method: str,
    ) -> np.ndarray:
        if method == "diff":
            diff_signal = -np.diff(waveform)
            diff_cumsum = np.concatenate(([0.0], np.cumsum(diff_signal, dtype=np.float64)))
            max_idx = len(diff_signal)

            start_idx = np.clip(np.rint(edges_start).astype(np.int64), 0, max_idx)
            end_idx = np.clip(np.rint(edges_end).astype(np.int64), 0, max_idx)

            heights = diff_cumsum[end_idx] - diff_cumsum[start_idx]
            heights = np.where(end_idx > start_idx, heights, 0.0)
            return heights.astype(np.float32, copy=False)

        if method == "minmax":
            heights = np.zeros(len(edges_start), dtype=np.float32)
            for i, (edge_start, edge_end) in enumerate(zip(edges_start, edges_end)):
                start_idx = int(np.round(edge_start))
                end_idx = int(np.round(edge_end))
                start_idx = max(0, start_idx)
                end_idx = min(len(waveform) - 1, end_idx)

                window_start = max(0, start_idx - 2)
                window_end = min(len(waveform), end_idx + 2)
                window_slice = slice(window_start, window_end)

                max_value = np.max(waveform[window_slice])
                min_value = np.min(waveform[window_slice])
                heights[i] = max_value - min_value
            return heights

        raise ValueError(f"不支持的峰高计算方法: {method}")

    def _get_sampling_interval(self, timestamp: int) -> float:
        unit = self._timestamp_unit
        if unit is None:
            if timestamp > 1e12:
                return self.sampling_interval_ns * 1e3
            return self.sampling_interval_ns

        if unit == "ps":
            return self.sampling_interval_ns * 1e3
        if unit == "ns":
            return self.sampling_interval_ns
        if unit == "us":
            return self.sampling_interval_ns * 1e-3
        if unit == "ms":
            return self.sampling_interval_ns * 1e-6
        if unit == "s":
            return self.sampling_interval_ns * 1e-9

        return self.sampling_interval_ns

    def _has_config(self, context: Any, name: str) -> bool:
        if hasattr(context, "has_explicit_config"):
            try:
                return context.has_explicit_config(self, name)
            except Exception:
                pass
        config = getattr(context, "config", {})
        provides = self.provides
        if provides in config and isinstance(config[provides], dict):
            if name in config[provides]:
                return True
        if f"{provides}.{name}" in config:
            return True
        return name in config

    def _get_sampling_interval_from_adapter(
        self,
        daq_adapter: Union[str, None],
        default_value: float,
    ) -> float:
        if not daq_adapter:
            return default_value
        try:
            from waveform_analysis.utils.formats import get_adapter
        except Exception:
            return default_value
        try:
            adapter = get_adapter(daq_adapter)
        except ValueError:
            return default_value
        sampling_rate_hz = adapter.sampling_rate_hz
        if not sampling_rate_hz:
            return default_value
        return 1e9 / float(sampling_rate_hz)

    def _set_chunk_dt(self, st_waveforms: List[np.ndarray]) -> None:
        sample_timestamp = None
        for st_ch in st_waveforms:
            if len(st_ch) > 0 and TIMESTAMP_FIELD in st_ch.dtype.names:
                sample_timestamp = int(st_ch[TIMESTAMP_FIELD][0])
                break

        if sample_timestamp is None:
            self.dt = None
            return

        self.dt = float(self._get_sampling_interval(sample_timestamp))

    def _get_global_daq_adapter(self, context: Any) -> Union[str, None]:
        config = getattr(context, "config", {})
        return config.get("daq_adapter")
