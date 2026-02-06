"""
CPU Waveform Width Plugin - 计算波形宽度特征

**加速器**: CPU (NumPy)
**功能**: 基于峰值检测结果计算波形的上升/下降时间

本插件依赖 SignalPeaksPlugin 的峰值检测结果，计算每个峰值的：
1. 上升时间 (Rise Time): 从 10% 到 90% 峰值高度的时间
2. 下降时间 (Fall Time): 从 90% 到 10% 峰值高度的时间
3. 总宽度: 从上升起点到下降终点的时间

支持使用原始波形或滤波后的波形进行计算。
"""

from typing import Any, List, Optional

import numpy as np

from waveform_analysis.core.plugins.core.base import Option, Plugin

# 定义波形宽度数据类型
WAVEFORM_WIDTH_DTYPE = np.dtype(
    [
        ("rise_time", "f4"),  # 上升时间 (10%-90%)，单位：ns
        ("fall_time", "f4"),  # 下降时间 (90%-10%)，单位：ns
        ("total_width", "f4"),  # 总宽度 (10%上升-10%下降)，单位：ns
        ("rise_time_samples", "f4"),  # 上升时间（采样点数）
        ("fall_time_samples", "f4"),  # 下降时间（采样点数）
        ("total_width_samples", "f4"),  # 总宽度（采样点数）
        ("peak_position", "i8"),  # 峰值位置（采样点索引）
        ("peak_height", "f4"),  # 峰值高度
        ("timestamp", "i8"),  # 事件时间戳
        ("channel", "i2"),  # 通道号
        ("event_index", "i8"),  # 事件索引
    ]
)


