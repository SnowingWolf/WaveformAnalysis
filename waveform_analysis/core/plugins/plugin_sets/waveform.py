# -*- coding: utf-8 -*-
# DOC: docs/features/plugin/PLUGIN_SET_PROFILE_GUIDE.md#plugin-sets
"""
Plugin set: Waveform processing.

Contains waveform extraction and optional filtering plugins.
"""

from waveform_analysis.core.foundation.utils import exporter

export, __all__ = exporter()


@export
def plugins_waveform():
    """Return waveform processing plugin instances in dependency order."""
    from waveform_analysis.core.plugins.builtin.cpu.waveforms import WaveformsPlugin
    from waveform_analysis.core.plugins.builtin.cpu.filtering import FilteredWaveformsPlugin

    return [
        WaveformsPlugin(),
        FilteredWaveformsPlugin(),
    ]
