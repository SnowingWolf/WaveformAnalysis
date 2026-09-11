"""hit_threshold bundle - provides 'hit_threshold'。

ThresholdHitPlugin 类实现位于 ``plugin``，共享 numba 内核位于 ``_compute``
（原 hit_threshold_numba.py，家族属主持有）。
"""

from waveform_analysis.core.plugins.builtin.hit_threshold.plugin import (
    THRESHOLD_HIT_DTYPE,
    ThresholdHitPlugin,
)

__all__ = ["ThresholdHitPlugin", "THRESHOLD_HIT_DTYPE"]
