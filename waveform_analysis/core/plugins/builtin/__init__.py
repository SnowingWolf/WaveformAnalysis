# -*- coding: utf-8 -*-
"""
Plugins Builtin 子模块 - 内置标准插件

本模块采用按加速器划分的插件架构（自 2026-01 版本起）：

**CPU 插件** (`builtin/cpu/`):
- 标准数据处理插件: RawFiles, Waveforms, StWaveforms, Features, DataFrame, Events
- 滤波插件: FilteredWaveformsPlugin (scipy)
- 寻峰插件: SignalPeaksPlugin (scipy)

**JAX 插件** (`builtin/jax/`):
- 待实现：JAX 加速版本的滤波和寻峰插件

**流式插件** (`builtin/streaming/`):
- 待实现：CPU 和 JAX 流式插件

**遗留插件** (`builtin/legacy/`):
- 向后兼容保留，将在下一个主版本中移除

向后兼容：
所有插件可以通过以下方式导入：
    from waveform_analysis.core.plugins.builtin import RawFilesPlugin
    from waveform_analysis.core import RawFilesPlugin  # 通过 core.__init__.py 兼容
"""

# CPU 标准插件
from .cpu import (
    RawFilesPlugin,
    WaveformsPlugin,
    StWaveformsPlugin,
    HitFinderPlugin,
    BasicFeaturesPlugin,
    PeaksPlugin,
    ChargesPlugin,
    DataFramePlugin,
    GroupedEventsPlugin,
    PairedEventsPlugin,
    FilteredWaveformsPlugin,
    SignalPeaksPlugin,
    ADVANCED_PEAK_DTYPE,
)

# 流式插件示例（待迁移到 streaming/）
from .streaming_examples import (
    StreamingStWaveformsPlugin,
    StreamingBasicFeaturesPlugin,
    StreamingFilterPlugin,
)

# 标准插件列表（方便批量注册）
standard_plugins = [
    RawFilesPlugin(),
    WaveformsPlugin(),
    StWaveformsPlugin(),
    HitFinderPlugin(),
    BasicFeaturesPlugin(),
    PeaksPlugin(),
    ChargesPlugin(),
    DataFramePlugin(),
    GroupedEventsPlugin(),
    PairedEventsPlugin(),
]

__all__ = [
    # 标准插件类
    "RawFilesPlugin",
    "WaveformsPlugin",
    "StWaveformsPlugin",
    "HitFinderPlugin",
    "BasicFeaturesPlugin",
    "PeaksPlugin",
    "ChargesPlugin",
    "DataFramePlugin",
    "GroupedEventsPlugin",
    "PairedEventsPlugin",
    # 信号处理插件
    "FilteredWaveformsPlugin",
    "SignalPeaksPlugin",
    "ADVANCED_PEAK_DTYPE",
    # 流式插件示例
    "StreamingStWaveformsPlugin",
    "StreamingBasicFeaturesPlugin",
    "StreamingFilterPlugin",
    # 便捷列表
    "standard_plugins",
]
