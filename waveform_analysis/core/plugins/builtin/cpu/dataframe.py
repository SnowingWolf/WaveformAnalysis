# -*- coding: utf-8 -*-
"""
DataFrame Plugin - DataFrame 构建插件

**加速器**: CPU (NumPy/Pandas)
**功能**: 构建单通道事件的 DataFrame

本模块包含 DataFrame 构建插件，整合结构化波形与基础特征，
构建包含所有事件信息的 pandas DataFrame。
"""

from typing import Any

import numpy as np

from waveform_analysis.core.plugins.core.base import Plugin


class DataFramePlugin(Plugin):
    """Plugin to build the initial single-channel events DataFrame."""

    provides = "df"
    depends_on = ["st_waveforms", "basic_features"]
    save_when = "always"

    def compute(self, context: Any, run_id: str, **kwargs) -> Any:
        """
        构建单通道事件的 DataFrame

        整合结构化波形与 height/area 特征，构建包含所有事件信息的 pandas DataFrame。

        Args:
            context: Context 实例
            run_id: 运行标识符
            **kwargs: 依赖数据，包含 st_waveforms, basic_features

        Returns:
            pd.DataFrame: 包含所有通道事件的 DataFrame

        Examples:
            >>> df = ctx.get_data('run_001', 'df')
            >>> print(f"总事件数: {len(df)}")
        """
        import pandas as pd

        st_waveforms = context.get_data(run_id, "st_waveforms")
        basic_features = context.get_data(run_id, "basic_features")
        heights = [ch_features["height"] for ch_features in basic_features]
        areas = [ch_features["area"] for ch_features in basic_features]

        n_channels = len(st_waveforms)
        if len(heights) != n_channels:
            raise ValueError(f"heights list length ({len(heights)}) != st_waveforms length ({n_channels})")
        if len(areas) != n_channels:
            raise ValueError(f"areas list length ({len(areas)}) != st_waveforms length ({n_channels})")

        all_timestamps = []
        all_areas = []
        all_heights = []
        all_channels = []

        for ch in range(n_channels):
            ts = np.asarray(st_waveforms[ch]["timestamp"])
            area_vals = np.asarray(areas[ch])
            height_vals = np.asarray(heights[ch])

            all_timestamps.append(ts)
            all_areas.append(area_vals)
            all_heights.append(height_vals)
            all_channels.append(np.asarray(st_waveforms[ch]["channel"]))

        all_timestamps = np.concatenate(all_timestamps)
        all_areas = np.concatenate(all_areas)
        all_heights = np.concatenate(all_heights)
        all_channels = np.concatenate(all_channels)

        df = pd.DataFrame({
            "timestamp": all_timestamps,
            "area": all_areas,
            "height": all_heights,
            "channel": all_channels,
        })
        return df.sort_values("timestamp")
