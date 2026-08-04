"""Hit Finder - 兼容 shim。

``THRESHOLD_HIT_DTYPE`` / ``ThresholdHitPlugin`` 已迁至
:mod:`waveform_analysis.core.plugins.builtin.hit_threshold`（算法属主，共享 numba 内核位于其
``_compute``）。``HitFinderPlugin`` 的 canonical 实现位于
:mod:`waveform_analysis.core.plugins.builtin.hit`（provides='hit'）。

本模块仅保留旧导入路径：
1. ``HitFinderPlugin``: 旧导入路径兼容别名（推荐改为 builtin.hit.HitFinderPlugin）
2. ``ThresholdHitPlugin`` / ``THRESHOLD_HIT_DTYPE``: 转发自 hit_threshold bundle
"""

import warnings

from waveform_analysis.core.plugins.builtin.cpu.peak_finding import (
    HitFinderPlugin as _CanonicalHitFinderPlugin,
)
from waveform_analysis.core.plugins.builtin.hit_threshold import (
    THRESHOLD_HIT_DTYPE,
    ThresholdHitPlugin,
)

__all__ = ["HitFinderPlugin", "ThresholdHitPlugin", "THRESHOLD_HIT_DTYPE"]


class HitFinderPlugin(_CanonicalHitFinderPlugin):
    """Deprecated import-path alias for hit.HitFinderPlugin."""

    def __init__(self, *args, **kwargs):
        warnings.warn(
            "Importing HitFinderPlugin from "
            "waveform_analysis.core.plugins.builtin.cpu.hit_finder is deprecated; "
            "use waveform_analysis.core.plugins.builtin.cpu (or .peak_finding) instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        super().__init__(*args, **kwargs)