class WaveformWidthPlugin(Plugin):
    """
    波形宽度计算插件 - 基于峰值检测结果计算上升/下降时间。

    依赖 SignalPeaksPlugin 提供的峰值位置和边缘信息，计算：
    - 上升时间: 从 10% 峰高到 90% 峰高的时间
    - 下降时间: 从 90% 峰高到 10% 峰高的时间
    - 总宽度: 从上升起点到下降终点的总时间

    支持使用原始波形或滤波后的波形进行精确计算。
    """

    provides = "waveform_width"
    depends_on = []  # 动态依赖，由 resolve_depends_on 决定
    description = "Calculate rise/fall time based on peak detection results."
    version = "2.1.0"  # 版本升级：输出改为单数组
    save_when = "always"
    output_dtype = WAVEFORM_WIDTH_DTYPE

    options = {
        "use_filtered": Option(
            default=False,
            type=bool,
            help="是否使用滤波后的波形（需要先注册 FilteredWaveformsPlugin）",
        ),
        "sampling_rate": Option(
            default=None,
            type=float,
            help="采样率（GHz），未显式设置时优先从 DAQ 适配器推断",
        ),
        "daq_adapter": Option(
            default=None,
            type=str,
            help="DAQ 适配器名称（用于自动推断采样率）",
        ),
        "rise_low": Option(
            default=0.1,
            type=float,
            help="上升时间的低阈值比例（默认 10%）",
        ),
        "rise_high": Option(
            default=0.9,
            type=float,
            help="上升时间的高阈值比例（默认 90%）",
        ),
        "fall_high": Option(
            default=0.9,
            type=float,
            help="下降时间的高阈值比例（默认 90%）",
        ),
        "fall_low": Option(
            default=0.1,
            type=float,
            help="下降时间的低阈值比例（默认 10%）",
        ),
        "interpolation": Option(
            default=True,
            type=bool,
            help="是否使用线性插值提高时间计算精度",
        ),
    }

    def compute(self, context: Any, run_id: str, **_kwargs) -> np.ndarray:
        """
        计算波形宽度特征

        基于 SignalPeaksPlugin 的峰值检测结果，计算每个峰值的上升/下降时间。

        Args:
            context: Context 实例
            run_id: 运行标识符
            **_kwargs: 依赖数据（未使用，通过 context.get_data 获取）

        Returns:
            np.ndarray: 宽度特征数组，dtype 为 WAVEFORM_WIDTH_DTYPE

        Examples:
            >>> from waveform_analysis.core.plugins.builtin.cpu import (
            ...     SignalPeaksPlugin, WaveformWidthPlugin
            ... )
            >>> ctx.register(SignalPeaksPlugin())
            >>> ctx.register(WaveformWidthPlugin())
            >>> ctx.set_config({'sampling_rate': 1.0}, plugin_name='waveform_width')
            >>> widths = ctx.get_data('run_001', 'waveform_width')
            >>> ch0 = widths[widths['channel'] == 0]
            >>> print(f"通道0平均上升时间: {np.mean(ch0['rise_time']):.2f} ns")
        """
        # 获取配置参数
        use_filtered = context.get_config(self, "use_filtered")
        sampling_rate = context.get_config(self, "sampling_rate")
        daq_adapter = context.get_config(self, "daq_adapter")
        if not self._has_config(context, "sampling_rate"):
            sampling_rate = self._get_sampling_rate_from_adapter(
                daq_adapter,
                sampling_rate,
            )
        if sampling_rate is None:
            sampling_rate = 0.5
        rise_low = context.get_config(self, "rise_low")
        rise_high = context.get_config(self, "rise_high")
        fall_high = context.get_config(self, "fall_high")
        fall_low = context.get_config(self, "fall_low")
        interpolation = context.get_config(self, "interpolation")

        # 获取依赖数据
        signal_peaks = context.get_data(run_id, "signal_peaks")

        # 根据 use_filtered 选择波形数据源
        if use_filtered:
            waveform_data = context.get_data(run_id, "filtered_waveforms")
        else:
            waveform_data = context.get_data(run_id, "st_waveforms")

        if not isinstance(signal_peaks, np.ndarray):
            raise ValueError("waveform_width expects signal_peaks as a single structured array")
        if not isinstance(waveform_data, np.ndarray):
            raise ValueError("waveform_width expects st_waveforms as a single structured array")

        if len(signal_peaks) == 0 or len(waveform_data) == 0:
            return np.zeros(0, dtype=WAVEFORM_WIDTH_DTYPE)

        widths = []

        for peak in signal_peaks:
            event_idx = int(peak["event_index"])
            peak_position = peak["position"]
            timestamp = peak["timestamp"]
            channel = peak["channel"]

            if event_idx < 0 or event_idx >= len(waveform_data):
                continue

            waveform = waveform_data[event_idx]["wave"]

            width_features = self._calculate_width_from_peak(
                waveform,
                peak_position,
                timestamp,
                channel,
                event_idx,
                rise_low,
                rise_high,
                fall_high,
                fall_low,
                sampling_rate,
                interpolation,
            )

            if width_features is not None:
                widths.append(width_features)

        if widths:
            return np.array(widths, dtype=WAVEFORM_WIDTH_DTYPE)
        return np.zeros(0, dtype=WAVEFORM_WIDTH_DTYPE)

    def resolve_depends_on(self, context: Any, run_id: Optional[str] = None) -> List[str]:
        # signal_peaks 始终需要，波形数据根据 use_filtered 动态选择
        if context.get_config(self, "use_filtered"):
            return ["signal_peaks", "filtered_waveforms"]
        return ["signal_peaks", "st_waveforms"]

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

    def _get_sampling_rate_from_adapter(
        self,
        daq_adapter: Optional[str],
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
        return float(sampling_rate_hz) / 1e9

    def _calculate_width_from_peak(
        self,
        waveform: np.ndarray,
        peak_position: int,
        timestamp: int,
        channel: int,
        event_index: int,
        rise_low: float,
        rise_high: float,
        fall_high: float,
        fall_low: float,
        sampling_rate: float,
        interpolation: bool,
    ) -> Optional[tuple]:
        """
        基于峰值位置计算宽度特征

        Args:
            waveform: 波形数组
            peak_position: 峰值位置（采样点索引）
            timestamp: 事件时间戳
            channel: 通道号
            event_index: 事件索引
            rise_low: 上升低阈值比例
            rise_high: 上升高阈值比例
            fall_high: 下降高阈值比例
            fall_low: 下降低阈值比例
            sampling_rate: 采样率（GHz）
            interpolation: 是否使用插值

        Returns:
            宽度特征元组，如果计算失败返回 None
        """
        # 计算基线（使用波形前50个点）
        baseline = np.mean(waveform[:50])
        waveform_corrected = waveform - baseline

        # 获取峰值高度
        if peak_position >= len(waveform_corrected):
            return None

        peak_value = waveform_corrected[peak_position]

        # 如果峰值太小，跳过
        if peak_value <= 0:
            return None

        # 计算阈值
        rise_low_threshold = peak_value * rise_low
        rise_high_threshold = peak_value * rise_high
        fall_high_threshold = peak_value * fall_high
        fall_low_threshold = peak_value * fall_low

        # 计算上升时间（峰值左侧）
        rise_low_pos = self._find_threshold_crossing(
            waveform_corrected[:peak_position],
            rise_low_threshold,
            direction="rising",
            interpolation=interpolation,
        )
        rise_high_pos = self._find_threshold_crossing(
            waveform_corrected[:peak_position],
            rise_high_threshold,
            direction="rising",
            interpolation=interpolation,
        )

        if rise_low_pos is not None and rise_high_pos is not None:
            rise_time_samples = rise_high_pos - rise_low_pos
            rise_time = rise_time_samples / sampling_rate
        else:
            rise_time_samples = 0.0
            rise_time = 0.0

        # 计算下降时间（峰值右侧）
        fall_high_pos = self._find_threshold_crossing(
            waveform_corrected[peak_position:],
            fall_high_threshold,
            direction="falling",
            interpolation=interpolation,
        )
        fall_low_pos = self._find_threshold_crossing(
            waveform_corrected[peak_position:],
            fall_low_threshold,
            direction="falling",
            interpolation=interpolation,
        )

        if fall_high_pos is not None and fall_low_pos is not None:
            # 调整为相对于整个波形的位置
            fall_high_pos += peak_position
            fall_low_pos += peak_position
            fall_time_samples = fall_low_pos - fall_high_pos
            fall_time = fall_time_samples / sampling_rate
        else:
            fall_time_samples = 0.0
            fall_time = 0.0

        # 计算总宽度
        if rise_low_pos is not None and fall_low_pos is not None:
            total_width_samples = fall_low_pos - rise_low_pos
            total_width = total_width_samples / sampling_rate
        else:
            total_width_samples = 0.0
            total_width = 0.0

        return (
            float(rise_time),  # rise_time
            float(fall_time),  # fall_time
            float(total_width),  # total_width
            float(rise_time_samples),  # rise_time_samples
            float(fall_time_samples),  # fall_time_samples
            float(total_width_samples),  # total_width_samples
            int(peak_position),  # peak_position
            float(peak_value),  # peak_height
            int(timestamp),  # timestamp
            int(channel),  # channel
            int(event_index),  # event_index
        )

    def _find_threshold_crossing(
        self,
        waveform: np.ndarray,
        threshold: float,
        direction: str,
        interpolation: bool,
    ) -> Optional[float]:
        """
        找到波形与阈值的交叉点

        Args:
            waveform: 波形数组
            threshold: 阈值
            direction: 'rising' (上升) 或 'falling' (下降)
            interpolation: 是否使用插值

        Returns:
            交叉点位置（可能是浮点数），如果未找到返回 None
        """
        if len(waveform) == 0:
            return None

        if direction == "rising":
            # 找到第一个超过阈值的点
            indices = np.where(waveform >= threshold)[0]
        else:  # falling
            # 找到第一个低于阈值的点
            indices = np.where(waveform <= threshold)[0]

        if len(indices) == 0:
            return None

        idx = indices[0]

        if not interpolation or idx == 0:
            return float(idx)

        # 使用线性插值计算精确交叉点
        y0 = waveform[idx - 1]
        y1 = waveform[idx]

        # 避免除零
        if abs(y1 - y0) < 1e-10:
            return float(idx)

        # 线性插值: x = (idx-1) + (threshold - y0) / (y1 - y0)
        fraction = (threshold - y0) / (y1 - y0)
        return float(idx - 1) + fraction
