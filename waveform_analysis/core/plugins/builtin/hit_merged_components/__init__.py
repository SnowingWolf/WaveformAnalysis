"""hit_merged_components bundle - provides 'hit_merged_components'。

共享计算来自属主 bundle ``hit_merged``（_compute）。本 bundle 仅导出 HitMergedComponentsPlugin。
"""

from waveform_analysis.core.plugins.builtin.hit_merged._compute import (
    HIT_MERGED_COMPONENTS_DTYPE,
)
from waveform_analysis.core.plugins.builtin.hit_merged_components.plugin import (
    HitMergedComponentsPlugin,
)

__all__ = ["HitMergedComponentsPlugin", "HIT_MERGED_COMPONENTS_DTYPE"]
