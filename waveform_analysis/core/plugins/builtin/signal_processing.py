# -*- coding: utf-8 -*-
"""
Signal Processing Plugins 模块 - 包含波形滤波和寻峰等信号处理插件。

提供了高级信号处理功能，包括：
- FilteredWaveformsPlugin: 波形滤波（Butterworth 带通滤波、Savitzky-Golay 滤波）
- PeaksPlugin: 基于滤波波形的峰值检测
"""

from typing import Any, List, Union

import numpy as np
from scipy.signal import butter, find_peaks, savgol_filter, sosfiltfilt

from ..core.base import Option, Plugin

# 定义峰值数据类型（扩展自原始 PEAK_DTYPE，增加边缘信息）
ADVANCED_PEAK_DTYPE = np.dtype(
    [
        ("position", "i8"),  # 峰值位置（采样点索引）
        ("height", "f4"),  # 峰值高度
        ("integral", "f4"),  # 峰值积分（面积）
        ("edge_start", "f4"),  # 峰值起始边缘（左边界）
        ("edge_end", "f4"),  # 峰值结束边缘（右边界）
        ("timestamp", "i8"),  # 事件时间戳
        ("channel", "i2"),  # 通道号
        ("event_index", "i8"),  # 事件索引
    ]
)


class FilteredWaveformsPlugin(Plugin):
    """
    波形滤波插件 - 提供多种滤波方法以去除噪声和平滑波形。

    支持的滤波方法：
    - Butterworth 带通滤波器 (BW)
    - Savitzky-Golay 滤波器 (SG)
    """

    provides = "filtered_waveforms"
    depends_on = ["st_waveforms"]
    description = "Apply filtering to waveforms using Butterworth or Savitzky-Golay filters."
    version = "1.0.0"
    save_when = "target"  # 滤波波形较大，按需保存

    options = {
        "filter_type": Option(
            default="SG",
            type=str,
            help="滤波器类型: 'BW' (Butterworth) 或 'SG' (Savitzky-Golay)",
        ),
        "lowcut": Option(
            default=0.1,
            type=float,
            help="带通滤波器低频截止频率（仅用于 BW 滤波器）",
        ),
        "highcut": Option(
            default=0.5,
            type=float,
            help="带通滤波器高频截止频率（仅用于 BW 滤波器）",
        ),
        "fs": Option(
            default=1.0,
            type=float,
            help="采样率（仅用于 BW 滤波器）",
        ),
        "filter_order": Option(
            default=4,
            type=int,
            help="滤波器阶数（仅用于 BW 滤波器）",
        ),
        "sg_window_size": Option(
            default=11,
            type=int,
            help="Savitzky-Golay 滤波器窗口大小（必须为奇数，仅用于 SG 滤波器）",
        ),
        "sg_poly_order": Option(
            default=2,
            type=int,
            help="Savitzky-Golay 滤波器多项式阶数（仅用于 SG 滤波器）",
        ),
    }

    def compute(self, context: Any, run_id: str, **_kwargs) -> List[np.ndarray]:
        """
        对波形应用滤波处理

        从结构化波形数据中提取波形数组，应用配置的滤波方法，
        返回滤波后的波形数据。

        Args:
            context: Context 实例
            run_id: 运行标识符
            **_kwargs: 依赖数据（未使用，通过 context.get_data 获取）

        Returns:
            List[np.ndarray]: 每个通道的滤波后波形列表，每个数组形状为 (n_events, n_samples)

        Examples:
            >>> ctx.register_plugin(FilteredWaveformsPlugin())
            >>> ctx.set_config({'filter_type': 'SG', 'sg_window_size': 11}, plugin_name='filtered_waveforms')
            >>> filtered = ctx.get_data('run_001', 'filtered_waveforms')
            >>> print(f"通道0滤波波形形状: {filtered[0].shape}")
        """
        # 获取配置参数
        filter_type = context.get_config(self, "filter_type")

        # 获取结构化波形数据
        st_waveforms = context.get_data(run_id, "st_waveforms")

        filtered_waveforms_list = []

        for st_ch in st_waveforms:
            if len(st_ch) == 0:
                # 空通道，添加空数组
                filtered_waveforms_list.append(np.zeros((0, 0), dtype=np.float32))
                continue

            # 提取波形数据 (n_events, n_samples)
            waveforms = np.stack(st_ch["wave"])
            n_events = len(waveforms)

            # 对每个事件应用滤波
            filtered_waveforms = np.zeros_like(waveforms, dtype=np.float32)

            for event_idx in range(n_events):
                waveform = waveforms[event_idx]
                filtered_waveforms[event_idx] = self._apply_filter(
                    waveform, filter_type, context
                )

            filtered_waveforms_list.append(filtered_waveforms)

        return filtered_waveforms_list

    def _apply_filter(
        self, waveform: np.ndarray, filter_type: str, context: Any
    ) -> np.ndarray:
        """
        对单个波形应用滤波

        Args:
            waveform: 单个波形数组
            filter_type: 滤波器类型 ('BW' 或 'SG')
            context: Context 实例，用于获取配置

        Returns:
            滤波后的波形数组
        """
        if filter_type == "BW":
            # Butterworth 带通滤波
            lowcut = context.get_config(self, "lowcut")
            highcut = context.get_config(self, "highcut")
            fs = context.get_config(self, "fs")
            order = context.get_config(self, "filter_order")

            nyquist = 0.5 * fs
            low = lowcut / nyquist
            high = highcut / nyquist

            # 使用 Butterworth 带通滤波器
            sos = butter(order, [low, high], btype="band", output='sos')
            filtered = sosfiltfilt(sos, waveform)

        elif filter_type == "SG":
            # Savitzky-Golay 滤波
            window_size = context.get_config(self, "sg_window_size")
            poly_order = context.get_config(self, "sg_poly_order")

            # 确保窗口大小为奇数且不超过波形长度
            if window_size % 2 == 0:
                window_size += 1
            window_size = min(window_size, len(waveform))
            if window_size <= poly_order:
                # 窗口太小，无法应用滤波，返回原波形
                return waveform.astype(np.float32)

            filtered = savgol_filter(waveform, window_size, poly_order)

        else:
            raise ValueError(
                f"不支持的滤波器类型: {filter_type}. 请使用 'BW' 或 'SG'."
            )

        return filtered.astype(np.float32)


