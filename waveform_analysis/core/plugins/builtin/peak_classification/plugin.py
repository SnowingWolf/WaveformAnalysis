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

# Keep field narratives beside the dtype they describe. Generated Help, Markdown,
# and static HTML consume these through the plugin's source ``agent_doc``.
PEAK_CLASSIFICATION_FIELD_NOTES = {
    "peak_id": "Zero-based index of the input `peaks` row receiving this classification.",
    "label": "Classification code: 0=unknown, 1=S1, 2=S2, 3=S1_S2.",
}


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
    - fall_time: 下降时间 (ns)，50%-90% 面积分位数
    - rise_time_10_50: 上升时间 (ns)，从 10% 到 50%
    - width_25_75: 宽度 (ns)，25%-75%
    - range_90p_area: 90% 面积范围 (ns)
    - n_hits: hits 数量
    - n_channels: 通道数量
    """

    provides = "peak_classification"
    depends_on = ["peaks"]
    description = "Classify peaks into S1/S2 using multi-dimensional features."
    version = "1.2.1"
    save_when = "always"
    output_dtype = PEAK_CLASSIFICATION_DTYPE
    agent_doc = {
        "field_notes": PEAK_CLASSIFICATION_FIELD_NOTES,
        "config_notes": {
            "priority_order": (
                "分类优先级顺序（列表，从高到低）。按顺序检查每个标签，"
                "返回第一个满足条件的类型。可用值: 's1', 's2', 's1_s2'。"
                "示例: ['s1_s2', 's1', 's2'] 先判定 s1_s2，再 s1，最后 s2；"
                "['s1', 's2', 's1_s2'] 则 S1 优先。"
            ),
            "default_label": (
                "当不满足任何配置条件时的默认标签。可选值: 'unknown', 's1', 's2'。"
                "默认 'unknown'（推荐，避免误判）。"
            ),
            "strict": (
                "为 True 时，至少需要配置一个 s1_selection / s2_selection / "
                "s1_s2_selection，否则抛出 RuntimeError。"
            ),
            "s1_selection": (
                "S1 分类配置字典。accept_any: 条件组列表，满足任一组即候选（组间 OR）；"
                "reject_any: 条件组列表，满足任一组即排除；条件组内字段条件为 AND。"
                "可用字段: width, area, height, rise_time, fall_time, rise_time_10_50, "
                "width_25_75, range_90p_area, n_hits, n_channels。"
                "示例: {'accept_any': [{'width': (0, 100)}, {'area': (0, 500)}], "
                "'reject_any': [{'width': (500, None)}]}"
            ),
            "s2_selection": "S2 分类配置，格式同 s1_selection。",
            "s1_s2_selection": ("S1_S2 分类配置，格式同 s1_selection。命中后优先标记为 S1_S2。"),
        },
        "behavior_notes": [
            "基于 peaks 表特征（width、area、height、rise_time、n_hits、n_channels 等）"
            "把每条 peak 标记为 Unknown(0)、S1(1)、S2(2) 或 S1_S2(3)。",
            "判定按 priority_order 顺序执行：为每个标签计算 selection 掩码，"
            "返回第一个满足条件的标签；都不满足时返回 default_label。",
            "accept_any 组间为 OR，组内字段条件为 AND；reject_any 命中即排除。",
            "s1_s2_selection 命中时优先标记为 S1_S2，再考虑普通 S1/S2 规则。",
        ],
    }

    doc_usage_example = """
    from waveform_analysis.core.context import Context
    from waveform_analysis.core.plugins.builtin.cpu import PeakClassificationPlugin

    run_id = "run_001"
    ctx = Context(config={"data_root": "DAQ"})
    ctx.register(PeakClassificationPlugin())

    # 条件组内部使用 AND；accept_any/reject_any 的多个条件组使用 OR。
    ctx.set_config(
        {
            "s1_selection": {
                "accept_any": [
                    {"width": (0.0, 100.0), "n_hits": (1, 7)},
                ],
            },
            "s2_selection": {
                "accept_any": [
                    {"width": (300.0, None), "n_hits": (8, None)},
                    {"rise_time_10_50": (100.0, None)},
                ],
            },
            "s1_s2_selection": {
                "accept_any": [
                    {"width": (100.0, 200.0), "area": (400.0, 600.0)},
                ],
            },
            "priority_order": ["s1_s2", "s1", "s2"],
            "default_label": "unknown",
        },
        plugin_name="peak_classification",
    )
    labels = ctx.get_data(run_id, "peak_classification")
    """

    options = {
        "priority_order": Option(
            default=["s1_s2", "s1", "s2"],
            type=list,
            help=(
                "分类优先级顺序（列表），从高到低。"
                "例如: ['s1_s2', 's1', 's2'] 表示先判定 s1_s2，再判定 s1，最后判定 s2。"
                "可用值: 's1', 's2', 's1_s2'"
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
        "s1_s2_selection": Option(
            default=None,
            type=dict,
            help="S1_S2 分类配置，格式同 s1_selection。命中后优先标记为 S1_S2。",
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
        s1_s2_selection = context.get_config(self, "s1_s2_selection")
        priority_order = context.get_config(self, "priority_order")
        default_label_str = context.get_config(self, "default_label")
        strict = context.get_config(self, "strict")

        # 检查是否至少配置了一个判断条件
        s1_enabled = s1_selection is not None
        s2_enabled = s2_selection is not None
        s1_s2_enabled = s1_s2_selection is not None

        if strict and not s1_enabled and not s2_enabled and not s1_s2_enabled:
            raise RuntimeError("No S1/S2 criteria configured; set selection or disable strict.")

        # 解析 default_label
        default_label_map = {"unknown": LABEL_UNKNOWN, "s1": LABEL_S1, "s2": LABEL_S2}
        default_label = default_label_map.get(default_label_str, LABEL_UNKNOWN)

        # 验证 priority_order
        if priority_order is not None:
            valid_labels = {"s1", "s2", "s1_s2"}
            for label in priority_order:
                if label not in valid_labels:
                    raise ValueError(
                        f"Invalid label '{label}' in priority_order. "
                        f"Valid values: {valid_labels}"
                    )

        compiled = {
            "s1": self._compile_selection(s1_selection),
            "s2": self._compile_selection(s2_selection),
            "s1_s2": self._compile_selection(s1_s2_selection),
        }
        ok_masks = {
            name: self._selection_mask(peaks, selection) for name, selection in compiled.items()
        }

        out = np.zeros(len(peaks), dtype=PEAK_CLASSIFICATION_DTYPE)
        out["peak_id"] = peaks["peak_id"]
        out["label"] = int(default_label)

        unset = np.ones(len(peaks), dtype=bool)
        label_map = {"s1": LABEL_S1, "s2": LABEL_S2, "s1_s2": LABEL_S1_S2}
        for label_name in priority_order:
            mask = unset & ok_masks[label_name]
            if np.any(mask):
                out["label"][mask] = int(label_map[label_name])
                unset[mask] = False
        return out

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

    @classmethod
    def _compile_selection(cls, selection_config: dict | None) -> tuple[
        list[dict[str, tuple[float | None, float | None]]],
        list[dict[str, tuple[float | None, float | None]]],
    ]:
        if not selection_config:
            return [], []
        accept_any = [
            cls._normalize_ranges(criteria_group)
            for criteria_group in selection_config.get("accept_any", [])
        ]
        reject_any = [
            cls._normalize_ranges(criteria_group)
            for criteria_group in selection_config.get("reject_any", [])
        ]
        return accept_any, reject_any

    @staticmethod
    def _criteria_mask(
        peaks: np.ndarray, criteria: dict[str, tuple[float | None, float | None]]
    ) -> np.ndarray:
        if not criteria:
            return np.ones(len(peaks), dtype=bool)
        names = peaks.dtype.names or ()
        mask = np.ones(len(peaks), dtype=bool)
        for feature_name, bounds in criteria.items():
            if feature_name not in names:
                return np.zeros(len(peaks), dtype=bool)
            values = peaks[feature_name]
            finite_mask = ~np.isnan(values) if np.issubdtype(values.dtype, np.floating) else True
            lo, hi = bounds
            feature_mask = finite_mask
            if lo is not None:
                feature_mask = feature_mask & (values >= lo)
            if hi is not None:
                feature_mask = feature_mask & (values <= hi)
            mask &= feature_mask
        return mask

    @classmethod
    def _selection_mask(
        cls,
        peaks: np.ndarray,
        selection: tuple[
            list[dict[str, tuple[float | None, float | None]]],
            list[dict[str, tuple[float | None, float | None]]],
        ],
    ) -> np.ndarray:
        accept_any, reject_any = selection
        accepted = np.zeros(len(peaks), dtype=bool)
        for criteria in accept_any:
            accepted |= cls._criteria_mask(peaks, criteria)

        rejected = np.zeros(len(peaks), dtype=bool)
        for criteria in reject_any:
            rejected |= cls._criteria_mask(peaks, criteria)
        return accepted & ~rejected

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

    def _determine_label(
        self,
        s1_ok: bool,
        s2_ok: bool,
        s1_s2_ok: bool,
        priority_order: list,
        default_label: int,
    ) -> int:
        """根据判定结果和优先级顺序确定最终标签

        Args:
            s1_ok: 是否满足 S1 条件
            s2_ok: 是否满足 S2 条件
            s1_s2_ok: 是否满足 S1_S2 条件
            priority_order: 优先级顺序列表，如 ['s1_s2', 's1', 's2']
            default_label: 默认标签

        Returns:
            最终标签（LABEL_S1, LABEL_S2, LABEL_S1_S2, 或 LABEL_UNKNOWN）
        """
        # 构建判定结果映射
        ok_map = {"s1": s1_ok, "s2": s2_ok, "s1_s2": s1_s2_ok}
        label_map = {"s1": LABEL_S1, "s2": LABEL_S2, "s1_s2": LABEL_S1_S2}

        # 按优先级顺序检查
        for label_name in priority_order:
            if ok_map.get(label_name, False):
                return label_map[label_name]

        # 都不满足，返回默认标签
        return default_label
