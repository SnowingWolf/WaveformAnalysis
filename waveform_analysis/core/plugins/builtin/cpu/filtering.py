# -*- coding: utf-8 -*-
"""
CPU Filtering Plugin - 使用 scipy 进行波形滤波

**加速器**: CPU (scipy)
**功能**: 波形滤波（Butterworth 带通滤波、Savitzky-Golay 滤波）

本插件提供两种滤波方法：
- Butterworth 带通滤波器 (BW)
- Savitzky-Golay 滤波器 (SG)
"""

from typing import Any, List

import numpy as np
from scipy.signal import butter, savgol_filter, sosfiltfilt

from ...core.base import Option, Plugin


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
