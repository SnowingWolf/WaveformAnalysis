"""
从 peaklet 特征进行 S1/S2 分类。

该插件基于 peaklet_features 的多维特征进行信号类型甄别：
- S1 特征：窄脉冲，快速上升/下降，小面积
- S2 特征：宽脉冲，慢速上升，大面积
- Unknown：不满足任何分类条件

分类标签：
- 0: Unknown
- 1: S1
- 2: S2
"""

from __future__ import annotations

from typing import Any

import numpy as np

from waveform_analysis.core.foundation.utils import exporter
from waveform_analysis.core.plugins.core.base import Option, Plugin

export, __all__ = exporter()

# 重用已有的标签常量
LABEL_UNKNOWN = export(0, name="LABEL_UNKNOWN")
LABEL_S1 = export(1, name="LABEL_S1")
LABEL_S2 = export(2, name="LABEL_S2")

PEAKLET_S1_S2_CLASSIFIER_DTYPE = np.dtype(
    [
        ("peak_id", "i8"),
        ("label", "i1"),
        ("width_ns", "f4"),
        ("area", "f4"),
        ("height", "f4"),
        ("rise_time_ns", "f4"),
        ("fall_time_ns", "f4"),
        ("n_hits", "i4"),
        ("n_channels", "i4"),
        ("time_start", "i8"),
        ("time_end", "i8"),
        ("time_peak", "i8"),
    ]
)


def _normalize_range(value: tuple[float | None, float | None] | None):
    """标准化范围参数 (min, max)"""
    if value is None:
        return None
    if not isinstance(value, tuple) or len(value) != 2:
        raise ValueError("range must be a tuple of (min, max)")
    lo, hi = value
    if lo is None and hi is None:
        return None
    return (None if lo is None else float(lo), None if hi is None else float(hi))


def _value_in_range(
    value: float,
    bounds: tuple[float | None, float | None] | None,
) -> bool:
    """判断值是否在范围内"""
    if bounds is None:
        return True
    if value is None or np.isnan(value):
        return False
    lo, hi = bounds
    if lo is not None and value < lo:
        return False
    if hi is not None and value > hi:
        return False
    return True


