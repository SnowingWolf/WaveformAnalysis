"""
时间计算工具函数

提供时间戳计算、pre_trigger 偏移处理等功能。
"""

from typing import Any

import numpy as np


def get_pre_trigger_offset_ps(context: Any) -> int:
    """
    从 context 获取 pre_trigger 时间偏移（皮秒）。

    许多 DAQ 系统（如 CAEN V1725/VX2730）的 record.timestamp 对应触发点时间，
    而波形的 sample 0 在触发点之前 pre_trigger 个采样点。此函数返回需要从
    timestamp 中减去的偏移量，以获得 sample 0 的真实时间。

    Args:
        context: Context 对象，包含配置信息

    Returns:
        pre_trigger_ps: pre_trigger 时间偏移（皮秒），用于修正时间戳
                       公式：sample_0_time = timestamp - pre_trigger_ps

    Examples:
        >>> pre_trigger_ps = get_pre_trigger_offset_ps(context)
        >>> corrected_timestamp = record.timestamp - pre_trigger_ps
    """
    pre_trigger_ns = context.config.get("pre_trigger_ns", 0)
    if pre_trigger_ns == 0:
        return 0

    # 转换为皮秒（1 ns = 1000 ps）
    return int(pre_trigger_ns * 1000)


def compute_absolute_time_ps(
    timestamp_ps: np.ndarray | int,
    sample_offset: np.ndarray | int,
    dt_ns: np.ndarray | int,
    pre_trigger_ps: int = 0,
) -> np.ndarray | int:
    """
    计算样本的绝对时间（皮秒）。

    此函数实现标准的时间计算公式，考虑 pre_trigger 偏移：

        abs_time = (timestamp - pre_trigger_ps) + sample_offset * dt_ps

    其中：
    - timestamp: record 的时间戳（对应触发点）
    - pre_trigger_ps: 触发点到 sample 0 的时间偏移
    - sample_offset: 目标样本相对某个参考位置的偏移
    - dt_ps: 采样间隔（皮秒）

    Args:
        timestamp_ps: record 的时间戳（皮秒，对应触发点时间）
        sample_offset: 样本相对 position 的偏移（采样点数）
        dt_ns: 采样间隔（纳秒）
        pre_trigger_ps: pre_trigger 时间偏移（皮秒），默认 0

    Returns:
        absolute_time_ps: 样本的绝对时间（皮秒）

    Examples:
        >>> # 单个时间戳
        >>> abs_time = compute_absolute_time_ps(1000000, 50, 2, pre_trigger_ps=200000)
        >>> # 向量化计算
        >>> timestamps = np.array([1000000, 2000000])
        >>> offsets = np.array([50, 100])
        >>> dt = np.array([2, 2])
        >>> abs_times = compute_absolute_time_ps(timestamps, offsets, dt, 200000)
    """
    # 转换为 int64 以支持大数值运算
    dt_ps = np.asarray(dt_ns, dtype=np.int64) * np.int64(1000)
    corrected_timestamp = np.asarray(timestamp_ps, dtype=np.int64) - np.int64(pre_trigger_ps)
    offset_ps = np.asarray(sample_offset, dtype=np.int64) * dt_ps

    return corrected_timestamp + offset_ps


def compute_absolute_time_window_ps(
    timestamp_ps: np.ndarray | int,
    start_sample: np.ndarray | int,
    end_sample: np.ndarray | int,
    position: np.ndarray | int,
    dt_ns: np.ndarray | int,
    pre_trigger_ps: int = 0,
) -> tuple[np.ndarray | int, np.ndarray | int]:
    """
    计算时间窗口的起止绝对时间（皮秒）。

    这是 compute_absolute_time_ps 的便捷包装，同时计算窗口的起止时间。

    Args:
        timestamp_ps: record 的时间戳（皮秒）
        start_sample: 窗口起始样本索引
        end_sample: 窗口结束样本索引
        position: 参考位置（timestamp 对应的样本索引，考虑 pre_trigger 后）
        dt_ns: 采样间隔（纳秒）
        pre_trigger_ps: pre_trigger 时间偏移（皮秒），默认 0

    Returns:
        (abs_start_ps, abs_end_ps): 窗口起止的绝对时间（皮秒）

    Examples:
        >>> t_start, t_end = compute_absolute_time_window_ps(
        ...     timestamp_ps=1000000,
        ...     start_sample=95,
        ...     end_sample=105,
        ...     position=100,
        ...     dt_ns=2,
        ...     pre_trigger_ps=200000
        ... )
    """
    dt_ps = np.asarray(dt_ns, dtype=np.int64) * np.int64(1000)
    corrected_timestamp = np.asarray(timestamp_ps, dtype=np.int64) - np.int64(pre_trigger_ps)
    position_arr = np.asarray(position, dtype=np.int64)

    start_offset = np.asarray(start_sample, dtype=np.int64) - position_arr
    end_offset = np.asarray(end_sample, dtype=np.int64) - position_arr

    abs_start_ps = corrected_timestamp + start_offset * dt_ps
    abs_end_ps = corrected_timestamp + end_offset * dt_ps

    return abs_start_ps, abs_end_ps


__all__ = [
    "get_pre_trigger_offset_ps",
    "compute_absolute_time_ps",
    "compute_absolute_time_window_ps",
]
