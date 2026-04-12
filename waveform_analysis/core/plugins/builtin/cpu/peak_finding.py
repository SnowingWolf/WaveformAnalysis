"""
CPU Peak Finding Plugin - 使用 scipy 进行峰值检测

**加速器**: CPU (scipy)
**功能**: 基于波形检测峰值并计算峰值特征

本插件使用 scipy.signal.find_peaks 进行峰值检测，支持多种峰值筛选条件。
计算峰值的位置、高度、积分、边缘等特征。

支持使用原始波形或滤波后的波形进行检测。
"""

from concurrent.futures import ThreadPoolExecutor
import os
from typing import Any, Optional, Union

import numpy as np
from scipy.signal import find_peaks

from waveform_analysis.core.plugins.builtin.cpu._dt_compat import resolve_dt_config
from waveform_analysis.core.plugins.builtin.cpu._wave_source import (
    WAVE_SOURCE_AUTO,
    LoadedWaveInput,
    load_wave_input,
    resolve_wave_input_spec,
)
from waveform_analysis.core.plugins.core.base import Option, Plugin

# 定义峰值数据类型（扩展自原始 PEAK_DTYPE，增加边缘信息）
HIT_DTYPE = np.dtype(
    [
        ("position", "i8"),  # 峰值位置（采样点索引）
        ("height", "f4"),  # 峰值高度
        ("integral", "f4"),  # 峰值积分（面积）
        ("edge_start", "f4"),  # 峰值起始边缘（左边界）
        ("edge_end", "f4"),  # 峰值结束边缘（右边界）
        ("dt", "i4"),  # 采样间隔（ns）
        ("timestamp", "i8"),  # 全局时间戳（事件时间戳 + 峰值位置 * 采样间隔）
        ("board", "i2"),  # 板卡编号
        ("channel", "i2"),  # 通道号
        ("record_id", "i8"),  # 来源波形/记录的唯一编号
    ]
)

# Backward-compatible alias used by legacy imports and streaming plugins.
ADVANCED_PEAK_DTYPE = HIT_DTYPE