class SignalPeaksPlugin(Plugin):
    """
    峰值检测插件 - 基于滤波后的波形检测峰值并计算峰值特征。

    使用 scipy.signal.find_peaks 进行峰值检测，支持多种峰值筛选条件。
    计算峰值的位置、高度、积分、边缘等特征。

    注意：此插件命名为 SignalPeaksPlugin 以区别于标准 PeaksPlugin。
    """

    provides = "signal_peaks"
    depends_on = ["filtered_waveforms", "st_waveforms"]
    description = "Detect peaks in filtered waveforms and extract peak features."
    version = "1.0.0"
    save_when = "always"  # 峰值数据较小，总是保存
    output_dtype = ADVANCED_PEAK_DTYPE

    options = {
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
            default="diff",
            type=str,
            help="峰高计算方法: 'diff' (积分差分) 或 'minmax' (最大最小值差)",
        ),
    }

    def compute(self, context: Any, run_id: str, **_kwargs) -> List[np.ndarray]:
        """
        从滤波后的波形中检测峰值

        使用配置的参数检测每个事件中的峰值，计算峰值特征
        （位置、高度、积分、边缘等）。

        Args:
            context: Context 实例
            run_id: 运行标识符
            **_kwargs: 依赖数据（未使用，通过 context.get_data 获取）

        Returns:
            List[np.ndarray]: 每个通道的峰值列表，dtype 为 ADVANCED_PEAK_DTYPE

        Examples:
            >>> ctx.register_plugin(PeaksPlugin())
            >>> ctx.set_config({'height': 30, 'prominence': 0.7}, plugin_name='peaks')
            >>> peaks = ctx.get_data('run_001', 'peaks')
            >>> print(f"通道0的峰值数: {len(peaks[0])}")
        """
        # 获取配置参数
        use_derivative = context.get_config(self, "use_derivative")
        height = context.get_config(self, "height")
        distance = context.get_config(self, "distance")
        prominence = context.get_config(self, "prominence")
        width = context.get_config(self, "width")
        threshold = context.get_config(self, "threshold")
        height_method = context.get_config(self, "height_method")

        # 获取依赖数据
        filtered_waveforms = context.get_data(run_id, "filtered_waveforms")
        st_waveforms = context.get_data(run_id, "st_waveforms")

        peaks_list = []

        for filtered_ch, st_ch in zip(filtered_waveforms, st_waveforms):
            if len(filtered_ch) == 0 or len(st_ch) == 0:
                # 空通道，添加空数组
                peaks_list.append(np.zeros(0, dtype=ADVANCED_PEAK_DTYPE))
                continue

            channel_peaks = []

            for event_idx, (filtered_waveform, st_waveform) in enumerate(zip(filtered_ch, st_ch)):
                timestamp = st_waveform["timestamp"]
                channel = st_waveform["channel"]

                # 检测峰值
                event_peaks = self._find_peaks_in_waveform(
                    filtered_waveform,
                    timestamp,
                    channel,
                    event_idx,
                    use_derivative,
                    height,
                    distance,
                    prominence,
                    width,
                    threshold,
                    height_method,
                )

                if len(event_peaks) > 0:
                    channel_peaks.extend(event_peaks)

            # 转换为结构化数组
            if len(channel_peaks) > 0:
                peaks_array = np.array(channel_peaks, dtype=ADVANCED_PEAK_DTYPE)
            else:
                peaks_array = np.zeros(0, dtype=ADVANCED_PEAK_DTYPE)

            peaks_list.append(peaks_array)

        return peaks_list

    def _find_peaks_in_waveform(
        self,
        waveform: np.ndarray,
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
        """
        在单个波形中检测峰值

        Args:
            waveform: 滤波后的波形数组
            timestamp: 事件时间戳
            channel: 通道号
            event_index: 事件索引
            use_derivative: 是否使用导数检测峰值
            height: 最小峰高
            distance: 最小峰间距
            prominence: 最小显著性
            width: 最小宽度
            threshold: 阈值条件
            height_method: 峰高计算方法

        Returns:
            峰值特征元组列表
        """
        # 根据配置选择检测波形或其导数
        if use_derivative:
            # 使用一阶导数的负值（下降沿代表原波形的峰值）
            detection_signal = -np.diff(waveform)
        else:
            detection_signal = waveform

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
                waveform, edge_start, edge_end, height_method
            )

            # 计算峰积分（这里简单设置为 None，后续可扩展）
            peak_integral = None

            peak_tuple = (
                int(pos),  # position
                float(peak_height),  # height
                float(peak_integral) if peak_integral is not None else 0.0,  # integral
                float(edge_start),  # edge_start
                float(edge_end),  # edge_end
                int(timestamp),  # timestamp
                int(channel),  # channel
                int(event_index),  # event_index
            )
            peaks.append(peak_tuple)

        return peaks

    def _calculate_peak_height(
        self, waveform: np.ndarray, edge_start: float, edge_end: float, method: str
    ) -> float:
        """
        计算峰值高度

        Args:
            waveform: 波形数组
            edge_start: 峰值起始边缘
            edge_end: 峰值结束边缘
            method: 计算方法 ('diff' 或 'minmax')

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
            window_start = max(0, start_idx - 2)
            window_end = min(len(waveform), end_idx + 2)
            window_slice = slice(window_start, window_end)

            max_value = np.max(waveform[window_slice])
            min_value = np.min(waveform[window_slice])
            peak_height = max_value - min_value
        else:
            raise ValueError(f"不支持的峰高计算方法: {method}")

        return float(peak_height)
