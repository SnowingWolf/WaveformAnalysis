"""
peaks bundle - provides 'peaks'。

本目录是 PeaksPlugin 的 bundle（provides="peaks"，与旧家族目录同名，因此升级为该插件 bundle），
同时向后兼容转发 peaklet 家族各插件的类与 dtype 常量。旧深导入路径（``peaks.peaklets`` /
``peaks.peaklet_channels``）由同目录下的 shim 模块继续提供。
"""

from waveform_analysis.core.plugins.builtin.peaklet_channels import (
    PEAKLET_CHANNELS_DTYPE,
    PeakletChannelsPlugin,
)
from waveform_analysis.core.plugins.builtin.peaklet_components import (
    PEAKLET_COMPONENTS_DTYPE,
    PeakletComponentsPlugin,
)
from waveform_analysis.core.plugins.builtin.peaklet_features import (
    PEAKLET_FEATURES_DTYPE,
    PeakletFeaturesPlugin,
)
from waveform_analysis.core.plugins.builtin.peaklet_waveform_pool import (
    PeakletWaveformPoolPlugin,
)
from waveform_analysis.core.plugins.builtin.peaklet_waveforms import (
    PEAKLET_WAVEFORMS_DTYPE,
    PeakletWaveformPlugin,
)
from waveform_analysis.core.plugins.builtin.peaklets import PEAKLET_DTYPE, PeakletPlugin
from waveform_analysis.core.plugins.builtin.peaklets._compute import PEAKS_DTYPE
from waveform_analysis.core.plugins.builtin.peaks.plugin import PeaksPlugin

__all__ = [
    # Peaklet 插件
    "PeakletPlugin",
    "PeakletComponentsPlugin",
    "PeakletWaveformPlugin",
    "PeakletWaveformPoolPlugin",
    "PeakletFeaturesPlugin",
    "PeakletChannelsPlugin",
    "PeaksPlugin",
    # 数据类型
    "PEAKLET_DTYPE",
    "PEAKLET_COMPONENTS_DTYPE",
    "PEAKLET_WAVEFORMS_DTYPE",
    "PEAKLET_FEATURES_DTYPE",
    "PEAKLET_CHANNELS_DTYPE",
    "PEAKS_DTYPE",
]
