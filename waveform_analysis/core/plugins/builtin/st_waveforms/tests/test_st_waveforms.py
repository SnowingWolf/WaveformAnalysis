"""Tests for WaveformsPlugin (st_waveforms bundle)."""

import numpy as np

from waveform_analysis.core.plugins.builtin.cpu.waveforms import (
    WaveformsPlugin as ShimPlugin,
)
from waveform_analysis.core.plugins.builtin.cpu.waveforms import (
    WaveformStruct,
    WaveformStructConfig,
)
from waveform_analysis.core.plugins.builtin.st_waveforms import (
    WaveformsPlugin,
)
from waveform_analysis.core.plugins.builtin.st_waveforms import (
    WaveformStructConfig as BundleConfig,
)


def test_old_path_is_new_bundle():
    """旧 shim 路径与新 bundle 路径指向同一类对象。"""
    from waveform_analysis.core.plugins.builtin.cpu.waveforms import (
        WaveformsPlugin as FromShim,
    )

    assert ShimPlugin is WaveformsPlugin
    assert FromShim is WaveformsPlugin


def test_plugin_metadata():
    plugin = WaveformsPlugin()
    assert plugin.provides == "st_waveforms"
    assert plugin.version == "0.10.0"
    assert plugin.output_dtype is not None
    assert "wave" in plugin.output_dtype.names


def test_waveform_struct_config_bundle_identity():
    assert WaveformStructConfig is BundleConfig
    config = WaveformStructConfig.default_vx2730()
    assert config.get_wave_length() > 0
    assert config.get_record_dtype() is not None


def test_waveform_struct_empty():
    struct = WaveformStruct([])
    out = struct.structure_waveforms()
    assert isinstance(out, np.ndarray)
    assert len(out) == 0
