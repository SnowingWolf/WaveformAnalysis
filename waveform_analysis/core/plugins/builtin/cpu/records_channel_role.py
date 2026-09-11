"""Records-backed channel role masks - 兼容 shim。

``RecordsDetectorMaskPlugin`` / ``RecordsVetoMaskPlugin`` 与共享的角色解析
（``_RecordsChannelRoleMaskPlugin``、``_resolve_roles``、角色常量）已迁至 bundle
``records_detector_mask``（算法属主）与 ``records_veto_mask``（单向依赖属主）。

本模块仅向后兼容转发全部对外符号。
"""

from waveform_analysis.core.plugins.builtin.records_detector_mask._compute import (
    ROLE_DETECTOR,
    ROLE_VETO,
    VALID_ROLES,
    _empty_mask,
    _RecordsChannelRoleMaskPlugin,
    _resolve_roles,
)
from waveform_analysis.core.plugins.builtin.records_detector_mask.plugin import (
    RecordsDetectorMaskPlugin,
)
from waveform_analysis.core.plugins.builtin.records_veto_mask.plugin import (
    RecordsVetoMaskPlugin,
)

__all__ = [
    "ROLE_DETECTOR",
    "ROLE_VETO",
    "VALID_ROLES",
    "RecordsDetectorMaskPlugin",
    "RecordsVetoMaskPlugin",
    "_RecordsChannelRoleMaskPlugin",
    "_empty_mask",
    "_resolve_roles",
]
