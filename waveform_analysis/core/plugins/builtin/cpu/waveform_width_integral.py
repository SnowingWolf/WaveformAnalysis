"""
CPU Waveform Width Integral Plugin - 事件级积分分位数宽度

**加速器**: CPU (NumPy)
**功能**: 对每条事件波形计算积分分位数宽度 (t_low/t_high)。

核心口径：
1) 输出是“按事件”的，不按峰；一条记录 = 一个 event_index
2) baseline 仅来自 st_waveforms.baseline（插件不再估计 baseline）
3) 若 use_filtered=True，波形使用 filtered_waveforms，但 baseline 仍来自 st_waveforms
4) t_low/t_high 是波形内部的相对位置；timestamp 保持 ADC 事件时间语义
"""

from typing import Any

import numpy as np

from waveform_analysis.core.hardware.channel import (
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
from waveform_analysis.core.plugins.core.base import Option, Plugin

WAVEFORM_WIDTH_INTEGRAL_DTYPE = np.dtype(
    [
        ("t_low", "f4"),  # 低分位积分点（ns，对应 q_low）
        ("t_high", "f4"),  # 高分位积分点（ns，对应 q_high）
        ("width", "f4"),  # t_high - t_low（ns）
        ("t_low_samples", "f4"),  # 低分位积分点（采样点索引）
        ("t_high_samples", "f4"),  # 高分位积分点（采样点索引）
        ("width_samples", "f4"),  # 宽度（采样点数）
        ("q_total", "f8"),  # 总电荷/总面积（基线校正后）
        ("timestamp", "i8"),  # 事件时间戳（ADC）
        ("board", "i2"),  # 板卡编号
        ("channel", "i2"),  # 通道号
        ("event_index", "i8"),  # 事件索引
    ]
)


class WaveformWidthIntegralPlugin(Plugin):
    """
    事件级积分分位数宽度 (Event-wise Integral Quantile Width)。

    对每条波形进行基线校正后积分，计算累计积分的 t_low/t_high 并得到宽度。
    baseline 始终来自 st_waveforms.baseline，与系统其它特征一致。
    """

    provides = "waveform_width_integral"
    depends_on = []  # 动态依赖，由 resolve_depends_on 决定
    description = "Event-wise integral quantile width using st_waveforms or filtered_waveforms."
    version = "2.5.0"  # 版本升级：records 分支支持统一极性信号接口
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
        "wave_source": Option(
            default=WAVE_SOURCE_AUTO,
            type=str,
            help="波形数据源: auto|records|st_waveforms|filtered_waveforms",
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
        "channel_metadata": Option(
            default=None,
            type=dict,
            help="已废弃；行为配置请改用 channel_config。",
        ),
        "channel_config": Option(
            default=None,
            type=dict,
            help="按 (board, channel) 的插件通道覆盖配置，可覆盖 polarity。",
        ),
    }

    def compute(self, context: Any, run_id: str, **_kwargs) -> np.ndarray:
        q_low = float(context.get_config(self, "q_low"))
        q_high = float(context.get_config(self, "q_high"))
        polarity = context.get_config(self, "polarity")
        use_filtered = bool(context.get_config(self, "use_filtered"))
        source = resolve_wave_source(context, self)
        dt = context.get_config(self, "dt")
        sampling_rate = context.get_config(self, "sampling_rate")
        daq_adapter = context.get_config(self, "daq_adapter")
        channel_config_cfg = context.get_config(self, "channel_config")

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

        if source == WAVE_SOURCE_RECORDS:
            from waveform_analysis.core import records_view

            rv = records_view(context, run_id)
            records = rv.records
            if len(records) == 0:
                return np.zeros(0, dtype=WAVEFORM_WIDTH_INTEGRAL_DTYPE)
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

        else:
            # 根据 wave_source/use_filtered 选择数据源
            if source == WAVE_SOURCE_FILTERED or (source == WAVE_SOURCE_AUTO and use_filtered):
                waveform_data = context.get_data(run_id, "filtered_waveforms")
            else:
                waveform_data = context.get_data(run_id, "st_waveforms")

            if not isinstance(waveform_data, np.ndarray):
                raise ValueError("waveform_width_integral expects st_waveforms as a single array")

            if len(waveform_data) == 0:
                return np.zeros(0, dtype=WAVEFORM_WIDTH_INTEGRAL_DTYPE)

            records_len = len(waveform_data)

            def get_wave(i: int) -> np.ndarray:
                return waveform_data[i]["wave"]

            def get_baseline(i: int) -> float:
                return float(waveform_data[i]["baseline"])

            def get_timestamp(i: int) -> int:
                return int(waveform_data[i]["timestamp"])

            def get_channel(i: int) -> int:
                if "channel" in waveform_data.dtype.names:
                    return int(waveform_data[i]["channel"])
                return 0

            def get_board(i: int) -> int:
                if "board" in waveform_data.dtype.names:
                    return int(waveform_data[i]["board"])
                return 0

        widths: list[tuple] = []

        for event_idx in range(records_len):
            wave = get_wave(event_idx)
            baseline = get_baseline(event_idx)
            channel = get_channel(event_idx)
            board = get_board(event_idx)
            effective_rule = resolve_effective_channel_config(
                context=context,
                plugin=self,
                run_id=run_id,
                board=board,
                channel=channel,
                base_values={"polarity": polarity},
                channel_config=channel_config_cfg,
            ).values

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

            if source == WAVE_SOURCE_RECORDS and data_polarity in ("positive", "negative"):
                x = np.maximum(-get_signal(event_idx).astype(np.float64, copy=False), 0.0)
            else:
                signal = wave - baseline
                if effective_polarity == "positive":
                    x = np.maximum(signal, 0.0)
                elif effective_polarity == "negative":
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
                t_low_samples = 0.0
                t_high_samples = 0.0
                width_samples = 0.0
            else:
                cumsum = np.cumsum(x)
                t_low_idx = int(np.searchsorted(cumsum, q_low * q_total, side="left"))
                t_high_idx = int(np.searchsorted(cumsum, q_high * q_total, side="left"))
                t_low_samples = float(t_low_idx)
                t_high_samples = float(t_high_idx)
                width_samples = float(max(t_high_idx - t_low_idx, 0))

            t_low = float(t_low_samples * dt)
            t_high = float(t_high_samples * dt)
            width = float(width_samples * dt)
            timestamp = get_timestamp(event_idx)

            widths.append(
                (
                    t_low,
                    t_high,
                    width,
                    t_low_samples,
                    t_high_samples,
                    width_samples,
                    q_total,
                    timestamp,
                    board,
                    channel,
                    int(event_idx),
                )
            )

        if widths:
            return np.array(widths, dtype=WAVEFORM_WIDTH_INTEGRAL_DTYPE)
        return np.zeros(0, dtype=WAVEFORM_WIDTH_INTEGRAL_DTYPE)

    def resolve_depends_on(self, context: Any, run_id: str | None = None) -> list[str]:
        source = resolve_wave_source(context, self)
        return resolve_wave_depends_on(source, bool(context.get_config(self, "use_filtered")))

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
        daq_adapter: str | None,
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
