"""
Event Analysis Plugins - 兼容 shim。

``GroupedEventsPlugin``（provides ``df_events``）与 ``PairedEventsPlugin``
（provides ``df_paired``）已分别迁至 bundle ``df_events`` / ``df_paired``。

本模块仅向后兼容转发全部符号。
"""

from waveform_analysis.core.plugins.builtin.df_events.plugin import GroupedEventsPlugin
from waveform_analysis.core.plugins.builtin.df_paired.plugin import PairedEventsPlugin

__all__ = [
    "GroupedEventsPlugin",
    "PairedEventsPlugin",
]
