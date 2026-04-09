"""
Plugins Builtin 子模块 - 内置标准插件

本模块采用按加速器划分的插件架构（自 2026-01 版本起）：

**CPU 插件** (`builtin/cpu/`):
- 标准数据处理插件: RawFileNames, Waveforms (合并了 StWaveforms), Features, DataFrame, Events
- 滤波插件: FilteredWaveformsPlugin (scipy)
- 寻峰插件: HitFinderPlugin (scipy)

**JAX 插件** (`builtin/jax/`):
- 待实现：JAX 加速版本的滤波和寻峰插件

**流式插件** (`builtin/streaming/`):
- CPU 流式插件: SignalPeaksStreamPlugin
- JAX 流式插件待实现

向后兼容：
所有插件可以通过以下方式导入：
    from waveform_analysis.core.plugins.builtin.cpu import RawFileNamesPlugin
"""

# CPU 标准插件
from .cpu import (
    HIT_DTYPE,
    WAVEFORM_WIDTH_DTYPE,
    WAVEFORM_WIDTH_INTEGRAL_DTYPE,
    BasicFeaturesPlugin,
    CacheAnalysisPlugin,
    DataFramePlugin,
    FilteredWaveformsPlugin,
    GroupedEventsPlugin,
    HitFinderPlugin,
    PairedEventsPlugin,
    RawFileNamesPlugin,
    RawFilesPlugin,
    RecordsPlugin,
    StWaveformsPlugin,
    WaveformsPlugin,
    WaveformStruct,
    WaveformStructConfig,
    WaveformWidthIntegralPlugin,
    WaveformWidthPlugin,
    WavePoolPlugin,
    standard_plugins,
)

# 流式插件
from .streaming import SignalPeaksStreamPlugin

__all__ = [
    # 标准插件类
    "RawFileNamesPlugin",
    "RawFilesPlugin",
    "WaveformsPlugin",
    "StWaveformsPlugin",
    "WaveformStruct",
    "WaveformStructConfig",
    "HitFinderPlugin",
    "BasicFeaturesPlugin",
    "DataFramePlugin",
    "GroupedEventsPlugin",
    "PairedEventsPlugin",
    "RecordsPlugin",
    "WavePoolPlugin",
    # 信号处理插件
    "FilteredWaveformsPlugin",
    "HIT_DTYPE",
    "WaveformWidthPlugin",
    "WAVEFORM_WIDTH_DTYPE",
    "WaveformWidthIntegralPlugin",
    "WAVEFORM_WIDTH_INTEGRAL_DTYPE",
    "CacheAnalysisPlugin",
    # 流式插件
    "SignalPeaksStreamPlugin",
    # 便捷列表
    "standard_plugins",
]
