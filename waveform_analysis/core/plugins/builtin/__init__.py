# -*- coding: utf-8 -*-
"""
Plugins Builtin 子模块 - 内置标准插件

提供预定义的标准数据处理插件和流式处理插件示例。

标准插件：
- RawFilesPlugin: CSV 文件读取
- WaveformsPlugin: 波形提取
- StWaveformsPlugin: 波形结构化
- HitFinderPlugin: Hit 查找
- BasicFeaturesPlugin: 基础特征提取
- PeaksPlugin: 峰值特征
- ChargesPlugin: 电荷计算
- DataFramePlugin: DataFrame 构建
- GroupedEventsPlugin: 事件分组
- PairedEventsPlugin: 事件配对

信号处理插件：
- FilteredWaveformsPlugin: 波形滤波（Butterworth、Savitzky-Golay）
- SignalPeaksPlugin: 基于滤波波形的高级峰值检测

流式插件示例：
- StreamingStWaveformsPlugin: 流式波形结构化
- StreamingBasicFeaturesPlugin: 流式特征提取
- StreamingFilterPlugin: 流式数据过滤

向后兼容：
所有插件可以通过以下方式导入：
    from waveform_analysis.core.plugins.builtin import RawFilesPlugin
    from waveform_analysis.core import RawFilesPlugin  # 通过 core.__init__.py 兼容
"""

# 标准插件
from .standard import (
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
)

# 流式插件示例
from .streaming_examples import (
    StreamingStWaveformsPlugin,
    StreamingBasicFeaturesPlugin,
    StreamingFilterPlugin,
)

# 信号处理插件
from .signal_processing import (
    FilteredWaveformsPlugin,
    SignalPeaksPlugin,
    ADVANCED_PEAK_DTYPE,
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
