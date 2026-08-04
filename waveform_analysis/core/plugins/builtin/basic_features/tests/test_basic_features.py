"""Tests for BasicFeaturesPlugin (basic_features bundle)."""

import numpy as np

from waveform_analysis.core.plugins.builtin.basic_features import (
    BASIC_FEATURES_DTYPE,
    BasicFeaturesPlugin,
)
from waveform_analysis.core.plugins.builtin.cpu.basic_features import (
    BASIC_FEATURES_DTYPE as ShimDT,
)
from waveform_analysis.core.plugins.builtin.cpu.basic_features import (
    BasicFeaturesPlugin as ShimPlugin,
)


def test_old_path_is_new_bundle():
    assert ShimPlugin is BasicFeaturesPlugin
    assert ShimDT is BASIC_FEATURES_DTYPE


def test_plugin_metadata():
    plugin = BasicFeaturesPlugin()
    assert plugin.provides == "basic_features"
    assert plugin.version == "4.1.0"
    assert plugin.output_dtype is BASIC_FEATURES_DTYPE


def test_dtype_fields():
    names = BASIC_FEATURES_DTYPE.names
    assert "height" in names
    assert "area" in names
    assert "amp" in names
    assert "max_abs_diff" in names
    assert "record_id" in names
    assert BASIC_FEATURES_DTYPE["height"] == np.float32
