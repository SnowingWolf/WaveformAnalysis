"""events bundle - provides 'events'。

EventPlugin 整合 S1-S2 配对、位置重建和事件级别特征，输出完整物理事件记录
（``EVENT_DTYPE``）。
"""

from waveform_analysis.core.plugins.builtin.events.plugin import (
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
