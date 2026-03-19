"""
Basic Features Plugin - 基础特征计算插件

**加速器**: CPU (NumPy)
**功能**: 计算波形的基础特征（height/area）

本模块包含基础特征计算插件，从结构化波形中提取：
- height: 脉冲高度（baseline - min(wave)），信号偏离基线的幅度
- amp: 峰峰值振幅（max - min）
- area: 波形面积（积分）

支持可选的滤波波形输入，可配置计算范围。
"""

from typing import Any

import numpy as np

from waveform_analysis.core.foundation.constants import FeatureDefaults
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

BASIC_FEATURES_DTYPE = np.dtype(
    [
        ("height", "f4"),  # baseline - min(wave)，信号偏离基线的幅度
        ("amp", "f4"),  # max - min，峰峰值振幅
        ("area", "f4"),
        ("timestamp", "i8"),  # ADC 时间戳 (ps)
        ("channel", "i2"),  # 物理通道号
        ("event_index", "i8"),  # 事件索引
    ]
)


class BasicFeaturesPlugin(Plugin):
    """Plugin to compute basic height/area features from structured waveforms."""

    provides = "basic_features"
    depends_on = []  # 动态依赖，由 resolve_depends_on 决定
    version = "3.3.0"  # 版本升级：新增 fixed_baseline 选项
    save_when = "always"
    output_dtype = BASIC_FEATURES_DTYPE
    options = {
        "height_range": Option(
            default=FeatureDefaults.PEAK_RANGE, type=tuple, help="高度计算范围 (start, end)"
        ),
        "area_range": Option(
            default=(0, None),
            type=tuple,
            help="面积计算范围 (start, end)，end=None 表示积分到波形末端",
        ),
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
        "fixed_baseline": Option(
            default=None,
            type=dict,
            help="按通道固定 baseline 值，如 {0: 8192, 1: 8200}。设置后覆盖动态 baseline 用于 height/area 计算。",
        ),
    }

    def resolve_depends_on(self, context: Any, run_id: str | None = None) -> list[str]:
        source = resolve_wave_source(context, self)
        return resolve_wave_depends_on(source, bool(context.get_config(self, "use_filtered")))

    def compute(self, context: Any, run_id: str, **kwargs) -> np.ndarray:
        """
        计算基础特征（height/amp/area）

        height = baseline - min(wave)  (信号偏离基线的幅度)
        amp = max - min  (峰峰值振幅)
        area = sum(baseline - wave)

        Returns:
            np.ndarray: 结构化数组，包含 height/area 字段
        """
        use_filtered = bool(context.get_config(self, "use_filtered"))
        source = resolve_wave_source(context, self)

        height_range = context.get_config(self, "height_range")
        area_range = context.get_config(self, "area_range")

        start_p, end_p = height_range
        start_c, end_c = area_range
        fixed_baseline = context.get_config(self, "fixed_baseline")
        fixed_by_channel = {}
        if fixed_baseline:
            fixed_by_channel = {int(ch): float(val) for ch, val in fixed_baseline.items()}

        if source == WAVE_SOURCE_RECORDS:
            from waveform_analysis.core import records_view

            rv = records_view(context, run_id)
            records = rv.records
            if len(records) == 0:
                return np.zeros(0, dtype=BASIC_FEATURES_DTYPE)

            features = np.zeros(len(records), dtype=BASIC_FEATURES_DTYPE)
            for idx, rec in enumerate(records):
                ch = int(rec["channel"]) if "channel" in records.dtype.names else 0
                baseline = fixed_by_channel.get(ch, float(rec["baseline"]))
                wave = rv.wave(idx)
                wave_p = wave[start_p:end_p]
                wave_c = wave[start_c:end_c]

                if wave_p.size > 0:
                    w_min = float(np.min(wave_p))
                    w_max = float(np.max(wave_p))
                    features["height"][idx] = baseline - w_min
                    features["amp"][idx] = w_max - w_min

                if wave_c.size > 0:
                    features["area"][idx] = float(
                        np.sum(np.asarray(baseline, dtype=np.float64) - wave_c.astype(np.float64))
                    )

                features["timestamp"][idx] = int(rec["timestamp"])
                features["channel"][idx] = ch
                features["event_index"][idx] = idx
            return features

        # 根据 wave_source/use_filtered 选择结构化波形数据源
        if source == WAVE_SOURCE_FILTERED or (source == WAVE_SOURCE_AUTO and use_filtered):
            waveform_data = context.get_data(run_id, "filtered_waveforms")
        else:
            waveform_data = context.get_data(run_id, "st_waveforms")

        if not isinstance(waveform_data, np.ndarray):
            raise ValueError("basic_features expects st_waveforms as a single structured array")
        if len(waveform_data) == 0:
            return np.zeros(0, dtype=BASIC_FEATURES_DTYPE)

        waves = waveform_data["wave"]
        baselines = waveform_data["baseline"].copy()
        timestamps = waveform_data["timestamp"]
        channels = (
            waveform_data["channel"]
            if "channel" in waveform_data.dtype.names
            else np.zeros(len(waveform_data), dtype="i2")
        )

        # 固定 baseline 覆盖
        if fixed_by_channel:
            for ch, val in fixed_by_channel.items():
                mask = channels == int(ch)
                baselines[mask] = val
        n_events = len(waveform_data)

        # 计算 height (baseline - min) 和 amp (max - min)
        waves_p = waves[:, start_p:end_p]
        height_vals = baselines - np.min(waves_p, axis=1)
        amp_vals = np.max(waves_p, axis=1) - np.min(waves_p, axis=1)

        # 计算 area
        waves_c = waves[:, start_c:end_c]
        area_vals = np.sum(baselines[:, np.newaxis] - waves_c, axis=1)

        # 构建输出（包含元数据）
        features = np.zeros(n_events, dtype=BASIC_FEATURES_DTYPE)
        features["height"] = height_vals
        features["amp"] = amp_vals
        features["area"] = area_vals
        features["timestamp"] = timestamps
        features["channel"] = channels
        features["event_index"] = np.arange(n_events)

        return features
