"""
从 peaklet 特征进行 S1/S2 分类。

该插件基于 peaks 的多维特征进行信号类型甄别。

默认分类规则（基于 n_hits 和 rise_time_10_50）：
┌─────────────┬──────────────────┬──────────┬────────────────────────────────┐
│ n_hits      │ rise_time_10_50  │ 分类结果 │ 说明                           │
├─────────────┼──────────────────┼──────────┼────────────────────────────────┤
│ < 8         │ 任意             │ S1       │ 少量 hits（单通道或少量通道）  │
│ >= 8        │ <= 100 ns        │ S1       │ 多 hits 但快速上升（类 S1）    │
│ >= 8        │ > 100 ns         │ S2       │ 多 hits 且慢速上升（典型 S2）  │
└─────────────┴──────────────────┴──────────┴────────────────────────────────┘

物理意义：
- n_hits < 8: 信号集中在少量通道，典型的 S1 直接闪烁特征
- n_hits >= 8 且 rise_time_10_50 <= 100 ns: 多通道但快速上升，可能是强 S1
- n_hits >= 8 且 rise_time_10_50 > 100 ns: 多通道且慢速上升，典型 S2 电子漂移信号

分类标签：
- 0: Unknown（未知类型）
- 1: S1（闪烁信号）
- 2: S2（电离信号）
- 3: S1_S2（混合信号或分类冲突）
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
LABEL_S1_S2 = export(3, name="LABEL_S1_S2")  # 混合信号或分类冲突

PEAK_CLASSIFICATION_DTYPE = np.dtype(
    [
        ("peak_id", "i8"),
        ("label", "i1"),
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
class PeakClassificationPlugin(Plugin):
    """基于 peaks 特征进行 S1/S2 分类。

    该插件使用 peaks 的多维特征（宽度、面积、高度、上升时间、下降时间、n_hits、n_channels 等）
    进行信号类型甄别。通过字典配置各类型的特征范围。

    可用的特征字段：
    - width: 宽度 (ns)
    - area: 面积
    - height: 高度
    - rise_time: 上升时间 (ns)，从 10% 到峰值
    - fall_time: 下降时间 (ns)，从峰值到 90%
    - rise_time_10_50: 上升时间 (ns)，从 10% 到 50%
    - width_25_75: 宽度 (ns)，25%-75%
    - range_90p_area: 90% 面积范围 (ns)
    - n_hits: hits 数量
    - n_channels: 通道数量
    """

    provides = "peak_classification"
    depends_on = ["peaks"]
    description = "Classify peaks into S1/S2 using multi-dimensional features."
    version = "1.1.0"
    save_when = "always"
    output_dtype = PEAK_CLASSIFICATION_DTYPE

    options = {
        "conflict_policy": Option(
            default="prefer_s1",
            type=str,
            choices=["unknown", "prefer_s1", "prefer_s2", "mark_as_s1_s2"],
            help=(
                "当同时满足 S1 和 S2 条件时的处理策略。"
                "- 'prefer_s1': 优先标记为 S1（默认）"
                "- 'prefer_s2': 优先标记为 S2"
                "- 'unknown': 标记为 Unknown"
                "- 'mark_as_s1_s2': 标记为 S1_S2（混合信号）"
            ),
        ),
        "default_label": Option(
            default="unknown",
            type=str,
            choices=["unknown", "s1", "s2"],
            help=("当不满足任何配置条件时的默认标签。" "默认 'unknown'（推荐用于灵活分类）。"),
        ),
        "strict": Option(
            default=False,
            type=bool,
            help="如果为 True，至少需要配置一个 S1 或 S2 的判断条件。",
        ),
        "s1_selection": Option(
            default=None,
            type=dict,
            help=(
                "S1 分类配置。字典包含："
                "- 'accept_any': 列表，每个元素是一个条件组（字典），满足任一组即为 S1 候选"
                "- 'reject_any': 列表，每个元素是一个条件组（字典），满足任一组即排除"
                "示例: {'accept_any': [{'width': (0, 100)}, {'area': (0, 500)}], "
                "'reject_any': [{'width': (500, None)}]}"
            ),
        ),
        "s2_selection": Option(
            default=None,
            type=dict,
            help="S2 分类配置，格式同 s1_selection。",
        ),
    }

    def compute(self, context: Any, run_id: str, **_kwargs) -> np.ndarray:
        # 获取依赖数据
        peaks = context.get_data(run_id, "peaks")

        if not isinstance(peaks, np.ndarray):
            raise ValueError("peak_classification expects peaks as a structured array")

        if len(peaks) == 0:
            return np.zeros(0, dtype=PEAK_CLASSIFICATION_DTYPE)

        # 获取配置
        s1_selection = context.get_config(self, "s1_selection")
        s2_selection = context.get_config(self, "s2_selection")
        conflict_policy = context.get_config(self, "conflict_policy")
        default_label_str = context.get_config(self, "default_label")
        strict = context.get_config(self, "strict")

        # 检查是否至少配置了一个判断条件
        s1_enabled = s1_selection is not None
        s2_enabled = s2_selection is not None

        if strict and not s1_enabled and not s2_enabled:
            raise RuntimeError("No S1/S2 criteria configured; set selection or disable strict.")

        # 解析 default_label
        default_label_map = {"unknown": LABEL_UNKNOWN, "s1": LABEL_S1, "s2": LABEL_S2}
        default_label = default_label_map.get(default_label_str, LABEL_UNKNOWN)

        # 逐个 peak 进行分类
        rows = []
        for peak in peaks:
            peak_id = int(peak["peak_id"])

            # 提取特征值
            features = self._extract_features(peak)

            # S1 判定
            if s1_enabled:
                s1_accepted, s1_rejected = self._check_selection(features, s1_selection)
                s1_ok = s1_accepted and not s1_rejected
            else:
                s1_ok = False

            # S2 判定
            if s2_enabled:
                s2_accepted, s2_rejected = self._check_selection(features, s2_selection)
                s2_ok = s2_accepted and not s2_rejected
            else:
                s2_ok = False

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
                elif conflict_policy == "mark_as_s1_s2":
                    label = LABEL_S1_S2
                else:
                    label = LABEL_UNKNOWN
            else:
                # 不满足任何条件时使用默认标签
                label = default_label

            # 构建输出行
            rows.append(
                (
                    peak_id,
                    int(label),
                )
            )

        if rows:
            return np.array(rows, dtype=PEAK_CLASSIFICATION_DTYPE)
        return np.zeros(0, dtype=PEAK_CLASSIFICATION_DTYPE)

    @staticmethod
    def _normalize_ranges(ranges: dict | None) -> dict[str, tuple[float | None, float | None]]:
        """标准化范围配置字典"""
        if ranges is None:
            return {}

        if not isinstance(ranges, dict):
            raise ValueError(f"ranges must be a dict, got {type(ranges)}")

        normalized = {}
        for key, value in ranges.items():
            norm_value = _normalize_range(value)
            if norm_value is not None:
                normalized[key] = norm_value

        return normalized

    @staticmethod
    def _extract_features(peak: np.record) -> dict[str, float]:
        """从 peak 中提取特征值"""
        return {
            "width": float(peak["width"]),
            "area": float(peak["area"]),
            "height": float(peak["height"]),
            "rise_time": float(peak["rise_time"]),
            "fall_time": float(peak["fall_time"]),
            "rise_time_10_50": float(peak["rise_time_10_50"]),
            "width_25_75": float(peak["width_25_75"]),
            "range_90p_area": float(peak["range_90p_area"]),
            "n_hits": int(peak["n_hits"]),
            "n_channels": int(peak["n_channels"]),
        }

    @staticmethod
    def _check_criteria(
        features: dict[str, float], criteria: dict[str, tuple[float | None, float | None]]
    ) -> bool:
        """检查特征是否满足所有条件（AND 逻辑）"""
        for feature_name, bounds in criteria.items():
            value = features.get(feature_name)
            if value is None:
                return False
            if not _value_in_range(value, bounds):
                return False
        return True

    def _check_selection(
        self, features: dict[str, float], selection_config: dict | None
    ) -> tuple[bool, bool]:
        """检查 accept_any / reject_any 逻辑

        Args:
            features: 特征字典
            selection_config: 包含 'accept_any' 和 'reject_any' 的配置字典

        Returns:
            (is_accepted, is_rejected)
            - is_accepted: 是否满足任一 accept 条件组
            - is_rejected: 是否满足任一 reject 条件组
        """
        if not selection_config:
            return False, False

        accept_any = selection_config.get("accept_any", [])
        reject_any = selection_config.get("reject_any", [])

        # 检查排除条件（优先）
        is_rejected = False
        if reject_any:
            for criteria_group in reject_any:
                normalized = self._normalize_ranges(criteria_group)
                if self._check_criteria(features, normalized):
                    is_rejected = True
                    break

        # 检查接受条件
        is_accepted = False
        if accept_any:
            for criteria_group in accept_any:
                normalized = self._normalize_ranges(criteria_group)
                if self._check_criteria(features, normalized):
                    is_accepted = True
                    break

        return is_accepted, is_rejected
