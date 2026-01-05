"""
优化版本的 processor 函数，使用 numba 和向量化操作提升性能。
"""
import numpy as np
import pandas as pd
from typing import List, Tuple

try:
    from numba import jit, prange
    NUMBA_AVAILABLE = True
except ImportError:
    NUMBA_AVAILABLE = False
    # 定义占位符函数
    def jit(*args, **kwargs):
        def decorator(func):
            return func
        return decorator
    prange = range


@jit(nopython=True, cache=True)
def find_cluster_boundaries_fast(ts_all: np.ndarray, time_window_ps: float) -> np.ndarray:
    """
    快速找到所有簇的边界索引（使用numba加速）。
    
    参数:
        ts_all: 已排序的时间戳数组
        time_window_ps: 时间窗口（皮秒）
    
    返回:
        边界索引数组，包括0和n
    """
    n = len(ts_all)
    if n == 0:
        return np.array([0])
    
    boundaries = [0]
    curr = 0
    
    while curr < n:
        # 使用二分查找找到第一个超出时间窗口的索引
        target = ts_all[curr] + time_window_ps
        left, right = curr, n
        
        # 二分查找
        while left < right:
            mid = (left + right) // 2
            if ts_all[mid] <= target:
                left = mid + 1
            else:
                right = mid
        
        next_idx = left
        boundaries.append(next_idx)
        curr = next_idx
    
    return np.array(boundaries)


def group_multi_channel_hits_optimized(df: pd.DataFrame, time_window_ns: float) -> pd.DataFrame:
    """
    优化版本：在 df 中按 timestamp 聚类，找"同一事件的多通道触发"。
    
    优化点：
    1. 使用numba加速边界查找
    2. 向量化排序操作
    3. 减少数组复制
    4. 优化DataFrame构建
    
    参数:
        df: 包含 timestamp, channel, charge, peak 列的 DataFrame
        time_window_ns: 时间窗口（纳秒）
    
    返回:
        包含 event_id, t_min, t_max, dt/ns, n_hits, channels, charges, peaks, timestamps 的 DataFrame
    """
    time_window_ps = time_window_ns * 1e3
    
    # 先按时间排序一次
    df_sorted = df.sort_values("timestamp").reset_index(drop=True)
    
    # 一次性取成 numpy 数组
    ts_all = df_sorted["timestamp"].to_numpy()
    ch_all = df_sorted["channel"].to_numpy()
    q_all = df_sorted["charge"].to_numpy()
    p_all = df_sorted["peak"].to_numpy()
    
    n = len(df_sorted)
    if n == 0:
        return pd.DataFrame(
            columns=[
                "event_id",
                "t_min",
                "t_max",
                "dt/ns",
                "n_hits",
                "channels",
                "charges",
                "peaks",
                "timestamps",
            ]
        )
    
    # 使用优化的边界查找
    if NUMBA_AVAILABLE:
        boundaries = find_cluster_boundaries_fast(ts_all, time_window_ps)
    else:
        # 回退到原始方法
        boundaries = [0]
        curr = 0
        while curr < n:
            next_idx = np.searchsorted(ts_all, ts_all[curr] + time_window_ps, side="right")
            boundaries.append(next_idx)
            curr = next_idx
        boundaries = np.array(boundaries)
    
    n_events = len(boundaries) - 1
    
    # 预分配数组用于存储结果
    event_ids = np.arange(n_events, dtype=np.int64)
    t_mins = np.zeros(n_events, dtype=np.int64)
    t_maxs = np.zeros(n_events, dtype=np.int64)
    dt_ns = np.zeros(n_events, dtype=np.float64)
    n_hits_list = np.zeros(n_events, dtype=np.int32)
    
    # 预分配列表用于存储数组（因为每个事件的数组长度不同）
    channels_list = []
    charges_list = []
    peaks_list = []
    timestamps_list = []
    
    # 批量处理：先收集所有需要排序的数据
    for event_id in range(n_events):
        start, end = boundaries[event_id], boundaries[event_id + 1]
        
        # 提取数据
        ts = ts_all[start:end]
        chs = ch_all[start:end]
        qs = q_all[start:end]
        ps = p_all[start:end]
        
        # 按 channel 排序（使用 argsort，然后索引）
        sort_idx = np.argsort(chs)
        ts_sorted = ts[sort_idx]
        chs_sorted = chs[sort_idx]
        qs_sorted = qs[sort_idx]
        ps_sorted = ps[sort_idx]
        
        # 存储结果
        t_mins[event_id] = ts_sorted[0]
        t_maxs[event_id] = ts_sorted[-1]
        dt_ns[event_id] = (ts_sorted[-1] - ts_sorted[0]) / 1e3
        n_hits_list[event_id] = len(ts_sorted)
        
        channels_list.append(chs_sorted)
        charges_list.append(qs_sorted)
        peaks_list.append(ps_sorted)
        timestamps_list.append(ts_sorted)
    
    # 构建DataFrame（使用字典方式，比从records列表构建更快）
    return pd.DataFrame({
        "event_id": event_ids,
        "t_min": t_mins,
        "t_max": t_maxs,
        "dt/ns": dt_ns,
        "n_hits": n_hits_list,
        "channels": channels_list,
        "charges": charges_list,
        "peaks": peaks_list,
        "timestamps": timestamps_list,
    })


