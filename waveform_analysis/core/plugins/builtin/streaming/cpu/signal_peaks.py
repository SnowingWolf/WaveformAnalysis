"""
CPU Streaming Signal Peaks Plugin.

基于滤波后的波形流式检测峰值，并返回峰值特征的 chunk 流。
时间字段使用事件的 timestamp（统一为 ps）。
"""

from collections.abc import Iterator
import logging
from typing import Any, Optional, Union

import numpy as np
from scipy.signal import find_peaks

from waveform_analysis.core.foundation.utils import exporter
from waveform_analysis.core.plugins.builtin.cpu._dt_compat import (
    require_dt_array,
    resolve_dt_config,
)
from waveform_analysis.core.plugins.builtin.cpu.peak_finding import HIT_DTYPE
from waveform_analysis.core.plugins.core.base import Option
from waveform_analysis.core.plugins.core.streaming import StreamingPlugin
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
    version = "1.2.0"
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
        "minmax_window_expand": Option(
            default=2,
            type=int,
            help="height_method='minmax' 时峰窗口左右扩展点数",
        ),
        "dt": Option(
            default=None,
            type=int,
            help="采样间隔（ns）。仅在输入数据缺少 dt 字段时作为兼容补充。",
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
        self.minmax_window_expand = max(0, int(context.get_config(self, "minmax_window_expand")))
        self.explicit_dt = resolve_dt_config(
            context,
            self,
            deprecated_keys=("sampling_interval_ns", "dt_ns"),
        )
        self.time_field = TIMESTAMP_FIELD
        self.length_field = EVENT_LENGTH_FIELD
        self.dt_field = "dt"
        self.endtime_field = "endtime"

    def _get_input_chunks(self, context: Any, run_id: str, **kwargs) -> Iterator[Chunk]:
        filtered_waveforms = context.get_data(run_id, "filtered_waveforms")
        st_waveforms = context.get_data(run_id, "st_waveforms")

        if not isinstance(filtered_waveforms, np.ndarray) or not isinstance(
            st_waveforms, np.ndarray
        ):
            raise ValueError("signal_peaks_stream expects st_waveforms as a single array")

        if len(filtered_waveforms) == 0 or len(st_waveforms) == 0:
            return iter(())

        dt_values = require_dt_array(
            st_waveforms,
            explicit_dt=self.explicit_dt,
            plugin_name=self.provides,
            data_name="st_waveforms",
        )

        channels = st_waveforms["channel"] if "channel" in st_waveforms.dtype.names else None
        if channels is None:
            raise ValueError("st_waveforms missing required 'channel' field for streaming peaks")

        for ch_idx in np.unique(channels):
            mask = channels == ch_idx
            st_ch = st_waveforms[mask]
            filtered_ch = filtered_waveforms[mask]
            dt_ch = dt_values[mask]
            if len(st_ch) == 0 or len(filtered_ch) == 0:
                continue

            if TIMESTAMP_FIELD not in st_ch.dtype.names:
                raise KeyError(f"st_waveforms 缺少时间字段: {TIMESTAMP_FIELD}")

            n_events = min(len(filtered_ch), len(st_ch))
            if n_events == 0:
                continue

            st_ch = st_ch[:n_events]
            filtered_ch = filtered_ch[:n_events]
            dt_ch = dt_ch[:n_events]
            times = st_ch[TIMESTAMP_FIELD]
            dt_change_indices = np.where(dt_ch[1:] != dt_ch[:-1])[0] + 1
            dt_boundaries = np.concatenate([[0], dt_change_indices, [n_events]])

            segment_id = 0
            for dt_seg_start, dt_seg_end in zip(
                dt_boundaries[:-1], dt_boundaries[1:], strict=False
            ):
                if dt_seg_end <= dt_seg_start:
                    segment_id += 1
                    continue

                st_dt_chunk = st_ch[dt_seg_start:dt_seg_end]
                filtered_dt_chunk = filtered_ch[dt_seg_start:dt_seg_end]
                dt_times = times[dt_seg_start:dt_seg_end]
                chunk_dt_ps = float(int(dt_ch[dt_seg_start]) * 1e3)

                if self.break_threshold_ps and self.break_threshold_ps > 0 and len(st_dt_chunk) > 1:
                    endtime_all = get_endtime(
                        st_dt_chunk,
                        time_field=TIMESTAMP_FIELD,
                        length_field=EVENT_LENGTH_FIELD,
                        dt=chunk_dt_ps,
                    )
                    gaps = dt_times[1:].astype(np.int64) - endtime_all[:-1].astype(np.int64)
                    break_indices = np.where(gaps > self.break_threshold_ps)[0] + 1
                    boundaries = np.concatenate([[0], break_indices, [len(st_dt_chunk)]])
                else:
                    boundaries = np.array([0, len(st_dt_chunk)], dtype=np.int64)

                for seg_start, seg_end in zip(boundaries[:-1], boundaries[1:], strict=False):
                    if seg_end <= seg_start:
                        segment_id += 1
                        continue

                    for start in range(seg_start, seg_end, self.chunk_size):
                        end = min(seg_end, start + self.chunk_size)
                        st_chunk = st_dt_chunk[start:end]
                        if len(st_chunk) == 0:
                            continue

                        filtered_chunk = filtered_dt_chunk[start:end]
                        time_values = st_chunk[TIMESTAMP_FIELD]
                        main_start = int(np.min(time_values))
                        endtime = get_endtime(
                            st_chunk,
                            time_field=TIMESTAMP_FIELD,
                            length_field=EVENT_LENGTH_FIELD,
                            dt=chunk_dt_ps,
                        )
                        main_end = int(np.max(endtime))

                        yield Chunk(
                            data=st_chunk,
                            start=main_start,
                            end=main_end,
                            run_id=run_id,
                            data_type=self.provides,
                            time_field=TIMESTAMP_FIELD,
                            length_field=EVENT_LENGTH_FIELD,
                            dt=chunk_dt_ps,
                            metadata={
                                "filtered_waveforms": filtered_chunk,
                                "event_offset": dt_seg_start + start,
                                "channel_index": ch_idx,
                                "main_start": main_start,
                                "main_end": main_end,
                                "segment_id": segment_id,
                            },
                        )
                    segment_id += 1

    def compute_chunk(self, chunk: Chunk, context: Any, run_id: str, **kwargs) -> Chunk | None:
        st_chunk = chunk.data
        filtered_chunk = chunk.metadata.get("filtered_waveforms")
        if filtered_chunk is None or len(st_chunk) == 0:
            return None

        peaks: list[tuple] = []
        event_offset = int(chunk.metadata.get("event_offset", 0))

        for local_idx, (filtered_waveform, st_waveform) in enumerate(
            zip(filtered_chunk, st_chunk, strict=False)
        ):
            timestamp = int(st_waveform[TIMESTAMP_FIELD])
            channel = int(st_waveform["channel"])
            board = int(st_waveform["board"]) if "board" in st_waveform.dtype.names else 0
            baseline = st_waveform["baseline"] if "baseline" in st_waveform.dtype.names else None
            dt_ns = (
                int(st_waveform["dt"]) if "dt" in st_waveform.dtype.names else int(self.explicit_dt)
            )
            record_id = (
                int(st_waveform["record_id"])
                if "record_id" in st_waveform.dtype.names
                else event_offset + local_idx
            )
            waveform = (
                np.asarray(filtered_waveform["wave"], dtype=np.float64)
                if getattr(filtered_waveform, "dtype", None) is not None
                and filtered_waveform.dtype.names
                and "wave" in filtered_waveform.dtype.names
                else np.asarray(filtered_waveform, dtype=np.float64)
            )

            event_peaks = self._find_peaks_in_waveform(
                waveform,
                baseline,
                timestamp,
                dt_ns,
                board,
                channel,
                record_id,
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

        peaks_array = np.array(peaks, dtype=HIT_DTYPE)
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
        baseline: float | None,
        timestamp: int,
        dt_ns: int,
        board: int,
        channel: int,
        record_id: int,
        use_derivative: bool,
        height: float,
        distance: int,
        prominence: float,
        width: int,
        threshold: float | None,
        height_method: str,
    ) -> list[tuple]:
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

        sampling_interval = self._get_sampling_interval(dt_ns)

        peaks = []
        for pos, edge_start, edge_end, peak_height in zip(
            peak_positions, edges_start, edges_end, peak_heights, strict=False
        ):
            global_timestamp = int(timestamp + pos * sampling_interval)

            peaks.append(
                (
                    int(pos),
                    float(peak_height),
                    0.0,
                    float(edge_start),
                    float(edge_end),
                    int(dt_ns),
                    int(global_timestamp),
                    int(board),
                    int(channel),
                    int(record_id),
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
            for i, (edge_start, edge_end) in enumerate(zip(edges_start, edges_end, strict=False)):
                start_idx = int(np.round(edge_start))
                end_idx = int(np.round(edge_end))
                start_idx = max(0, start_idx)
                end_idx = min(len(waveform) - 1, end_idx)

                # 使用最大最小值差方法（在峰值周围按配置扩展窗口）
                expand = self.minmax_window_expand
                window_start = max(0, start_idx - expand)
                window_end = min(len(waveform), end_idx + expand)
                window_slice = slice(window_start, window_end)

                max_value = np.max(waveform[window_slice])
                min_value = np.min(waveform[window_slice])
                heights[i] = max_value - min_value
            return heights

        raise ValueError(f"不支持的峰高计算方法: {method}")

    def _get_sampling_interval(self, dt_ns: int) -> float:
        if dt_ns <= 0:
            raise ValueError("[signal_peaks_stream] dt must be > 0")
        return float(dt_ns) * 1e3
