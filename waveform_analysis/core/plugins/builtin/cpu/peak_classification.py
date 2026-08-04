"""S1/S2 分类插件 - 兼容 shim。

``PeakClassificationPlugin``（provides="peak_classification"）、
``PEAK_CLASSIFICATION_DTYPE`` 与标签常量（``LABEL_S1`` / ``LABEL_S2`` /
``LABEL_S1_S2`` / ``LABEL_UNKNOWN``）已迁至
:mod:`waveform_analysis.core.plugins.builtin.peak_classification`。
本模块仅向后兼容转发全部符号。
"""

from waveform_analysis.core.plugins.builtin.peak_classification import (
    LABEL_S1,
    LABEL_S1_S2,
    LABEL_S2,
    LABEL_UNKNOWN,
    PEAK_CLASSIFICATION_DTYPE,
    PeakClassificationPlugin,
)

__all__ = [
    "PeakClassificationPlugin",
    "PEAK_CLASSIFICATION_DTYPE",
    "LABEL_S1",
    "LABEL_S2",
    "LABEL_S1_S2",
    "LABEL_UNKNOWN",
]
