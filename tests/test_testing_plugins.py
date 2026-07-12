from __future__ import annotations

import numpy as np

from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu.peak_finding import HitFinderPlugin
from waveform_analysis.core.plugins.builtin.hit.hit_finder import ThresholdHitPlugin
from waveform_analysis.testing import (
    FAKE_CURRENT_PIPELINE_PLUGINS,
    FAKE_PIPELINE_DTYPE,
    FakeHitPlugin,
    FakeHitThresholdPlugin,
    FakePeakletWaveformsPlugin,
    FakeS1S2PairCandidatesPlugin,
    register_fake_current_pipeline,
)


def test_fake_pipeline_declares_current_dependency_shape():
    hit_context = Context()
    hit_context.register(HitFinderPlugin)
    hit_context.set_config(
        {"wave_source": "records", "use_filtered": False},
        plugin_name="hit",
    )
    threshold_context = Context()
    threshold_context.register(ThresholdHitPlugin)
    threshold_context.set_config(
        {
            "wave_source": "records",
            "use_filtered": False,
            "asymmetry_cut_enabled": False,
            "channel_role_cut_enabled": False,
        },
        plugin_name="hit_threshold",
    )

    assert HitFinderPlugin().resolve_depends_on(hit_context) == FakeHitPlugin.depends_on
    assert (
        ThresholdHitPlugin().resolve_depends_on(threshold_context)
        == FakeHitThresholdPlugin.depends_on
    )
    assert FakePeakletWaveformsPlugin.depends_on == [
        "peaklets",
        "peaklet_components",
        "hit_merged",
        "hit_merged_components",
        "hit_threshold",
        "records",
        "wave_pool",
    ]
    assert FakeS1S2PairCandidatesPlugin.depends_on == ["peak_classification", "peaks"]
    assert {plugin.provides for plugin in FAKE_CURRENT_PIPELINE_PLUGINS} == {
        "records",
        "wave_pool",
        "hit",
        "hit_threshold",
        "hit_merged",
        "hit_merged_components",
        "hit_merged_features",
        "peaklet_components",
        "peaklets",
        "peaklet_waveforms",
        "peaklet_waveform_pool",
        "peaklet_features",
        "peaklet_channels",
        "peaks",
        "peak_classification",
        "s1_s2_pair_candidates",
        "s1_s2_pairs",
    }


def test_fake_pipeline_executes_full_modern_chain(tmp_path):
    context = Context(storage_dir=str(tmp_path / "storage"))
    register_fake_current_pipeline(context)

    result = context.get_data("run_001", "s1_s2_pairs")

    assert result.dtype == FAKE_PIPELINE_DTYPE
    np.testing.assert_array_equal(result["id"], np.arange(3))
    assert np.all(result["value"] > 0)
    assert context.get_data("run_001", "hit").shape == (3,)
