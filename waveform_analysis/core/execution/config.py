# -*- coding: utf-8 -*-
"""
执行器配置模块 - 预定义常用执行器配置

提供常用的执行器配置模板，便于快速使用。
"""
from typing import Dict, Optional

from waveform_analysis.core.foundation.utils import exporter

# 初始化 exporter
export, __all__ = exporter()

# 预定义配置
EXECUTOR_CONFIGS = export({
    # IO密集型任务（文件读取、网络请求等）
    "io_intensive": {
        "executor_type": "thread",
        "max_workers": None,  # 使用默认值（通常是CPU核心数）
        "reuse": True,
    },
    
    # CPU密集型任务（计算、数据处理等）
    "cpu_intensive": {
        "executor_type": "process",
        "max_workers": None,
        "reuse": True,
    },
    
    # 大数据处理（多进程，较多工作进程）
    "large_data": {
        "executor_type": "process",
        "max_workers": 8,
        "reuse": True,
    },
    
    # 小数据快速处理（线程池，较少工作线程）
    "small_data": {
        "executor_type": "thread",
        "max_workers": 4,
        "reuse": True,
    },
    
    # 波形文件加载（IO密集型，多线程）
    "waveform_loading": {
        "executor_type": "thread",
        "max_workers": 10,
        "reuse": True,
    },
    
    # 事件聚类处理（CPU密集型，多进程）
    "event_grouping": {
        "executor_type": "process",
        "max_workers": None,
        "reuse": True,
    },
    
    # 特征计算（CPU密集型，多进程）
    "feature_computation": {
        "executor_type": "process",
        "max_workers": None,
        "reuse": True,
    },
}, name="EXECUTOR_CONFIGS")


def get_config(config_name: str) -> Dict:
    """
    获取预定义配置。
    
    参数:
        config_name: 配置名称
    
    返回:
        配置字典
    
    示例:
        config = get_config("cpu_intensive")
        with get_executor("my_task", **config) as ex:
            ...
    """
    if config_name not in EXECUTOR_CONFIGS:
        raise ValueError(f"未知配置: {config_name}. 可用配置: {list(EXECUTOR_CONFIGS.keys())}")
    return EXECUTOR_CONFIGS[config_name].copy()


def register_config(name: str, config: Dict):
    """
    注册新的配置。
    
    参数:
        name: 配置名称
        config: 配置字典
    """
    EXECUTOR_CONFIGS[name] = config.copy()

