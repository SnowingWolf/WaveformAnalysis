"""
Hit Finder Plugin - Hit 检测插件

**加速器**: CPU (NumPy/Numba)
**功能**: 从结构化波形中检测 Hit 事件

本模块包含 Hit 检测插件，使用阈值法从波形中识别和定位 Hit。
返回每个 Hit 的时间、面积、高度和宽度等特征。

支持使用原始波形或滤波后的波形进行检测。
"""

from typing import Any, List, Optional

import numpy as np

from waveform_analysis.core.plugins.core.base import Option, Plugin
from waveform_analysis.core.processing.dtypes import PEAK_DTYPE
from waveform_analysis.core.processing.event_grouping import find_hits


class HitFinderPlugin(Plugin):
    """Example implementation of the HitFinder as a plugin."""

    provides = "hits"
    depends_on = []  # 动态依赖，由 resolve_depends_on 决定
    version = "2.0.0"  # 版本升级：支持动态依赖切换
    output_dtype = np.dtype(PEAK_DTYPE)

    options = {
        "threshold": Option(default=10.0, type=float, help="Hit 检测阈值"),
        "use_filtered": Option(
            default=False,
            type=bool,
            help="是否使用 filtered_waveforms（需要先注册 FilteredWaveformsPlugin）",
        ),
    }

    def resolve_depends_on(self, context: Any, run_id: Optional[str] = None) -> List[str]:
        # 根据 use_filtered 动态选择依赖
        if context.get_config(self, "use_filtered"):
            return ["filtered_waveforms"]
        return ["st_waveforms"]

    def compute(self, context: Any, run_id: str, **_kwargs) -> List[np.ndarray]:
        """
        从结构化波形中检测 Hit 事件

        使用阈值法从波形中识别和定位 Hit（超过阈值的信号峰值）。
        返回每个 Hit 的时间、面积、高度和宽度等特征。

        Args:
            context: Context 实例
            run_id: 运行标识符
            **_kwargs: 未使用

        Returns:
            List[np.ndarray]: 每个通道的 Hit 列表，dtype 为 PEAK_DTYPE

        Examples:
            >>> hits = ctx.get_data('run_001', 'hits')
            >>> print(f"通道0的Hit数: {len(hits[0])}")
        """
        threshold = context.get_config(self, "threshold")
        use_filtered = context.get_config(self, "use_filtered")

        # 根据 use_filtered 选择数据源
        if use_filtered:
            waveform_data = context.get_data(run_id, "filtered_waveforms")
        else:
            waveform_data = context.get_data(run_id, "st_waveforms")

        hits_list = []
        for st_ch in waveform_data:
            if len(st_ch) == 0:
                hits_list.append(np.zeros(0, dtype=PEAK_DTYPE))
                continue

            # 使用每个通道的全部事件数
            waves_2d = np.stack(st_ch["wave"])
            hits = find_hits(waves_2d, st_ch["baseline"], threshold=threshold)
            hits_list.append(hits)
        return hits_list
