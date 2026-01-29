# -*- coding: utf-8 -*-
"""
Hit Finder Plugin - Hit 检测插件

**加速器**: CPU (NumPy/Numba)
**功能**: 从结构化波形中检测 Hit 事件

本模块包含 Hit 检测插件，使用阈值法从波形中识别和定位 Hit。
返回每个 Hit 的时间、面积、高度和宽度等特征。
"""

from typing import Any, List

import numpy as np

from waveform_analysis.core.plugins.core.base import Plugin
from waveform_analysis.core.processing.dtypes import PEAK_DTYPE
from waveform_analysis.core.processing.event_grouping import find_hits


class HitFinderPlugin(Plugin):
    """Example implementation of the HitFinder as a plugin."""

    provides = "hits"
    depends_on = ["st_waveforms"]
    output_dtype = np.dtype(PEAK_DTYPE)

    def compute(self, context: Any, run_id: str, threshold: float = 10.0, **kwargs) -> List[np.ndarray]:
        """
        从结构化波形中检测 Hit 事件

        使用阈值法从波形中识别和定位 Hit（超过阈值的信号峰值）。
        返回每个 Hit 的时间、面积、高度和宽度等特征。

        Args:
            context: Context 实例
            run_id: 运行标识符
            threshold: Hit 检测阈值（默认10.0）
            **kwargs: 依赖数据，包含 st_waveforms

        Returns:
            List[np.ndarray]: 每个通道的 Hit 列表，dtype 为 PEAK_DTYPE

        Examples:
            >>> hits = ctx.get_data('run_001', 'hits')
            >>> print(f"通道0的Hit数: {len(hits[0])}")
        """
        st_waveforms = context.get_data(run_id, "st_waveforms")

        hits_list = []
        for i in range(len(st_waveforms)):
            st_ch = st_waveforms[i]
            if len(st_ch) == 0:
                hits_list.append(np.zeros(0, dtype=PEAK_DTYPE))
                continue

            # 使用每个通道的全部事件数
            waves_2d = np.stack(st_ch["wave"])
            hits = find_hits(waves_2d, st_ch["baseline"], threshold=threshold)
            hits_list.append(hits)
        return hits_list
