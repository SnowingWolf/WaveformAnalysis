"""完整事件重建插件 - 兼容 shim。

``EventPlugin``（provides="events"）、``EVENT_DTYPE`` 与全部 ``FLAG_*`` 常量
已迁至 :mod:`waveform_analysis.core.plugins.builtin.events`。
本模块仅向后兼容转发全部符号。
"""

from waveform_analysis.core.plugins.builtin.events import (
    EVENT_DTYPE,
    FLAG_AMBIGUOUS_PAIRING,
    FLAG_EVENT_VALID,
    FLAG_FIDUCIAL_VOLUME,
    FLAG_LOW_S1,
    FLAG_LOW_S2,
    FLAG_POSITION_VALID,
    FLAG_SINGLE_SCATTER,
    EventPlugin,
)

__all__ = [
    "EventPlugin",
    "EVENT_DTYPE",
    "FLAG_EVENT_VALID",
    "FLAG_POSITION_VALID",
    "FLAG_FIDUCIAL_VOLUME",
    "FLAG_SINGLE_SCATTER",
    "FLAG_AMBIGUOUS_PAIRING",
    "FLAG_LOW_S1",
    "FLAG_LOW_S2",
]
