# -*- coding: utf-8 -*-
"""
CPU Waveform Width Integral Plugin - 事件级积分分位数宽度

**加速器**: CPU (NumPy)
**功能**: 对每条事件波形计算积分分位数宽度 (t10/t90)。

核心口径：
1) 输出是“按事件”的，不按峰；一条记录 = 一个 event_index
2) baseline 仅来自 st_waveforms.baseline（插件不再估计 baseline）
3) 若 use_filtered=True，波形使用 filtered_waveforms，但 baseline 仍来自 st_waveforms
4) t10/t90 是波形内部的相对位置；timestamp 保持 ADC 事件时间语义
"""

from typing import Any, List, Optional

import numpy as np

from waveform_analysis.core.plugins.core.base import Option, Plugin

WAVEFORM_WIDTH_INTEGRAL_DTYPE = np.dtype([
    ("t10", "f4"),  # 10% 积分点（ns）
    ("t90", "f4"),  # 90% 积分点（ns）
    ("width", "f4"),  # t90 - t10（ns）
    ("t10_samples", "f4"),  # 10% 积分点（采样点索引）
    ("t90_samples", "f4"),  # 90% 积分点（采样点索引）
    ("width_samples", "f4"),  # 宽度（采样点数）
    ("q_total", "f8"),  # 总电荷/总面积（基线校正后）
    ("timestamp", "i8"),  # 事件时间戳（ADC）
    ("channel", "i2"),  # 通道号
    ("event_index", "i8"),  # 事件索引
])


class WaveformWidthIntegralPlugin(Plugin):
    """
    事件级积分分位数宽度 (Event-wise Integral Quantile Width)。

    对每条波形进行基线校正后积分，计算累计积分的 t10/t90 并得到宽度。
    baseline 始终来自 st_waveforms.baseline，与系统其它特征一致。
    """

    provides = "waveform_width_integral"
    depends_on = ["st_waveforms", "filtered_waveforms"]
    description = "Event-wise integral quantile width using st_waveforms baseline."
    version = "1.0.0"
    save_when = "always"

    output_dtype = WAVEFORM_WIDTH_INTEGRAL_DTYPE

    options = {
        "q_low": Option(default=0.10, type=float, help="低分位点（默认 0.10）"),
        "q_high": Option(default=0.90, type=float, help="高分位点（默认 0.90）"),
        "polarity": Option(
            default="auto",
            type=str,
            help="信号极性: auto | positive | negative",
        ),
        "use_filtered": Option(
            default=False,
            type=bool,
            help="是否使用 filtered_waveforms（若启用，baseline 仍来自 st_waveforms）",
        ),
        "sampling_rate": Option(
            default=0.5,
            type=float,
            help="采样率（GHz），用于换算时间（ns）",
        ),
        "dt": Option(
            default=None,
            type=float,
            help="采样间隔（ns），优先级高于 sampling_rate",
        ),
        "daq_adapter": Option(
            default=None,
            type=str,
            help="DAQ 适配器名称（用于自动推断采样率）",
        ),
    }

    def compute(self, context: Any, run_id: str, **_kwargs) -> List[np.ndarray]:
        q_low = float(context.get_config(self, "q_low"))
        q_high = float(context.get_config(self, "q_high"))
        polarity = context.get_config(self, "polarity")
        use_filtered = context.get_config(self, "use_filtered")
        dt = context.get_config(self, "dt")
        sampling_rate = context.get_config(self, "sampling_rate")
        daq_adapter = context.get_config(self, "daq_adapter")

        if dt is None:
            if not self._has_config(context, "sampling_rate"):
                sampling_rate = self._get_sampling_rate_from_adapter(
                    daq_adapter,
                    sampling_rate,
                )
            if sampling_rate <= 0:
                raise ValueError(f"sampling_rate ({sampling_rate}) 必须大于 0")
            dt = 1.0 / float(sampling_rate)

        if q_low <= 0 or q_high >= 1 or q_low >= q_high:
            raise ValueError(f"q_low/q_high 无效: q_low={q_low}, q_high={q_high}")

        if polarity not in ("auto", "positive", "negative"):
            raise ValueError(f"不支持的 polarity: {polarity}")

        st_waveforms = context.get_data(run_id, "st_waveforms")

        if use_filtered:
            try:
                filtered_waveforms = context.get_data(run_id, "filtered_waveforms")
            except Exception:
                raise ValueError("use_filtered=True 但无法获取 filtered_waveforms。请先注册 FilteredWaveformsPlugin。")
        else:
            filtered_waveforms = None

        width_list: List[np.ndarray] = []

        for ch_idx, st_ch in enumerate(st_waveforms):
            if len(st_ch) == 0:
                width_list.append(np.zeros(0, dtype=WAVEFORM_WIDTH_INTEGRAL_DTYPE))
                continue

            filtered_ch = filtered_waveforms[ch_idx] if use_filtered else None
            channel_widths = []

            for event_idx in range(len(st_ch)):
                record = st_ch[event_idx]
                wave = record["wave"]
                baseline = float(record["baseline"])

                if use_filtered and filtered_ch is not None and event_idx < len(filtered_ch):
                    wave = filtered_ch[event_idx]

                signal = wave - baseline

                if polarity == "positive":
                    x = np.maximum(signal, 0.0)
                elif polarity == "negative":
                    x = np.maximum(-signal, 0.0)
                else:
                    pos_area = float(np.sum(np.maximum(signal, 0.0)))
                    neg_area = float(np.sum(np.maximum(-signal, 0.0)))
                    if neg_area > pos_area:
                        x = np.maximum(-signal, 0.0)
                    else:
                        x = np.maximum(signal, 0.0)

                q_total = float(np.sum(x))

                if q_total <= 0 or not np.isfinite(q_total):
                    t10_samples = 0.0
                    t90_samples = 0.0
                    width_samples = 0.0
                else:
                    cumsum = np.cumsum(x)
                    t10_idx = int(np.searchsorted(cumsum, q_low * q_total, side="left"))
                    t90_idx = int(np.searchsorted(cumsum, q_high * q_total, side="left"))
                    t10_samples = float(t10_idx)
                    t90_samples = float(t90_idx)
                    width_samples = float(max(t90_idx - t10_idx, 0))

                t10 = float(t10_samples * dt)
                t90 = float(t90_samples * dt)
                width = float(width_samples * dt)
                timestamp = int(record["timestamp"])
                channel = int(record["channel"]) if "channel" in record.dtype.names else int(ch_idx)

                channel_widths.append((
                    t10,
                    t90,
                    width,
                    t10_samples,
                    t90_samples,
                    width_samples,
                    q_total,
                    timestamp,
                    channel,
                    int(event_idx),
                ))

            if channel_widths:
                widths_array = np.array(channel_widths, dtype=WAVEFORM_WIDTH_INTEGRAL_DTYPE)
            else:
                widths_array = np.zeros(0, dtype=WAVEFORM_WIDTH_INTEGRAL_DTYPE)

            width_list.append(widths_array)

        return width_list

    def _has_config(self, context: Any, name: str) -> bool:
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