class HitFinderPlugin(Plugin):
    """
    峰值检测插件 - 基于波形检测峰值并计算峰值特征。

    使用 scipy.signal.find_peaks 进行峰值检测，支持多种峰值筛选条件。
    计算峰值的位置、高度、积分、边缘等特征。

    注意：此插件是当前唯一官方 Hit 检测接口（provides="hit"）。

    配置示例：
        >>> ctx.set_config({
        ...     'dt': 2,
        ...     'use_filtered': True,  # 使用滤波后的波形
        ... }, plugin_name='hit')
    """

    provides = "hit"
    depends_on = []  # 动态依赖，由 resolve_depends_on 决定
    description = "Detect peaks in waveforms and extract peak features."
    version = "3.0.0"  # 版本升级：hit 输出使用 record_id 替代 event_index
    save_when = "always"  # 峰值数据较小，总是保存
    output_dtype = HIT_DTYPE

    options = {
        "use_filtered": Option(
            default=True,
            type=bool,
            help="是否使用 filtered_waveforms（默认 True，需要先注册 FilteredWaveformsPlugin）",
        ),
        "wave_source": Option(
            default=WAVE_SOURCE_AUTO,
            type=str,
            help="波形数据源: auto|records|st_waveforms|filtered_waveforms",
        ),
        "use_derivative": Option(
            default=True,
            type=bool,
            help="是否使用一阶导数进行峰值检测（True: 检测导数峰值, False: 检测波形峰值）",
        ),
        "height": Option(
            default=30.0,
            type=float,
            help="峰值的最小高度阈值",
        ),
        "distance": Option(
            default=2,
            type=int,
            help="峰值之间的最小距离（采样点数）",
        ),
        "prominence": Option(
            default=0.7,
            type=float,
            help="峰值的最小显著性（prominence）",
        ),
        "width": Option(
            default=4,
            type=int,
            help="峰值的最小宽度（采样点数）",
        ),
        "threshold": Option(
            default=None,
            help="峰值的阈值条件（可选）",
        ),
        "height_method": Option(
            default="minmax",
            type=str,
            help="峰高计算方法: 'diff' (积分差分) 或 'minmax' (最大最小值差)",
        ),
        "height_window_extension": Option(
            default=4,
            type=int,
            help="height_method='minmax' 时，峰值窗口左右两侧扩展的采样点数",
        ),
        "dt": Option(
            default=None,
            type=int,
            help="采样间隔（ns）。仅在输入数据缺少 dt 字段时作为兼容补充。",
        ),
        "parallel": Option(
            default=True,
            type=bool,
            help="是否启用并行峰值检测（按事件分块并行）",
        ),
        "n_workers": Option(
            default=0,
            type=int,
            help="并行 worker 数；<=0 表示自动（基于 CPU 核心数）",
        ),
        "chunk_size": Option(
            default=1024,
            type=int,
            help="并行分块大小（每个任务处理的事件数）",
        ),
        "parallel_min_events": Option(
            default=20480,
            type=int,
            help="触发并行的最小事件数（小数据量时自动串行）",
        ),
    }

    def resolve_depends_on(self, context: Any, run_id: str | None = None) -> list[str]:
        spec = resolve_wave_input_spec(context, self)
        return list(spec.depends_on)

    def compute(self, context: Any, run_id: str, **_kwargs) -> np.ndarray:
        """
        从波形中检测峰值

        使用配置的参数检测每个事件中的峰值，计算峰值特征
        （位置、高度、积分、边缘等）。

        Args:
            context: Context 实例
            run_id: 运行标识符
            **_kwargs: 依赖数据（未使用，通过 context.get_data 获取）

        Returns:
            np.ndarray: 峰值结构化数组，dtype 为 HIT_DTYPE

        Examples:
            >>> ctx.register(HitFinderPlugin())
            >>> ctx.set_config({'height': 30, 'prominence': 0.7}, plugin_name='hit')
            >>> peaks = ctx.get_data('run_001', 'hit')
            >>> print(f"峰值数: {len(peaks)}")
        """
        # 获取配置参数
        use_derivative = context.get_config(self, "use_derivative")
        height = context.get_config(self, "height")
        distance = context.get_config(self, "distance")
        prominence = context.get_config(self, "prominence")
        width = context.get_config(self, "width")
        threshold = context.get_config(self, "threshold")
        height_method = context.get_config(self, "height_method")
        height_window_extension = context.get_config(self, "height_window_extension")
        explicit_dt = resolve_dt_config(
            context, self, deprecated_keys=("sampling_interval_ns", "dt_ns")
        )
        parallel = context.get_config(self, "parallel")
        n_workers = context.get_config(self, "n_workers")
        chunk_size = context.get_config(self, "chunk_size")
        parallel_min_events = context.get_config(self, "parallel_min_events")
        # st_waveforms 的 timestamp 已统一为 ps
        timestamp_unit = "ps"
        wave_input = load_wave_input(context, self, run_id, needs_wave_samples=True)

        peaks = self._compute_peaks(
            wave_input=wave_input,
            use_derivative=bool(use_derivative),
            height=float(height),
            distance=int(distance),
            prominence=float(prominence),
            width=int(width),
            threshold=threshold,
            height_method=str(height_method),
            height_window_extension=int(height_window_extension),
            explicit_dt=explicit_dt,
            timestamp_unit=timestamp_unit,
            parallel=bool(parallel),
            n_workers=int(n_workers),
            chunk_size=int(chunk_size),
            parallel_min_events=int(parallel_min_events),
        )

        if peaks:
            return np.array(peaks, dtype=HIT_DTYPE)
        return np.zeros(0, dtype=HIT_DTYPE)

    def _compute_peaks(
        self,
        wave_input: LoadedWaveInput,
        use_derivative: bool,
        height: float,
        distance: int,
        prominence: float,
        width: int,
        threshold: float | None,
        height_method: str,
        height_window_extension: int,
        explicit_dt: int | None,
        timestamp_unit: str | None,
        parallel: bool,
        n_workers: int,
        chunk_size: int,
        parallel_min_events: int,
    ) -> list[tuple]:
        if wave_input.spec.is_records:
            rv = wave_input.records_view
            records = wave_input.records
            if rv is None or records is None:
                raise ValueError("hit failed to load records_view for records source")
            n_events = len(records)
            if n_events == 0:
                return []

            process_fn = self._process_records_range
            process_args = (rv,)
        else:
            waveform_data = wave_input.waveform_data
            if waveform_data is None:
                raise ValueError("hit failed to load waveform input")

            n_events = len(waveform_data)
            if n_events == 0:
                return []

            process_fn = self._process_event_range
            process_args = (waveform_data,)

        peaks: list[tuple] = []
        use_parallel = bool(parallel) and n_events >= max(1, int(parallel_min_events))
        resolved_workers = self._resolve_parallel_workers(int(n_workers), n_events)
        resolved_chunk_size = max(1, int(chunk_size))

        if use_parallel and resolved_workers > 1:
            ranges = [
                (start, min(start + resolved_chunk_size, n_events))
                for start in range(0, n_events, resolved_chunk_size)
            ]
            with ThreadPoolExecutor(max_workers=resolved_workers) as executor:
                futures = [
                    executor.submit(
                        process_fn,
                        *process_args,
                        start,
                        end,
                        use_derivative,
                        height,
                        distance,
                        prominence,
                        width,
                        threshold,
                        height_method,
                        height_window_extension,
                        explicit_dt,
                        timestamp_unit,
                    )
                    for start, end in ranges
                ]
                for future in futures:
                    chunk_peaks = future.result()
                    if chunk_peaks:
                        peaks.extend(chunk_peaks)
            return peaks

        return process_fn(
            *process_args,
            0,
            n_events,
            use_derivative,
            height,
            distance,
            prominence,
            width,
            threshold,
            height_method,
            height_window_extension,
            explicit_dt,
            timestamp_unit,
        )

    def _resolve_parallel_workers(self, n_workers: int, n_events: int) -> int:
        if n_workers > 0:
            return min(n_workers, max(1, n_events))
        cpu_count = os.cpu_count() or 1
        auto_workers = min(32, cpu_count)
        return min(auto_workers, max(1, n_events))

    def _process_event_range(
        self,
        waveform_data: np.ndarray,
        start: int,
        end: int,
        use_derivative: bool,
        height: float,
        distance: int,
        prominence: float,
        width: int,
        threshold: float | None,
        height_method: str,
        height_window_extension: int,
        explicit_dt: int | None,
        timestamp_unit: str | None,
    ) -> list[tuple]:
        peaks: list[tuple] = []
        for event_idx in range(start, end):
            st_waveform = waveform_data[event_idx]
            waveform = st_waveform["wave"]
            # Truncate to valid samples (rest may be NaN-padded)
            event_len = (
                int(st_waveform["event_length"])
                if "event_length" in st_waveform.dtype.names
                else len(waveform)
            )
            if event_len > 0 and event_len < len(waveform):
                waveform = waveform[:event_len]
            timestamp = st_waveform["timestamp"]
            board = st_waveform["board"] if "board" in st_waveform.dtype.names else 0
            channel = st_waveform["channel"] if "channel" in st_waveform.dtype.names else 0
            record_id = (
                int(st_waveform["record_id"])
                if "record_id" in st_waveform.dtype.names
                else int(event_idx)
            )
            baseline = st_waveform["baseline"] if "baseline" in st_waveform.dtype.names else None
            if "dt" in st_waveform.dtype.names:
                dt_ns = int(st_waveform["dt"])
            elif explicit_dt is not None:
                dt_ns = int(explicit_dt)
            else:
                raise ValueError(
                    "[hit] st_waveforms is missing required field 'dt'; provide explicit config 'dt'."
                )

            event_peaks = self._find_peaks_in_waveform(
                waveform,
                baseline,
                timestamp,
                board,
                channel,
                record_id,
                use_derivative,
                height,
                distance,
                prominence,
                width,
                threshold,
                height_method,
                height_window_extension,
                dt_ns,
                timestamp_unit,
            )
            if event_peaks:
                peaks.extend(event_peaks)
        return peaks

    def _process_records_range(
        self,
        rv: Any,
        start: int,
        end: int,
        use_derivative: bool,
        height: float,
        distance: int,
        prominence: float,
        width: int,
        threshold: float | None,
        height_method: str,
        height_window_extension: int,
        explicit_dt: int | None,
        timestamp_unit: str | None,
    ) -> list[tuple]:
        peaks: list[tuple] = []
        records = rv.records
        for event_idx in range(start, end):
            record = records[event_idx]
            record_id = (
                int(record["record_id"]) if "record_id" in records.dtype.names else event_idx
            )
            signal = -rv.signals(record_id).astype(np.float64, copy=False)
            if signal.size == 0:
                continue

            timestamp = int(record["timestamp"])
            board = int(record["board"]) if "board" in records.dtype.names else 0
            channel = int(record["channel"]) if "channel" in records.dtype.names else 0
            if "dt" in records.dtype.names:
                dt_ns = int(record["dt"])
            elif explicit_dt is not None:
                dt_ns = int(explicit_dt)
            else:
                raise ValueError(
                    "[hit] records is missing required field 'dt'; provide explicit config 'dt'."
                )

            event_peaks = self._find_peaks_in_waveform(
                signal,
                0.0,
                timestamp,
                board,
                channel,
                record_id,
                use_derivative,
                height,
                distance,
                prominence,
                width,
                threshold,
                height_method,
                height_window_extension,
                dt_ns,
                timestamp_unit,
                pulse_polarity="positive",
            )
            if event_peaks:
                peaks.extend(event_peaks)
        return peaks

    def _find_peaks_in_waveform(
        self,
        waveform: np.ndarray,
        baseline: float | None,
        timestamp: int,
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
        height_window_extension: int,
        dt_ns: int,
        timestamp_unit: str | None,  # 新增参数
        pulse_polarity: str = "negative",
    ) -> list[tuple]:
        """
        在单个波形中检测峰值

        Args:
            waveform: 滤波后的波形数组
            baseline: 基线值（用于反转法检测负脉冲）
            timestamp: 事件时间戳（事件开始时间）
            channel: 通道号
            record_id: 来源波形/记录 ID
            use_derivative: 是否使用导数检测峰值
            height: 最小峰高
            distance: 最小峰间距
            prominence: 最小显著性
            width: 最小宽度
            threshold: 阈值条件
            height_method: 峰高计算方法
            height_window_extension: minmax 峰高计算时窗口扩展点数
            dt_ns: 采样间隔（纳秒），用于计算全局时间戳
            timestamp_unit: 时间戳单位（st_waveforms 中已统一为 'ps'）

        Returns:
            峰值特征元组数组
        """
        # 根据配置选择检测波形或其导数
        if use_derivative:
            # 负脉冲用 -diff，正脉冲用 +diff，将上升沿统一成正峰值。
            if pulse_polarity == "positive":
                detection_signal = np.diff(waveform)
            else:
                detection_signal = -np.diff(waveform)
        else:
            if pulse_polarity == "positive":
                if baseline is not None:
                    detection_signal = waveform - baseline
                else:
                    detection_signal = waveform
            else:
                # 反转法：使用 baseline - waveform 来检测负脉冲的谷值
                # 对于负脉冲：波形谷值 -> (baseline - waveform) 后变成峰值
                if baseline is not None:
                    detection_signal = baseline - waveform
                else:
                    # 如果没有 baseline，使用波形均值作为基线
                    baseline_approx = np.mean(waveform)
                    detection_signal = baseline_approx - waveform

        # 检测峰值
        peak_positions, properties = find_peaks(
            detection_signal,
            height=height,
            distance=distance,
            prominence=prominence,
            width=width,
            threshold=threshold,
        )

        # 提取峰值特征
        peaks = []
        for i, pos in enumerate(peak_positions):
            edge_start = properties["left_ips"][i]
            edge_end = properties["right_ips"][i]

            # 计算峰高
            peak_height = self._calculate_peak_height(
                waveform,
                edge_start,
                edge_end,
                height_method,
                height_window_extension,
            )

            # 计算峰积分（这里简单设置为 None，后续可扩展）
            peak_integral = None

            # 标准链路中的 timestamp 固定为 ps，采样间隔固定使用 dt(ns)->ps。
            if dt_ns <= 0:
                raise ValueError("[hit] dt must be > 0")
            if timestamp_unit not in (None, "ps"):
                raise ValueError(
                    f"[hit] unsupported timestamp_unit in standardized pipeline: {timestamp_unit}"
                )

            sampling_interval_ps = dt_ns * 1e3
            global_timestamp = int(timestamp + pos * sampling_interval_ps)

            peak_tuple = (
                int(pos),  # position
                float(peak_height),  # height
                float(peak_integral) if peak_integral is not None else 0.0,  # integral
                float(edge_start),  # edge_start
                float(edge_end),  # edge_end
                int(dt_ns),  # dt
                int(global_timestamp),  # timestamp: 全局时间戳
                int(board),  # board
                int(channel),  # channel
                int(record_id),  # record_id
            )
            peaks.append(peak_tuple)

        return peaks

    def _calculate_peak_height(
        self,
        waveform: np.ndarray,
        edge_start: float,
        edge_end: float,
        method: str,
        window_extension: int = 2,
    ) -> float:
        """
        计算峰值高度

        Args:
            waveform: 波形数组
            edge_start: 峰值起始边缘
            edge_end: 峰值结束边缘
            method: 计算方法 ('diff' 或 'minmax')
            window_extension: minmax 计算时窗口扩展点数

        Returns:
            峰值高度
        """
        start_idx = int(np.round(edge_start))
        end_idx = int(np.round(edge_end))

        # 确保索引在有效范围内
        start_idx = max(0, start_idx)
        end_idx = min(len(waveform) - 1, end_idx)

        if method == "diff":
            # 使用差分积分方法
            if end_idx > start_idx:
                peak_height = np.sum(np.diff(-waveform)[start_idx:end_idx])
            else:
                peak_height = 0.0
        elif method == "minmax":
            # 使用最大最小值差方法（在峰值周围扩展窗口）
            ext = max(0, int(window_extension))
            window_start = max(0, start_idx - ext)
            window_end = min(len(waveform), end_idx + ext)
            window_slice = slice(window_start, window_end)

            max_value = np.max(waveform[window_slice])
            min_value = np.min(waveform[window_slice])
            peak_height = max_value - min_value
        else:
            raise ValueError(f"不支持的峰高计算方法: {method}")

        return float(peak_height)


__all__ = [
    "HIT_DTYPE",
    "HitFinderPlugin",
]
