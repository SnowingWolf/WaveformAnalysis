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
import warnings

import numpy as np

from waveform_analysis.core.foundation.constants import FeatureDefaults
from waveform_analysis.core.plugins.core.base import Option, Plugin

BASIC_FEATURES_DTYPE = np.dtype(
    [
        ("height", "f4"),
        ("area", "f4"),
    ]
)


class BasicFeaturesPlugin(Plugin):
    """Plugin to compute basic height/area features from structured waveforms."""

    provides = "basic_features"
    depends_on = []
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
        deps = ["st_waveforms"]
        if context.get_config(self, "use_filtered"):
            deps.append("filtered_waveforms")
        return deps

    def compute(self, context: Any, run_id: str, **kwargs) -> List[np.ndarray]:
        """
        计算基础特征（height/area）

        height = max - min
        area = sum(baseline - wave)

        Returns:
            List[np.ndarray]: 每个通道一个结构化数组，包含 height/area 字段
        """
        st_waveforms = context.get_data(run_id, "st_waveforms")
        height_range = context.get_config(self, "height_range")
        area_range = context.get_config(self, "area_range")

        use_filtered = context.get_config(self, "use_filtered")
        if use_filtered:
            try:
                filtered_waveforms = context.get_data(run_id, "filtered_waveforms")
            except Exception:
                raise ValueError(
                    "use_filtered=True 但无法获取 filtered_waveforms。请先注册 FilteredWaveformsPlugin。"
                )
        else:
            filtered_waveforms = None

        if height_range is None:
            height_range = FeatureDefaults.PEAK_RANGE
        if area_range is None:
            area_range = FeatureDefaults.CHARGE_RANGE

        start_p, end_p = height_range
        start_c, end_c = area_range

        heights = []
        areas = []

        for i in range(len(st_waveforms)):
            st_ch = st_waveforms[i]
            if len(st_ch) == 0:
                heights.append(np.zeros(0))
                areas.append(np.zeros(0))
                continue

            waves = st_ch["wave"]
            if filtered_waveforms is not None:
                if i < len(filtered_waveforms):
                    waves = filtered_waveforms[i]
                else:
                    waves = None

            if waves is None or len(waves) == 0:
                heights.append(np.zeros(0))
                areas.append(np.zeros(0))
                continue
            if waves.ndim != 2:
                warnings.warn(
                    f"Waveforms for channel {i} are not 2D; skip feature calculation.",
                    UserWarning,
                )
                heights.append(np.zeros(0))
                areas.append(np.zeros(0))
                continue

            n_events = len(st_ch)
            if waves.shape[0] != n_events:
                n_events = min(waves.shape[0], n_events)
                if n_events == 0:
                    heights.append(np.zeros(0))
                    areas.append(np.zeros(0))
                    continue
                warnings.warn(
                    f"Waveforms length mismatch on channel {i}: "
                    f"{waves.shape[0]} vs {len(st_ch)}; truncating to {n_events}.",
                    UserWarning,
                )

            waves_p = waves[:n_events, start_p:end_p]
            height_vals = np.max(waves_p, axis=1) - np.min(waves_p, axis=1)
            heights.append(height_vals)

            waves_c = waves[:n_events, start_c:end_c]
            baselines = st_ch["baseline"][:n_events]
            area_vals = np.sum(baselines[:, np.newaxis] - waves_c, axis=1)
            areas.append(area_vals)
        features = []
        for height_ch, area_ch in zip(heights, areas):
            n_events = len(height_ch)
            ch_features = np.zeros(n_events, dtype=BASIC_FEATURES_DTYPE)
            if n_events > 0:
                ch_features["height"] = height_ch
                ch_features["area"] = area_ch
            features.append(ch_features)
        return features