@export
class PeakletS1S2ClassifierPlugin(Plugin):
    """基于 peaklet 特征进行 S1/S2 分类。

    该插件使用 peaklet_features 的多维特征（宽度、面积、高度、上升时间、下降时间等）
    进行信号类型甄别。支持灵活配置各类型的特征范围。
    """

    provides = "peaklet_s1_s2"
    depends_on = ["peaklet_features", "peaklets"]
    description = "Classify peaklets into S1/S2 using multi-dimensional features."
    version = "0.1.0"
    save_when = "always"
    output_dtype = PEAKLET_S1_S2_CLASSIFIER_DTYPE

    options = {
        # S1 特征范围（典型：窄脉冲，快速，小面积）
        "s1_width_range": Option(
            default=None,
            type=tuple,
            help="S1 宽度范围 (min_ns, max_ns)。None 表示不限制。",
        ),
        "s1_area_range": Option(
            default=None,
            type=tuple,
            help="S1 面积范围 (min, max)。None 表示不限制。",
        ),
        "s1_height_range": Option(
            default=None,
            type=tuple,
            help="S1 高度范围 (min, max)。None 表示不限制。",
        ),
        "s1_rise_time_range": Option(
            default=None,
            type=tuple,
            help="S1 上升时间范围 (min_ns, max_ns)。None 表示不限制。",
        ),
        "s1_fall_time_range": Option(
            default=None,
            type=tuple,
            help="S1 下降时间范围 (min_ns, max_ns)。None 表示不限制。",
        ),
        "s1_n_channels_range": Option(
            default=None,
            type=tuple,
            help="S1 通道数范围 (min, max)。None 表示不限制。",
        ),
        # S2 特征范围（典型：宽脉冲，慢速，大面积）
        "s2_width_range": Option(
            default=None,
            type=tuple,
            help="S2 宽度范围 (min_ns, max_ns)。None 表示不限制。",
        ),
        "s2_area_range": Option(
            default=None,
            type=tuple,
            help="S2 面积范围 (min, max)。None 表示不限制。",
        ),
        "s2_height_range": Option(
            default=None,
            type=tuple,
            help="S2 高度范围 (min, max)。None 表示不限制。",
        ),
        "s2_rise_time_range": Option(
            default=None,
            type=tuple,
            help="S2 上升时间范围 (min_ns, max_ns)。None 表示不限制。",
        ),
        "s2_fall_time_range": Option(
            default=None,
            type=tuple,
            help="S2 下降时间范围 (min_ns, max_ns)。None 表示不限制。",
        ),
        "s2_n_channels_range": Option(
            default=None,
            type=tuple,
            help="S2 通道数范围 (min, max)。None 表示不限制。",
        ),
        # 冲突处理策略
        "conflict_policy": Option(
            default="unknown",
            type=str,
            choices=["unknown", "prefer_s1", "prefer_s2"],
            help="当同时满足 S1 和 S2 条件时的处理策略。",
        ),
        # 严格模式
        "strict": Option(
            default=False,
            type=bool,
            help="如果为 True，至少需要配置一个 S1 或 S2 的判断条件。",
        ),
    }

    def compute(self, context: Any, run_id: str, **_kwargs) -> np.ndarray:
        # 获取依赖数据
        features = context.get_data(run_id, "peaklet_features")
        peaklets = context.get_data(run_id, "peaklets")

        if not isinstance(features, np.ndarray):
            raise ValueError("peaklet_s1_s2 expects peaklet_features as a structured array")
        if not isinstance(peaklets, np.ndarray):
            raise ValueError("peaklet_s1_s2 expects peaklets as a structured array")

        if len(features) == 0:
            return np.zeros(0, dtype=PEAKLET_S1_S2_CLASSIFIER_DTYPE)

        # 获取配置
        s1_width_range = _normalize_range(context.get_config(self, "s1_width_range"))
        s1_area_range = _normalize_range(context.get_config(self, "s1_area_range"))
        s1_height_range = _normalize_range(context.get_config(self, "s1_height_range"))
        s1_rise_time_range = _normalize_range(context.get_config(self, "s1_rise_time_range"))
        s1_fall_time_range = _normalize_range(context.get_config(self, "s1_fall_time_range"))
        s1_n_channels_range = _normalize_range(context.get_config(self, "s1_n_channels_range"))

        s2_width_range = _normalize_range(context.get_config(self, "s2_width_range"))
        s2_area_range = _normalize_range(context.get_config(self, "s2_area_range"))
        s2_height_range = _normalize_range(context.get_config(self, "s2_height_range"))
        s2_rise_time_range = _normalize_range(context.get_config(self, "s2_rise_time_range"))
        s2_fall_time_range = _normalize_range(context.get_config(self, "s2_fall_time_range"))
        s2_n_channels_range = _normalize_range(context.get_config(self, "s2_n_channels_range"))

        conflict_policy = context.get_config(self, "conflict_policy")
        strict = context.get_config(self, "strict")

        # 检查是否至少配置了一个判断条件
        s1_enabled = any(
            r is not None
            for r in (
                s1_width_range,
                s1_area_range,
                s1_height_range,
                s1_rise_time_range,
                s1_fall_time_range,
                s1_n_channels_range,
            )
        )
        s2_enabled = any(
            r is not None
            for r in (
                s2_width_range,
                s2_area_range,
                s2_height_range,
                s2_rise_time_range,
                s2_fall_time_range,
                s2_n_channels_range,
            )
        )

        if strict and not s1_enabled and not s2_enabled:
            raise ValueError("No S1/S2 criteria configured; set ranges or disable strict.")

        # 构建 peaklet_id -> peaklet 映射
        peaklet_map = dict(enumerate(peaklets))

        # 逐个 peaklet 进行分类
        rows = []
        for feature in features:
            peak_id = int(feature["peak_id"])
            peaklet = peaklet_map.get(peak_id)
            if peaklet is None:
                # 跳过没有对应 peaklet 的特征
                continue

            # 提取特征值（注意：width 在 peaklet_features 中单位是 ns）
            width_ns = float(feature["width"])
            area = float(feature["area"])
            height = float(feature["height"])
            rise_time_ns = float(feature["rise_time"])
            fall_time_ns = float(feature["fall_time"])
            n_hits = int(peaklet["n_hits"])
            n_channels = int(peaklet["n_channels"])

            # 判断是否满足 S1 条件（所有配置的条件必须同时满足）
            s1_ok = s1_enabled
            if s1_ok:
                s1_ok = (
                    _value_in_range(width_ns, s1_width_range)
                    and _value_in_range(area, s1_area_range)
                    and _value_in_range(height, s1_height_range)
                    and _value_in_range(rise_time_ns, s1_rise_time_range)
                    and _value_in_range(fall_time_ns, s1_fall_time_range)
                    and _value_in_range(n_channels, s1_n_channels_range)
                )

            # 判断是否满足 S2 条件（所有配置的条件必须同时满足）
            s2_ok = s2_enabled
            if s2_ok:
                s2_ok = (
                    _value_in_range(width_ns, s2_width_range)
                    and _value_in_range(area, s2_area_range)
                    and _value_in_range(height, s2_height_range)
                    and _value_in_range(rise_time_ns, s2_rise_time_range)
                    and _value_in_range(fall_time_ns, s2_fall_time_range)
                    and _value_in_range(n_channels, s2_n_channels_range)
                )

            # 根据判断结果和冲突策略确定最终标签
            if s1_ok and not s2_ok:
                label = LABEL_S1
            elif s2_ok and not s1_ok:
                label = LABEL_S2
            elif s1_ok and s2_ok:
                if conflict_policy == "prefer_s1":
                    label = LABEL_S1
                elif conflict_policy == "prefer_s2":
                    label = LABEL_S2
                else:
                    label = LABEL_UNKNOWN
            else:
                label = LABEL_UNKNOWN

            # 构建输出行
            rows.append(
                (
                    peak_id,
                    int(label),
                    float(width_ns),
                    float(area),
                    float(height),
                    float(rise_time_ns),
                    float(fall_time_ns),
                    int(n_hits),
                    int(n_channels),
                    int(feature["time_start"]),
                    int(feature["time_end"]),
                    int(feature["time_peak"]),
                )
            )

        if rows:
            return np.array(rows, dtype=PEAKLET_S1_S2_CLASSIFIER_DTYPE)
        return np.zeros(0, dtype=PEAKLET_S1_S2_CLASSIFIER_DTYPE)
