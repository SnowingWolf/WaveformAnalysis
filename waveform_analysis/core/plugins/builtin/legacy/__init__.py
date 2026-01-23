# -*- coding: utf-8 -*-
"""
遗留插件模块 - 向后兼容保留

本模块保留原始插件文件以确保向后兼容：
- standard.py: 原始标准插件（将被弃用）
- signal_processing.py: 原始信号处理插件（将被弃用）

**警告**: 这些插件已被重构为新的按加速器划分的结构。
建议迁移到新版本：
- CPU 插件: builtin/cpu/
- JAX 插件: builtin/jax/
- 流式插件: builtin/streaming/

**弃用时间表**: 将在下一个主版本中移除
"""

import warnings


def _deprecated_import(old_name: str, new_location: str):
    """发出弃用警告的辅助函数"""
    warnings.warn(
        f"{old_name} 已被弃用，将在下一个主版本中移除。"
        f"请使用 {new_location} 替代。",
        DeprecationWarning,
        stacklevel=3,
    )


# 从 standard.py 导入（带弃用警告）
def __getattr__(name):
    """延迟导入并发出弃用警告"""
    # 标准插件映射
    standard_plugins = {
        "RawFilesPlugin": "waveform_analysis.core.plugins.builtin.cpu.standard",
        "WaveformsPlugin": "waveform_analysis.core.plugins.builtin.cpu.standard",
        "StWaveformsPlugin": "waveform_analysis.core.plugins.builtin.cpu.standard",
        "HitFinderPlugin": "waveform_analysis.core.plugins.builtin.cpu.standard",
        "PeaksPlugin": "waveform_analysis.core.plugins.builtin.cpu.standard",
        "ChargesPlugin": "waveform_analysis.core.plugins.builtin.cpu.standard",
        "DataFramePlugin": "waveform_analysis.core.plugins.builtin.cpu.standard",
        "GroupedEventsPlugin": "waveform_analysis.core.plugins.builtin.cpu.standard",
        "PairedEventsPlugin": "waveform_analysis.core.plugins.builtin.cpu.standard",
    }

    # 信号处理插件映射
    signal_plugins = {
        "FilteredWaveformsPlugin": "waveform_analysis.core.plugins.builtin.cpu.filtering",
        "SignalPeaksPlugin": "waveform_analysis.core.plugins.builtin.cpu.peak_finding",
        "ADVANCED_PEAK_DTYPE": "waveform_analysis.core.plugins.builtin.cpu.peak_finding",
    }

    # 检查标准插件
    if name in standard_plugins:
        _deprecated_import(name, standard_plugins[name])
        from .standard import (
            ChargesPlugin,
            DataFramePlugin,
            GroupedEventsPlugin,
            HitFinderPlugin,
            PairedEventsPlugin,
            PeaksPlugin,
            RawFilesPlugin,
            StWaveformsPlugin,
            WaveformsPlugin,
        )
        return locals()[name]

    # 检查信号处理插件
    if name in signal_plugins:
        _deprecated_import(name, signal_plugins[name])
        from .signal_processing import (
            ADVANCED_PEAK_DTYPE,
            FilteredWaveformsPlugin,
            SignalPeaksPlugin,
        )
        return locals()[name]

    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


__all__ = [
    # 标准插件（已弃用）
    "RawFilesPlugin",
    "WaveformsPlugin",
    "StWaveformsPlugin",
    "HitFinderPlugin",
    "PeaksPlugin",
    "ChargesPlugin",
    "DataFramePlugin",
    "GroupedEventsPlugin",
    "PairedEventsPlugin",
    # 信号处理插件（已弃用）
    "FilteredWaveformsPlugin",
    "SignalPeaksPlugin",
    "ADVANCED_PEAK_DTYPE",
]
