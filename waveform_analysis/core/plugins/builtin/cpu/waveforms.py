"""Waveforms Plugin - 兼容 shim。

``WaveformsPlugin`` / ``WaveformStruct`` / ``WaveformStructConfig`` /
``create_channel_mapping`` 已迁至 :mod:`waveform_analysis.core.plugins.builtin.st_waveforms`
（provides="st_waveforms"），``RawFileNamesPlugin`` 已迁至
:mod:`waveform_analysis.core.plugins.builtin.raw_files`（provides="raw_files"）。
本模块仅向后兼容转发全部符号（含记录侧依赖的私有 helper）。
"""

from waveform_analysis.core.plugins.builtin.raw_files import RawFileNamesPlugin
from waveform_analysis.core.plugins.builtin.st_waveforms import (
    WaveformsPlugin,
    WaveformStruct,
    WaveformStructConfig,
    create_channel_mapping,
)
from waveform_analysis.core.plugins.builtin.st_waveforms.plugin import (
    _build_polarity_lookup,
    _structure_waveforms_streaming,
)

__all__ = [
    "RawFileNamesPlugin",
    "WaveformsPlugin",
    "WaveformStruct",
    "WaveformStructConfig",
    "create_channel_mapping",
]
