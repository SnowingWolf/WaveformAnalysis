# -*- coding: utf-8 -*-
"""
Loader Utility - 数据加载工具，整合了文件扫描与 DAQRun 适配。
"""

from waveform_analysis.core.processing.loader import (
    WaveformLoader,
    build_filetime_index,
    get_files_before,
    get_files_by_filetime,
    get_raw_files,
    get_waveforms,
    get_waveforms_generator,
)
from waveform_analysis.core.foundation.utils import exporter

# 初始化 exporter
export, __all__ = exporter()

# Re-export for backward compatibility
RawFileLoader = export(WaveformLoader, name="RawFileLoader")
export(get_raw_files)
export(get_waveforms)
export(get_waveforms_generator)
export(build_filetime_index)
export(get_files_by_filetime)
export(get_files_before)
