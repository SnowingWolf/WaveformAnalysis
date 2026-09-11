"""peak_classification bundle - provides 'peak_classification'。

PeakClassificationPlugin 基于 peaks 的多维特征进行 S1/S2 信号类型甄别，
输出 ``PEAK_CLASSIFICATION_DTYPE``。标签常量（LABEL_S1/S2/S1_S2/UNKNOWN）
也由此 bundle 统一导出。
"""

from waveform_analysis.core.plugins.builtin.peak_classification.plugin import (
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
