"""st_waveforms bundle - provides 'st_waveforms'。

WaveformsPlugin 从原始 CSV 文件提取波形数据并结构化为 NumPy 结构化数组
（ST_WAVEFORM_DTYPE）。共享计算（WaveformStruct / WaveformStructConfig /
create_channel_mapping 及私有 helper）位于 ``plugin``。
"""

from waveform_analysis.core.plugins.builtin.st_waveforms.plugin import (
    WaveformsPlugin,
    WaveformStruct,
    WaveformStructConfig,
    create_channel_mapping,
)

__all__ = [
    "WaveformsPlugin",
    "WaveformStruct",
    "WaveformStructConfig",
    "create_channel_mapping",
]
