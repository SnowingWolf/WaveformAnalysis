"""records_detector_mask bundle - provides 'records_detector_mask'。

本 bundle 是 channel-role masks 家族的算法属主：角色解析与基类位于 ``_compute``，
兄弟 bundle ``records_veto_mask`` 单向依赖本模块。
"""

from waveform_analysis.core.plugins.builtin.records_detector_mask.plugin import (
    RecordsDetectorMaskPlugin,
)

__all__ = ["RecordsDetectorMaskPlugin"]
