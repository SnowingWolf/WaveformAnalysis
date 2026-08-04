"""RecordsDetectorMaskPlugin 类实现 - detector 通道角色掩码。"""

from waveform_analysis.core.plugins.builtin.records_detector_mask._compute import (
    ROLE_DETECTOR,
    _RecordsChannelRoleMaskPlugin,
)


class RecordsDetectorMaskPlugin(_RecordsChannelRoleMaskPlugin):
    """Bool mask for records that should enter normal detector hit finding."""

    provides = "records_detector_mask"
    description = "Bool mask for detector-channel records after channel-role splitting."
    version = "0.1.0"
    role = ROLE_DETECTOR


__all__ = ["RecordsDetectorMaskPlugin"]
