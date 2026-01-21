# -*- coding: utf-8 -*-
"""
CPU Peak Finding Plugin - 使用 scipy 进行峰值检测

**加速器**: CPU (scipy)
**功能**: 基于滤波后的波形检测峰值并计算峰值特征

本插件使用 scipy.signal.find_peaks 进行峰值检测，支持多种峰值筛选条件。
计算峰值的位置、高度、积分、边缘等特征。
"""

from typing import Any, List, Union

import numpy as np
from scipy.signal import find_peaks

from ...core.base import Option, Plugin


# 定义峰值数据类型（扩展自原始 PEAK_DTYPE，增加边缘信息）
ADVANCED_PEAK_DTYPE = np.dtype(
    [
        ("position", "i8"),  # 峰值位置（采样点索引）
        ("height", "f4"),  # 峰值高度
        ("integral", "f4"),  # 峰值积分（面积）
        ("edge_start", "f4"),  # 峰值起始边缘（左边界）
        ("edge_end", "f4"),  # 峰值结束边缘（右边界）
        ("timestamp", "i8"),  # 全局时间戳（事件时间戳 + 峰值位置 * 采样间隔）
        ("channel", "i2"),  # 通道号
        ("event_index", "i8"),  # 事件索引
    ]
)


class SignalPeaksPlugin(Plugin):
    """
    峰值检测插件 - 基于滤波后的波形检测峰值并计算峰值特征。

    使用 scipy.signal.find_peaks 进行峰值检测，支持多种峰值筛选条件。
    计算峰值的位置、高度、积分、边缘等特征。

    注意：此插件命名为 SignalPeaksPlugin 以区别于标准 PeaksPlugin。

    配置示例：
        >>> # 使用 VX2730 适配器（时间戳单位为皮秒）
        >>> ctx.set_config({
        ...     'daq_adapter': 'vx2730',
        ...     'sampling_interval_ns': 2.0,
        ... }, plugin_name='signal_peaks')

        >>> # 不指定适配器（向后兼容，使用数值判断）
        >>> ctx.set_config({
        ...     'sampling_interval_ns': 2.0,
        ... }, plugin_name='signal_peaks')
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
        "sampling_interval_ns": Option(
            default=2.0,
            type=float,
            help="采样间隔（纳秒），用于计算全局时间戳。默认 2.0 ns",
        ),
        "daq_adapter": Option(
            default=None,
            type=str,
            help="DAQ 适配器名称（如 'vx2730'），用于确定时间戳单位。未指定时使用数值判断逻辑",
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
            >>> ctx.register_plugin(SignalPeaksPlugin())
            >>> ctx.set_config({'height': 30, 'prominence': 0.7}, plugin_name='signal_peaks')
            >>> peaks = ctx.get_data('run_001', 'signal_peaks')
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
        sampling_interval_ns = context.get_config(self, "sampling_interval_ns")
        daq_adapter = context.get_config(self, "daq_adapter")

        # 确定时间戳单位
        timestamp_unit = self._get_timestamp_unit(daq_adapter)

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
                # 获取 baseline（用于反转法检测负脉冲）
                baseline = st_waveform["baseline"] if "baseline" in st_waveform.dtype.names else None

                # 检测峰值
                event_peaks = self._find_peaks_in_waveform(
                    filtered_waveform,
                    baseline,
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
                    sampling_interval_ns,
                    timestamp_unit,  # 新增参数
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
        sampling_interval_ns: float,
        timestamp_unit: Union[str, None],  # 新增参数
    ) -> List[tuple]:
        """
        在单个波形中检测峰值

        Args:
            waveform: 滤波后的波形数组
            baseline: 基线值（用于反转法检测负脉冲）
            timestamp: 事件时间戳（事件开始时间）
            channel: 通道号
            event_index: 事件索引
            use_derivative: 是否使用导数检测峰值
            height: 最小峰高
            distance: 最小峰间距
            prominence: 最小显著性
            width: 最小宽度
            threshold: 阈值条件
            height_method: 峰高计算方法
            sampling_interval_ns: 采样间隔（纳秒），用于计算全局时间戳
            timestamp_unit: 时间戳单位 ('ps', 'ns', 'us', 'ms', 's')，
                            None 表示使用旧的数值判断逻辑

        Returns:
            峰值特征元组列表
        """
        # 根据配置选择检测波形或其导数
        if use_derivative:
            # 使用一阶导数的负值（下降沿代表原波形的峰值）
            detection_signal = -np.diff(waveform)
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
                waveform, edge_start, edge_end, height_method
            )

            # 计算峰积分（这里简单设置为 None，后续可扩展）
            peak_integral = None

            # 计算全局时间戳：事件时间戳 + 峰值位置 * 采样间隔
            # 根据时间戳单位调整采样间隔
            if timestamp_unit is None:
                # 向后兼容：使用旧的数值判断逻辑
                if timestamp > 1e12:
                    sampling_interval = sampling_interval_ns * 1e3  # ns -> ps
                else:
                    sampling_interval = sampling_interval_ns
            else:
                # 使用适配器提供的时间戳单位
                if timestamp_unit == "ps":
                    # 时间戳是皮秒，采样间隔也转换为皮秒
                    sampling_interval = sampling_interval_ns * 1e3  # ns -> ps
                elif timestamp_unit == "ns":
                    # 时间戳是纳秒，采样间隔保持纳秒
                    sampling_interval = sampling_interval_ns
                elif timestamp_unit == "us":
                    # 时间戳是微秒，采样间隔转换为微秒
                    sampling_interval = sampling_interval_ns * 1e-3  # ns -> us
                elif timestamp_unit == "ms":
                    # 时间戳是毫秒，采样间隔转换为毫秒
                    sampling_interval = sampling_interval_ns * 1e-6  # ns -> ms
                elif timestamp_unit == "s":
                    # 时间戳是秒，采样间隔转换为秒
                    sampling_interval = sampling_interval_ns * 1e-9  # ns -> s
                else:
                    # 未知单位，使用纳秒
                    sampling_interval = sampling_interval_ns

            global_timestamp = int(timestamp + pos * sampling_interval)

            peak_tuple = (
                int(pos),  # position
                float(peak_height),  # height
                float(peak_integral) if peak_integral is not None else 0.0,  # integral
                float(edge_start),  # edge_start
                float(edge_end),  # edge_end
                int(global_timestamp),  # timestamp: 全局时间戳
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

    def _get_timestamp_unit(self, daq_adapter: Union[str, None]) -> Union[str, None]:
        """
        获取时间戳单位

        Args:
            daq_adapter: DAQ 适配器名称

        Returns:
            时间戳单位字符串 ('ps', 'ns', 'us', 'ms', 's')，
            None 表示未指定适配器（使用旧的数值判断逻辑）
        """
        if daq_adapter is None:
            # 向后兼容：未指定适配器时返回 None，使用旧逻辑
            return None

        try:
            from waveform_analysis.utils.formats import get_adapter

            adapter = get_adapter(daq_adapter)
            return adapter.format_spec.timestamp_unit.value  # 返回 'ps', 'ns' 等
        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.warning(f"无法获取适配器 '{daq_adapter}' 的时间戳单位: {e}")
            return None
