# -*- coding: utf-8 -*-
"""
Analyzer 模块 - 高层事件分析与配对逻辑。

提供 EventAnalyzer 类，用于对多通道命中 (Hits) 进行时间窗口聚类 (Grouping)
以及跨通道的事件配对 (Pairing)，是生成最终物理分析结果的关键步骤。
"""

from typing import Callable, Optional

import numpy as np
import pandas as pd

from waveform_analysis.core.foundation.utils import exporter

from .processor import group_multi_channel_hits

# 初始化 exporter
export, __all__ = exporter()


@export
class EventAnalyzer:
    """
    负责事件聚类、配对与分析。
    """

    def __init__(self, n_channels: int = 2, start_channel_slice: int = 6):
        """
        初始化事件分析器

        Args:
            n_channels: 分析的通道数（默认2）
            start_channel_slice: 起始通道索引（默认6）

        初始化内容:
        - 通道数和起始索引
        - 默认时间窗口（100ns）
        """
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

    def pair_events(self, df_events: pd.DataFrame, time_window_ns: Optional[float] = None) -> pd.DataFrame:
        """
        筛选成对的 N 通道事件。
        
        配对条件：
        - 事件的时间跨度（dt/ns）在指定的时间窗口内（默认100ns）
        - 不严格要求所有通道都存在，只要时间窗口满足即可
        
        参数:
            df_events: 分组后的事件DataFrame
            time_window_ns: 时间窗口（纳秒），默认使用self.time_window_ns
        """
        tw = time_window_ns if time_window_ns is not None else self.time_window_ns
        
        # 筛选条件：事件时间跨度在时间窗口内
        # dt/ns列已经在group_events中计算好了
        df_paired = df_events[df_events["dt/ns"] <= tw].copy()

        # 计算时间差（单位: ns）- 如果还没有计算
        if "delta_t" not in df_paired.columns:
            if not df_paired.empty:
                df_paired["delta_t"] = df_paired["timestamps"].apply(lambda x: (x[-1] - x[0]) / 1000.0)

        # 提取各通道的 charges 和 peaks（动态处理，根据实际通道数）
        if not df_paired.empty:
            for i in range(self.n_channels):
                ch_name = f"charge_ch{self.start_channel_slice + i}"
                pk_name = f"peak_ch{self.start_channel_slice + i}"
                
                def get_ch_value(arr, idx):
                    """安全地获取数组索引值"""
                    if isinstance(arr, (list, np.ndarray)) and len(arr) > idx:
                        return arr[idx]
                    return np.nan
                
                df_paired[ch_name] = df_paired["charges"].apply(lambda x: get_ch_value(x, i))
                df_paired[pk_name] = df_paired["peaks"].apply(lambda x: get_ch_value(x, i))

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
