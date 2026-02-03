# DOC: docs/features/plugin/PLUGIN_SET_PROFILE_GUIDE.md#plugin-sets
"""
Plugin set: Basic feature extraction.
"""

from waveform_analysis.core.foundation.utils import exporter

export, __all__ = exporter()


@export
def plugins_basic_features():
    """Return basic feature plugin instances in dependency order."""
    from waveform_analysis.core.plugins.builtin.cpu.basic_features import BasicFeaturesPlugin
    from waveform_analysis.core.plugins.builtin.cpu.hit_finder import HitFinderPlugin
    from waveform_analysis.core.plugins.builtin.cpu.peak_finding import SignalPeaksPlugin
    from waveform_analysis.core.plugins.builtin.cpu.waveform_width_integral import (
        WaveformWidthIntegralPlugin,
    )

    return [
        HitFinderPlugin(),
        BasicFeaturesPlugin(),
        SignalPeaksPlugin(),
        WaveformWidthIntegralPlugin(),
    ]
