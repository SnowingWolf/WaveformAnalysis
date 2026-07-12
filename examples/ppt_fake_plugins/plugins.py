"""Empty plugins for drawing a simplified pipeline in presentations."""

from __future__ import annotations

from typing import Any

import numpy as np

from waveform_analysis.core.plugins.core.base import Plugin

EMPTY_DTYPE = np.dtype([])


class _PPTPlugin(Plugin):
    """Return an empty array; only the declared dependency is meaningful."""

    output_dtype = EMPTY_DTYPE
    version = "0.0.0"
    save_when = "never"

    def compute(self, context: Any, run_id: str, **_kwargs: Any) -> np.ndarray:
        return np.zeros(0, dtype=self.output_dtype)


class PPTRecordsPlugin(_PPTPlugin):
    provides = "records"
    depends_on = []


class PPTHitPlugin(_PPTPlugin):
    provides = "hit"
    depends_on = ["records"]


class PPTHitMergedPlugin(_PPTPlugin):
    provides = "hit_merged"
    depends_on = ["hit"]


class PPTPeaksPlugin(_PPTPlugin):
    provides = "peaks"
    depends_on = ["hit_merged"]


class PPTS1S2Plugin(_PPTPlugin):
    provides = "s1_s2"
    depends_on = ["peaks"]


PPT_FAKE_PLUGINS = (
    PPTRecordsPlugin,
    PPTHitPlugin,
    PPTHitMergedPlugin,
    PPTPeaksPlugin,
    PPTS1S2Plugin,
)

__all__ = [
    "EMPTY_DTYPE",
    "PPT_FAKE_PLUGINS",
    "PPTHitMergedPlugin",
    "PPTHitPlugin",
    "PPTPeaksPlugin",
    "PPTRecordsPlugin",
    "PPTS1S2Plugin",
]
