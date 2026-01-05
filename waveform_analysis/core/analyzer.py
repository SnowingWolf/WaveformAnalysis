"""
Analyzer 模块 - 高层事件分析与配对逻辑。

提供 EventAnalyzer 类，用于对多通道命中 (Hits) 进行时间窗口聚类 (Grouping)
以及跨通道的事件配对 (Pairing)，是生成最终物理分析结果的关键步骤。
"""

from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from waveform_analysis.core.utils import exporter

from .processor import group_multi_channel_hits

# 初始化 exporter
export, __all__ = exporter()


@export
class EventAnalyzer:
    """
    负责事件聚类、配对与分析。
    """

    def __init__(self, n_channels: int = 2, start_channel_slice: int = 6):
        self.n_channels = n_channels
        self.start_channel_slice = start_channel_slice
        self.time_window_ns = 100

    def group_events(
        self,
        df: pd.DataFrame,
        time_window_ns: Optional[float] = None,
        use_numba: bool = True,
        n_processes: Optional[int] = None,
    ) -> pd.DataFrame:
        """
        按时间窗口聚类多通道事件。
        
        参数:
            df: 包含 timestamp, channel, charge, peak 列的 DataFrame
            time_window_ns: 时间窗口（纳秒）
            use_numba: 是否使用numba加速（默认True）
            n_processes: 多进程数量（None=单进程，>1=多进程）
        """
        if time_window_ns is not None:
            self.time_window_ns = time_window_ns

        return group_multi_channel_hits(df, self.time_window_ns, use_numba=use_numba, n_processes=n_processes)

    def pair_events(self, df_events: pd.DataFrame) -> pd.DataFrame:
        """
        筛选成对的 N 通道事件。
        """
        df_paired = df_events[
            (df_events["n_hits"] == self.n_channels)
            & (df_events["channels"].apply(lambda x: np.array_equal(x, list(range(self.n_channels)))))
        ].copy()

        # 计算时间差（单位: ns）
        if not df_paired.empty:
            df_paired["delta_t"] = df_paired["timestamps"].apply(lambda x: (x[-1] - x[0]) / 1000.0)

            # 提取各通道的 charges 和 peaks
            for i in range(self.n_channels):
                df_paired[f"charge_ch{self.start_channel_slice + i}"] = df_paired["charges"].apply(lambda x: x[i])
                df_paired[f"peak_ch{self.start_channel_slice + i}"] = df_paired["peaks"].apply(lambda x: x[i])

        return df_paired

    def pair_events_with(
        self, df_events: pd.DataFrame, strategy: Callable[[pd.DataFrame, int], pd.DataFrame]
    ) -> pd.DataFrame:
        """
        使用自定义策略对 df_events 进行配对过滤。
        """
        df_paired = strategy(df_events, self.n_channels).copy()

        # 若策略未计算 delta_t，这里进行补充
        if "timestamps" in df_paired.columns and "delta_t" not in df_paired.columns:
            df_paired["delta_t"] = df_paired["timestamps"].apply(lambda x: (x[-1] - x[0]) / 1000.0)

        # 若策略保留了 charges / peaks，则生成派生列
        if "charges" in df_paired.columns:
            for i in range(min(self.n_channels, 8)):
                df_paired[f"charge_ch{self.start_channel_slice + i}"] = df_paired["charges"].apply(
                    lambda x: x[i] if len(x) > i else np.nan
                )
        if "peaks" in df_paired.columns:
            for i in range(min(self.n_channels, 8)):
                df_paired[f"peak_ch{self.start_channel_slice + i}"] = df_paired["peaks"].apply(
                    lambda x: x[i] if len(x) > i else np.nan
                )

        return df_paired
