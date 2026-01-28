# -*- coding: utf-8 -*-
"""
Processor 模块 - 波形信号处理与特征提取核心逻辑。

本模块负责波形信号处理与特征提取。
核心功能包括：
1. **特征提取**：提供 `find_hits` (向量化寻峰)、基线扣除、电荷积分 (Charge) 与幅度 (Peak) 计算。
2. **事件聚类**：`group_multi_channel_hits` 基于时间窗口将多通道 Hit 聚类为物理事件。
3. **通道编码**：提供二进制掩码 (Bitmask) 与权重编码工具，用于多通道符合逻辑筛选。

说明：
- `WaveformStruct` 已移至 `waveform_struct` 模块。
- `DataFramePlugin`: 在插件层拼接结构化波形与特征 DataFrame。
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from waveform_analysis.core.execution.manager import get_executor
from waveform_analysis.core.foundation.utils import exporter

# Setup logger
logger = logging.getLogger(__name__)

# 尝试导入numba（可选）
try:
    from numba import jit, prange

    NUMBA_AVAILABLE = True
except ImportError:
    NUMBA_AVAILABLE = False

    def jit(*args, **kwargs):
        def decorator(func):
            return func

        return decorator

    prange = range

# 初始化 exporter
export, __all__ = exporter()

# Peak: A detected peak in a waveform
PEAK_DTYPE = export(
    [
        ("time", "i8"),  # time of the peak
        ("area", "f4"),  # area of the peak
        ("height", "f4"),  # height of the peak
        ("width", "f4"),  # width of the peak
        ("channel", "i2"),  # channel index
        ("event_index", "i8"),  # index of the event in the dataset
    ],
    name="PEAK_DTYPE",
)


@export
def find_hits(
    waves: np.ndarray,
    baselines: np.ndarray,
    threshold: float,
    left_extension: int = 2,
    right_extension: int = 2,
) -> np.ndarray:
    """
    Vectorized hit-finding. Finds contiguous regions where (baseline - wave) > threshold.

    Args:
        waves: 2D array of waveforms (n_events, n_samples)
        baselines: 1D array of baselines (n_events)
        threshold: threshold for hit detection
        left_extension: number of samples to extend hit to the left
        right_extension: number of samples to extend hit to the right

    Returns:
        A structured array of hits (PEAK_DTYPE).
        Note: This returns a flat array of all hits found across all events.
    """
    if waves.size == 0:
        return np.zeros(0, dtype=PEAK_DTYPE)

    # Signal is baseline - wave (assuming negative pulses)
    signal = baselines[:, np.newaxis] - waves
    mask = signal > threshold

    # Find starts and ends of contiguous regions
    # We pad with False to catch hits at the boundaries
    mask_padded = np.pad(mask, ((0, 0), (1, 1)), mode="constant", constant_values=False)
    diff = np.diff(mask_padded.astype(np.int8), axis=1)

    starts = np.where(diff == 1)
    ends = np.where(diff == -1)

    # starts and ends are tuples (event_indices, sample_indices)
    event_indices = starts[0]
    s_starts = starts[1]
    s_ends = ends[1]

    n_hits = len(event_indices)
    hits = np.zeros(n_hits, dtype=PEAK_DTYPE)

    hits["event_index"] = event_indices
    hits["time"] = s_starts  # Relative to start of waveform
    # Note: area, height, width calculation would go here or in a separate step
    # For now we just return the hits with time and event_index
    return hits


@export
@export
def group_multi_channel_hits(
    df: pd.DataFrame,
    time_window_ns: float,
    use_numba: bool = True,
    n_processes: Optional[int] = None,
) -> pd.DataFrame:
    """
    在 df 中按 timestamp 聚类，找"同一事件的多通道触发"，并在簇内部
    按 channel 从小到大对 (channels, areas, heights, timestamps) 同步排序。

    参数:
        df: 包含 timestamp, channel, area, height 列的 DataFrame
            - timestamp 列的单位为 ps（皮秒）
        time_window_ns: 时间窗口（纳秒），默认值为100ns
            - 内部会转换为 ps 单位与 timestamp 进行比较
            - 例如：100ns = 100,000ps
        use_numba: 是否使用numba加速（默认True，如果numba可用）
        n_processes: 多进程数量（None=单进程，>1=多进程，默认None）

    注意:
        - timestamp 列的单位为 ps（皮秒）
        - time_window_ns 参数单位为 ns（纳秒），内部会自动转换为 ps 进行比较
        - 时间窗口转换：time_window_ps = time_window_ns * 1e3

    性能优化:
        - 使用numba JIT编译加速边界查找（如果可用）
        - 支持多进程并行处理事件簇（适用于超大数据集）
        - 优化DataFrame构建方式
        - 减少不必要的数组复制

    示例:
        # 使用numba加速（单进程），时间窗口100ns
        df_events = group_multi_channel_hits(df, time_window_ns=100)

        # 使用多进程（4个进程）
        df_events = group_multi_channel_hits(df, time_window_ns=100, n_processes=4)

        # 禁用numba，使用多进程
        df_events = group_multi_channel_hits(df, time_window_ns=100, use_numba=False, n_processes=4)
    """
    time_window_ps = time_window_ns * 1e3

    # 先按时间排序一次
    df_sorted = df.sort_values("timestamp").reset_index(drop=True)

    # 一次性取成 numpy 数组，后面循环只处理索引，少做 iloc / array 构造
    ts_all = df_sorted["timestamp"].to_numpy()
    ch_all = df_sorted["channel"].to_numpy()
    area_col = "area" if "area" in df_sorted.columns else "charge"
    height_col = "height" if "height" in df_sorted.columns else "peak"
    if area_col not in df_sorted.columns or height_col not in df_sorted.columns:
        raise KeyError("df must contain area/height (or charge/peak) columns")
    area_all = df_sorted[area_col].to_numpy()
    height_all = df_sorted[height_col].to_numpy()

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
                "areas",
                "heights",
                "timestamps",
            ]
        )

    # 查找边界（使用numba加速如果可用）
    if use_numba and NUMBA_AVAILABLE:
        boundaries = _find_cluster_boundaries_numba(ts_all, time_window_ps)
    else:
        boundaries = [0]
        curr = 0
        while curr < n:
            next_idx = np.searchsorted(ts_all, ts_all[curr] + time_window_ps, side="right")
            boundaries.append(next_idx)
            curr = next_idx
        boundaries = np.array(boundaries)

    n_events = len(boundaries) - 1

    # 多进程处理（适用于超大数据集）
    if n_processes and n_processes > 1 and n_events > 1000:  # 只有事件数足够多时才使用多进程
        # 将事件分块
        chunk_size = max(1, n_events // n_processes)
        chunks = []
        for i in range(0, n_events, chunk_size):
            chunks.append((i, min(i + chunk_size, n_events)))

        # 准备参数
        args_list = [(ts_all, ch_all, area_all, height_all, boundaries, start, end) for start, end in chunks]

        # 多进程处理（使用全局执行器管理器）
        records = []
        from concurrent.futures import as_completed

        with get_executor("event_grouping", executor_type="process", max_workers=n_processes, reuse=True) as executor:
            futures = {executor.submit(_process_event_chunk, args): args for args in args_list}
            for future in as_completed(futures):
                try:
                    chunk_records = future.result()
                    records.extend(chunk_records)
                except (MemoryError, KeyboardInterrupt):
                    # 致命错误：立即抛出
                    raise
                except Exception as e:
                    logger.warning(f"Multiprocessing chunk failed ({e}), falling back to single-process")
                    # 可恢复错误：回退到单进程处理该块
                    args = futures[future]
                    chunk_records = _process_event_chunk(args)
                    records.extend(chunk_records)

        # 按event_id排序（因为多进程处理顺序可能不同）
        records.sort(key=lambda x: x["event_id"])

        # 构建DataFrame
        return pd.DataFrame(records)

    else:
        # 单进程处理（优化版本）
        event_ids = np.arange(n_events, dtype=np.int64)
        t_mins = np.zeros(n_events, dtype=np.int64)
        t_maxs = np.zeros(n_events, dtype=np.int64)
        dt_ns = np.zeros(n_events, dtype=np.float64)
        n_hits_list = np.zeros(n_events, dtype=np.int32)

        channels_list = []
        areas_list = []
        heights_list = []
        timestamps_list = []

        # 处理每个事件
        for event_id in range(n_events):
            start, end = boundaries[event_id], boundaries[event_id + 1]

            ts = ts_all[start:end]
            chs = ch_all[start:end]
            areas = area_all[start:end]
            heights = height_all[start:end]

            # 按channel排序
            sort_idx = np.argsort(chs)
            ts_sorted = ts[sort_idx]
            chs_sorted = chs[sort_idx]
            areas_sorted = areas[sort_idx]
            heights_sorted = heights[sort_idx]

            t_min = ts_sorted[0]
            t_max = ts_sorted[-1]

            # 存储结果
            t_mins[event_id] = t_min
            t_maxs[event_id] = t_max
            dt_ns[event_id] = (t_max - t_min) / 1e3
            n_hits_list[event_id] = len(ts_sorted)

            channels_list.append(chs_sorted)
            areas_list.append(areas_sorted)
            heights_list.append(heights_sorted)
            timestamps_list.append(ts_sorted)

        # 使用字典方式构建DataFrame
        return pd.DataFrame({
            "event_id": event_ids,
            "t_min": t_mins,
            "t_max": t_maxs,
            "dt/ns": dt_ns,
            "n_hits": n_hits_list,
            "channels": channels_list,
            "areas": areas_list,
            "heights": heights_list,
            "timestamps": timestamps_list,
        })


# Numba加速的边界查找函数（模块级别定义，numba要求）
if NUMBA_AVAILABLE:

    @jit(nopython=True, cache=True)
    def _find_cluster_boundaries_numba(ts_all: np.ndarray, time_window_ps: float) -> np.ndarray:
        """
        使用numba加速的边界查找。

        参数:
            ts_all: 已排序的时间戳数组
            time_window_ps: 时间窗口（皮秒）

        返回:
            边界索引数组
        """
        n = len(ts_all)
        if n == 0:
            return np.array([0])

        boundaries = [0]
        curr = 0

        while curr < n:
            target = ts_all[curr] + time_window_ps
            # 二分查找（比searchsorted稍快，因为numba编译）
            left, right = curr, n
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

else:

    def _find_cluster_boundaries_numba(ts_all: np.ndarray, time_window_ps: float) -> np.ndarray:
        """回退到numpy实现"""
        n = len(ts_all)
        if n == 0:
            return np.array([0])
        boundaries = [0]
        curr = 0
        while curr < n:
            next_idx = np.searchsorted(ts_all, ts_all[curr] + time_window_ps, side="right")
            boundaries.append(next_idx)
            curr = next_idx
        return np.array(boundaries)


def _process_event_chunk(args: Tuple) -> List[Dict]:
    """
    处理事件块（用于多进程）。

    参数:
        args: (ts_all, ch_all, q_all, p_all, boundaries, start_idx, end_idx)
        注意：numpy数组在多进程间传递时需要确保是可序列化的

    返回:
        事件记录列表
    """
    # 解包参数
    ts_all, ch_all, area_all, height_all, boundaries, start_idx, end_idx = args

    # 确保是numpy数组（多进程传递后可能变成列表）
    ts_all = np.asarray(ts_all)
    ch_all = np.asarray(ch_all)
    area_all = np.asarray(area_all)
    height_all = np.asarray(height_all)
    boundaries = np.asarray(boundaries)

    records = []
    for i in range(start_idx, end_idx):
        if i >= len(boundaries) - 1:
            break
        start, end = int(boundaries[i]), int(boundaries[i + 1])

        ts = ts_all[start:end]
        chs = ch_all[start:end]
        areas = area_all[start:end]
        heights = height_all[start:end]

        # 按channel排序
        sort_idx = np.argsort(chs)
        ts_sorted = ts[sort_idx]
        chs_sorted = chs[sort_idx]
        areas_sorted = areas[sort_idx]
        heights_sorted = heights[sort_idx]

        t_min = int(ts_sorted[0])
        t_max = int(ts_sorted[-1])

        records.append({
            "event_id": int(i),
            "t_min": t_min,
            "t_max": t_max,
            "dt/ns": float((t_max - t_min) / 1e3),
            "n_hits": int(len(ts_sorted)),
            "channels": chs_sorted,  # 只读访问，无需复制
            "areas": areas_sorted,
            "heights": heights_sorted,
            "timestamps": ts_sorted,
        })

    return records
