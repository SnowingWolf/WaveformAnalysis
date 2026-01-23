# -*- coding: utf-8 -*-
"""
事件筛选和属性提取工具函数。

提供用于筛选和提取事件数据的通用函数，支持numba加速。
"""
from typing import Callable, Dict, List, Optional

import numpy as np
import pandas as pd

# 尝试导入 numba 用于加速
try:
    from numba import jit
    NUMBA_AVAILABLE = True
except ImportError:
    NUMBA_AVAILABLE = False
    # 定义占位符装饰器
    def jit(*args, **kwargs):
        def decorator(func):
            return func
        return decorator


@jit(nopython=True, cache=True)
def _check_channels_match_numba(channels_arr, target_channels):
    """
    Numba加速的通道匹配检查函数（nopython模式）
    检查 channels_arr 是否包含所有 target_channels 中的通道
    
    参数:
        channels_arr: 通道数组（1D numpy数组）
        target_channels: 目标通道数组（1D numpy数组）
    
    返回:
        bool: 如果channels_arr包含所有target_channels中的通道则返回True
    """
    for target_ch in target_channels:
        found = False
        for ch in channels_arr:
            if ch == target_ch:
                found = True
                break
        if not found:
            return False
    return True


@jit(nopython=True, cache=True)
def _find_channel_index_numba(channels_arr, target_channel):
    """
    Numba加速的通道索引查找函数（nopython模式）
    在channels_arr中查找target_channel的索引
    
    参数:
        channels_arr: 通道数组（1D numpy数组）
        target_channel: 目标通道号
    
    返回:
        int: 如果找到返回索引，否则返回-1
    """
    for i in range(len(channels_arr)):
        if channels_arr[i] == target_channel:
            return i
    return -1


def filter_events_by_function(
    df_events: pd.DataFrame,
    filter_func: Callable,
    column: Optional[str] = None,
    use_vectorized: bool = True,
) -> pd.DataFrame:
    """
    通用的筛选函数，使用自定义函数对df_events进行筛选
    
    参数:
        df_events: 事件DataFrame
        filter_func: 筛选函数，可以是：
            - 接受Series（整行）的函数：lambda row: bool
            - 接受特定列值的函数：lambda value: bool（需要指定column）
        column: 可选，指定要操作的列名（用于向量化优化）
        use_vectorized: 是否尝试向量化优化（默认True）
    
    返回:
        DataFrame: 筛选后的事件DataFrame
    """
    if column is not None and use_vectorized:
        # 尝试向量化操作
        try:
            # 如果filter_func可以向量化，直接应用到列
            mask = filter_func(df_events[column])
            return df_events[mask]
        except:
            # 如果向量化失败，回退到apply
            pass
    
    # 使用apply进行筛选
    if column is not None:
        mask = df_events[column].apply(filter_func)
    else:
        mask = df_events.apply(filter_func, axis=1)
    
    return df_events[mask]


def filter_coincidence_events(
    df_events: pd.DataFrame,
    channels: List[int],
    use_vectorized: bool = True,
    use_numba: Optional[bool] = None,
) -> pd.DataFrame:
    """
    筛选同时包含所有指定通道的事件（Coincidence筛选）
    支持numba加速和向量化优化
    
    参数:
        df_events: 包含channels列的DataFrame
        channels: 要筛选的通道列表，如 [2, 3]
        use_vectorized: 是否使用向量化优化（默认True）
        use_numba: 是否使用numba加速（默认None，自动检测）
    
    返回:
        DataFrame: 筛选后的事件DataFrame
    """
    # 自动检测是否使用numba
    if use_numba is None:
        use_numba = NUMBA_AVAILABLE and use_vectorized
    
    # 将channels转换为numpy数组（用于numba）
    target_channels = np.asarray(channels, dtype=np.int64)
    
    if use_numba and NUMBA_AVAILABLE:
        # Numba加速版本：处理不等长的嵌套数组
        # channels列包含不等长的数组，.values返回对象数组（object array）
        channels_arr = df_events["channels"].values
        # 使用numba加速的检查函数
        mask = np.array([
            _check_channels_match_numba(np.asarray(chs, dtype=np.int64), target_channels)
            for chs in channels_arr
        ], dtype=bool)
        return df_events[mask]
    elif use_vectorized:
        # 向量化版本（无numba）：处理不等长的嵌套数组
        # channels列包含不等长的数组，.values返回对象数组（object array）
        # 使用列表推导式逐个处理，不依赖于数组长度的一致性
        channels_arr = df_events["channels"].values
        # 确保转换为列表以处理不等长数组（比apply快，且能处理不等长情况）
        mask = np.array([
            all(ch in np.asarray(chs) for ch in channels) 
            for chs in channels_arr
        ], dtype=bool)
        return df_events[mask]
    else:
        # 使用通用函数版本
        return filter_events_by_function(
            df_events,
            lambda chs: all(ch in chs for ch in channels),
            column="channels",
            use_vectorized=False
        )


def extract_channel_attributes(
    df_filtered: pd.DataFrame,
    channels: List[int],
    attribute: str = 'charges',
    use_numba: Optional[bool] = None,
) -> Dict[int, List]:
    """
    从筛选后的事件中提取指定通道的指定属性值
    支持numba加速
    
    参数:
        df_filtered: 筛选后的事件DataFrame
        channels: 要提取的通道列表，如 [2, 3]
        attribute: 要提取的属性名称，如 'charges', 'peaks', 'timestamps'
        use_numba: 是否使用numba加速（默认None，自动检测）
    
    返回:
        dict: {channel: [attribute_values]} 格式的字典
    """
    # 自动检测是否使用numba
    if use_numba is None:
        use_numba = NUMBA_AVAILABLE
    
    result = {ch: [] for ch in channels}
    
    # 使用iterrows遍历事件
    for idx, row in df_filtered.iterrows():
        channels_arr = np.asarray(row["channels"], dtype=np.int64)
        attributes_arr = np.asarray(row[attribute])
        
        for ch in channels:
            if use_numba and NUMBA_AVAILABLE:
                # 使用numba加速的查找函数
                idx_ch = _find_channel_index_numba(channels_arr, ch)
                if idx_ch >= 0:
                    result[ch].append(attributes_arr[idx_ch])
            else:
                # 使用numpy的where函数
                idx_ch = np.where(channels_arr == ch)[0]
                if len(idx_ch) > 0:
                    result[ch].append(attributes_arr[idx_ch[0]])
    
    return result

