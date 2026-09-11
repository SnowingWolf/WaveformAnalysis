"""
peaks bundle - provides 'peaks'。

本目录是 PeaksPlugin 的 bundle（provides="peaks"，与旧家族目录同名，因此升级为该插件 bundle），
同时向后兼容转发 peaklet 家族各插件的类与 dtype 常量。旧深导入路径（``peaks.peaklets`` /
``peaks.peaklet_channels``）由同目录下的 shim 模块继续提供。
"""

from waveform_analysis._lazy_exports import LazyExport as _LazyExport
from waveform_analysis._lazy_exports import lazy_dir as _lazy_dir
from waveform_analysis._lazy_exports import (
    resolve_lazy_attribute as _resolve_lazy_attribute,
)

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


_BUILTIN = "waveform_analysis.core.plugins.builtin"
_LAZY_EXPORTS: dict[str, _LazyExport] = {
    "PeakletPlugin": (f"{_BUILTIN}.peaklets", "PeakletPlugin"),
    "PeakletComponentsPlugin": (
        f"{_BUILTIN}.peaklet_components",
        "PeakletComponentsPlugin",
    ),
    "PeakletWaveformPlugin": (
        f"{_BUILTIN}.peaklet_waveforms",
        "PeakletWaveformPlugin",
    ),
    "PeakletWaveformPoolPlugin": (
        f"{_BUILTIN}.peaklet_waveform_pool",
        "PeakletWaveformPoolPlugin",
    ),
    "PeakletFeaturesPlugin": (
        f"{_BUILTIN}.peaklet_features",
        "PeakletFeaturesPlugin",
    ),
    "PeakletChannelsPlugin": (
        f"{_BUILTIN}.peaklet_channels",
        "PeakletChannelsPlugin",
    ),
    "PeaksPlugin": (f"{_BUILTIN}.peaks.plugin", "PeaksPlugin"),
    "PEAKLET_DTYPE": (f"{_BUILTIN}.peaklets", "PEAKLET_DTYPE"),
    "PEAKLET_COMPONENTS_DTYPE": (
        f"{_BUILTIN}.peaklet_components",
        "PEAKLET_COMPONENTS_DTYPE",
    ),
    "PEAKLET_WAVEFORMS_DTYPE": (
        f"{_BUILTIN}.peaklet_waveforms",
        "PEAKLET_WAVEFORMS_DTYPE",
    ),
    "PEAKLET_FEATURES_DTYPE": (
        f"{_BUILTIN}.peaklet_features",
        "PEAKLET_FEATURES_DTYPE",
    ),
    "PEAKLET_CHANNELS_DTYPE": (
        f"{_BUILTIN}.peaklet_channels",
        "PEAKLET_CHANNELS_DTYPE",
    ),
    "PEAKS_DTYPE": (f"{_BUILTIN}.peaklets._compute", "PEAKS_DTYPE"),
    # The historical peaks.* shim modules remain available through getattr().
    "plugin": (f"{__name__}.plugin", None),
}

_LAZY_ATTRS = _LAZY_EXPORTS


def __getattr__(name: str):
    return _resolve_lazy_attribute(name, _LAZY_EXPORTS, globals())


def __dir__():
    return _lazy_dir(globals(), _LAZY_EXPORTS, __all__)