def group_multi_channel_hits_vectorized(df: pd.DataFrame, time_window_ns: float) -> pd.DataFrame:
    """
    进一步优化的向量化版本（实验性）。
    
    这个版本尝试减少Python循环，但可能在某些情况下不如优化版本快。
    """
    time_window_ps = time_window_ns * 1e3
    
    # 按时间排序
    df_sorted = df.sort_values("timestamp").reset_index(drop=True)
    
    ts_all = df_sorted["timestamp"].to_numpy()
    ch_all = df_sorted["channel"].to_numpy()
    q_all = df_sorted["charge"].to_numpy()
    p_all = df_sorted["peak"].to_numpy()
    
    n = len(df_sorted)
    if n == 0:
        return pd.DataFrame(
            columns=["event_id", "t_min", "t_max", "dt/ns", "n_hits", "channels", "charges", "peaks", "timestamps"]
        )
    
    # 找到边界
    if NUMBA_AVAILABLE:
        boundaries = find_cluster_boundaries_fast(ts_all, time_window_ps)
    else:
        boundaries = np.concatenate([[0], np.searchsorted(ts_all, ts_all + time_window_ps, side="right")])
        # 去重并保持顺序
        boundaries = np.unique(boundaries)
        if boundaries[-1] != n:
            boundaries = np.concatenate([boundaries, [n]])
    
    n_events = len(boundaries) - 1
    
    # 使用groupby风格的向量化操作
    event_ids = np.arange(n_events)
    t_mins = np.zeros(n_events, dtype=np.int64)
    t_maxs = np.zeros(n_events, dtype=np.int64)
    dt_ns = np.zeros(n_events, dtype=np.float64)
    n_hits_list = np.zeros(n_events, dtype=np.int32)
    
    channels_list = []
    charges_list = []
    peaks_list = []
    timestamps_list = []
    
    # 仍然需要循环来处理每个事件（因为每个事件的数组长度不同）
    for i in range(n_events):
        start, end = boundaries[i], boundaries[i + 1]
        
        # 提取并排序
        idx = np.arange(start, end)
        sort_idx_local = np.argsort(ch_all[idx])
        idx_sorted = idx[sort_idx_local]
        
        ts = ts_all[idx_sorted]
        chs = ch_all[idx_sorted]
        qs = q_all[idx_sorted]
        ps = p_all[idx_sorted]
        
        t_mins[i] = ts[0]
        t_maxs[i] = ts[-1]
        dt_ns[i] = (ts[-1] - ts[0]) / 1e3
        n_hits_list[i] = len(ts)
        
        channels_list.append(chs)
        charges_list.append(qs)
        peaks_list.append(ps)
        timestamps_list.append(ts)
    
    return pd.DataFrame({
        "event_id": event_ids,
        "t_min": t_mins,
        "t_max": t_maxs,
        "dt/ns": dt_ns,
        "n_hits": n_hits_list,
        "channels": channels_list,
        "charges": charges_list,
        "peaks": peaks_list,
        "timestamps": timestamps_list,
    })

