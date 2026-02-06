"""
Basic Features Plugin - 基础特征计算插件

**加速器**: CPU (NumPy)
**功能**: 计算波形的基础特征（height/area）

本模块包含基础特征计算插件，从结构化波形中提取：
- height: 波形高度（max - min）
- area: 波形面积（积分）

支持可选的滤波波形输入，可配置计算范围。
"""

from typing import Any, List, Optional

import numpy as np

from waveform_analysis.core.foundation.constants import FeatureDefaults
from waveform_analysis.core.plugins.core.base import Option, Plugin

BASIC_FEATURES_DTYPE = np.dtype(
    [
        ("height", "f4"),
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
    version = "3.1.0"  # 版本升级：输出改为单数组
    save_when = "always"
    output_dtype = BASIC_FEATURES_DTYPE
    options = {
        "height_range": Option(default=None, type=tuple, help="高度计算范围 (start, end)"),
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
    }

    def resolve_depends_on(self, context: Any, run_id: Optional[str] = None) -> List[str]:
        # 根据 use_filtered 动态选择依赖
        if context.get_config(self, "use_filtered"):
            return ["filtered_waveforms"]
        return ["st_waveforms"]

    def compute(self, context: Any, run_id: str, **kwargs) -> np.ndarray:
        """
        计算基础特征（height/area）

        height = max - min
        area = sum(baseline - wave)

        Returns:
            np.ndarray: 结构化数组，包含 height/area 字段
        """
        use_filtered = context.get_config(self, "use_filtered")

        # 根据 use_filtered 选择数据源
        if use_filtered:
            waveform_data = context.get_data(run_id, "filtered_waveforms")
        else:
            waveform_data = context.get_data(run_id, "st_waveforms")

        height_range = context.get_config(self, "height_range")
        area_range = context.get_config(self, "area_range")

        if height_range is None:
            height_range = FeatureDefaults.PEAK_RANGE
        if area_range is None:
            area_range = FeatureDefaults.CHARGE_RANGE

        start_p, end_p = height_range
        start_c, end_c = area_range

        if not isinstance(waveform_data, np.ndarray):
            raise ValueError("basic_features expects st_waveforms as a single structured array")
        if len(waveform_data) == 0:
            return np.zeros(0, dtype=BASIC_FEATURES_DTYPE)

        waves = waveform_data["wave"]
        baselines = waveform_data["baseline"]
        timestamps = waveform_data["timestamp"]
        channels = (
            waveform_data["channel"]
            if "channel" in waveform_data.dtype.names
            else np.zeros(len(waveform_data), dtype="i2")
        )
        n_events = len(waveform_data)

        # 计算 height
        waves_p = waves[:, start_p:end_p]
        height_vals = np.max(waves_p, axis=1) - np.min(waves_p, axis=1)

        # 计算 area
        waves_c = waves[:, start_c:end_c]
        area_vals = np.sum(baselines[:, np.newaxis] - waves_c, axis=1)

        # 构建输出（包含元数据）
        features = np.zeros(n_events, dtype=BASIC_FEATURES_DTYPE)
        features["height"] = height_vals
        features["area"] = area_vals
        features["timestamp"] = timestamps
        features["channel"] = channels
        features["event_index"] = np.arange(n_events)

        return features
