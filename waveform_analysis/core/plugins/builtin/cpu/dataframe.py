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
    version = "1.1.0"
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

        if not isinstance(st_waveforms, np.ndarray):
            raise ValueError("df expects st_waveforms as a single structured array")
        if not isinstance(basic_features, np.ndarray):
            raise ValueError("df expects basic_features as a single structured array")

        if len(st_waveforms) != len(basic_features):
            raise ValueError(
                f"basic_features length ({len(basic_features)}) != st_waveforms length ({len(st_waveforms)})"
            )

        df = pd.DataFrame(
            {
                "timestamp": np.asarray(st_waveforms["timestamp"]),
                "area": np.asarray(basic_features["area"]),
                "height": np.asarray(basic_features["height"]),
                "channel": np.asarray(st_waveforms["channel"]),
            }
        )
        return df.sort_values("timestamp")
