"""df bundle - provides 'df'。

DataFramePlugin 整合结构化波形与基础特征，构建包含所有事件信息的 pandas
DataFrame（单通道事件表）。
"""

from waveform_analysis.core.plugins.builtin.df.plugin import DataFramePlugin

__all__ = ["DataFramePlugin"]
