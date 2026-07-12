"""Small plugins that reproduce the current analysis dependency graph.

These plugins are intended for dependency, lineage, and teaching examples. They
do not reproduce the physics algorithms or output contracts of production
plugins.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from waveform_analysis.core.plugins.core.base import Plugin

FAKE_PIPELINE_DTYPE = np.dtype([("id", np.int64), ("value", np.float64)])


class _FakePipelinePlugin(Plugin):
    """Propagate a tiny payload while explicitly loading every dependency."""

    output_dtype = FAKE_PIPELINE_DTYPE
    version = "0.1.0"
    save_when = "never"

    def compute(self, context: Any, run_id: str, **_kwargs: Any) -> np.ndarray:
        inputs = [context.get_data(run_id, name) for name in self.depends_on]
        if not inputs:
            result = np.zeros(3, dtype=self.output_dtype)
            result["id"] = np.arange(3)
            result["value"] = 1.0
            return result

        result = np.zeros(len(inputs[0]), dtype=self.output_dtype)
        result["id"] = inputs[0]["id"]
        for payload in inputs:
            result["value"] += payload["value"]
        return result


class FakeRecordsPlugin(_FakePipelinePlugin):
    """Root of the fake records-backed pipeline."""

    provides = "records"
    depends_on = []


class FakeWavePoolPlugin(_FakePipelinePlugin):
    """Minimal companion source used by records-backed waveform consumers."""

    provides = "wave_pool"
    depends_on = []


class FakeHitPlugin(_FakePipelinePlugin):
    """Legacy-style hit view retained as an independent teaching branch."""

    provides = "hit"
    depends_on = ["records", "wave_pool"]


class FakeHitThresholdPlugin(_FakePipelinePlugin):
    provides = "hit_threshold"
    depends_on = ["records", "wave_pool"]


class FakeHitMergedPlugin(_FakePipelinePlugin):
    provides = "hit_merged"
    depends_on = ["hit_threshold"]


class FakeHitMergedComponentsPlugin(_FakePipelinePlugin):
    provides = "hit_merged_components"
    depends_on = ["hit_merged", "hit_threshold"]


class FakeHitMergedFeaturesPlugin(_FakePipelinePlugin):
    provides = "hit_merged_features"
    depends_on = [
        "hit_merged",
        "hit_merged_components",
        "hit_threshold",
        "records",
        "wave_pool",
    ]


class FakePeakletComponentsPlugin(_FakePipelinePlugin):
    provides = "peaklet_components"
    depends_on = ["hit_merged"]


class FakePeakletsPlugin(_FakePipelinePlugin):
    provides = "peaklets"
    depends_on = ["hit_merged", "peaklet_components"]


class FakePeakletWaveformsPlugin(_FakePipelinePlugin):
    provides = "peaklet_waveforms"
    depends_on = [
        "peaklets",
        "peaklet_components",
        "hit_merged",
        "hit_merged_components",
        "hit_threshold",
        "records",
        "wave_pool",
    ]


class FakePeakletWaveformPoolPlugin(_FakePipelinePlugin):
    provides = "peaklet_waveform_pool"
    depends_on = ["peaklet_waveforms"]


class FakePeakletFeaturesPlugin(_FakePipelinePlugin):
    provides = "peaklet_features"
    depends_on = ["peaklet_waveforms", "peaklet_waveform_pool", "peaklets"]


class FakePeakletChannelsPlugin(_FakePipelinePlugin):
    provides = "peaklet_channels"
    depends_on = [
        "peaklets",
        "peaklet_components",
        "hit_merged_features",
        "peaklet_features",
    ]


class FakePeaksPlugin(_FakePipelinePlugin):
    provides = "peaks"
    depends_on = ["peaklets", "peaklet_features", "peaklet_channels"]


class FakePeakClassificationPlugin(_FakePipelinePlugin):
    provides = "peak_classification"
    depends_on = ["peaks"]


class FakeS1S2PairCandidatesPlugin(_FakePipelinePlugin):
    provides = "s1_s2_pair_candidates"
    depends_on = ["peak_classification", "peaks"]


class FakeS1S2PairsPlugin(_FakePipelinePlugin):
    provides = "s1_s2_pairs"
    depends_on = ["s1_s2_pair_candidates"]


FAKE_CURRENT_PIPELINE_PLUGINS = (
    FakeRecordsPlugin,
    FakeWavePoolPlugin,
    FakeHitPlugin,
    FakeHitThresholdPlugin,
    FakeHitMergedPlugin,
    FakeHitMergedComponentsPlugin,
    FakeHitMergedFeaturesPlugin,
    FakePeakletComponentsPlugin,
    FakePeakletsPlugin,
    FakePeakletWaveformsPlugin,
    FakePeakletWaveformPoolPlugin,
    FakePeakletFeaturesPlugin,
    FakePeakletChannelsPlugin,
    FakePeaksPlugin,
    FakePeakClassificationPlugin,
    FakeS1S2PairCandidatesPlugin,
    FakeS1S2PairsPlugin,
)


def register_fake_current_pipeline(context: Any) -> None:
    """Register the fake modern records-to-S1/S2-pairs pipeline."""

    context.register(*FAKE_CURRENT_PIPELINE_PLUGINS)


__all__ = [
    "FAKE_CURRENT_PIPELINE_PLUGINS",
    "FAKE_PIPELINE_DTYPE",
    "FakeHitMergedComponentsPlugin",
    "FakeHitMergedFeaturesPlugin",
    "FakeHitMergedPlugin",
    "FakeHitPlugin",
    "FakeHitThresholdPlugin",
    "FakePeakClassificationPlugin",
    "FakePeakletChannelsPlugin",
    "FakePeakletComponentsPlugin",
    "FakePeakletFeaturesPlugin",
    "FakePeakletWaveformPoolPlugin",
    "FakePeakletWaveformsPlugin",
    "FakePeakletsPlugin",
    "FakePeaksPlugin",
    "FakeRecordsPlugin",
    "FakeS1S2PairCandidatesPlugin",
    "FakeS1S2PairsPlugin",
    "FakeWavePoolPlugin",
    "register_fake_current_pipeline",
]
