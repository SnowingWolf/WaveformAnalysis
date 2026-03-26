# DOC: docs/plugins/guides/PLUGIN_SET_PROFILE_GUIDE.md#plugin-sets
"""
Plugin set: Optional peaks-related extensions.
"""

from waveform_analysis.core.foundation.utils import exporter

export, __all__ = exporter()


@export
def plugins_peaks():
    """Return peaks-related plugin instances in dependency order."""
    from waveform_analysis.core.plugins.builtin.cpu.hit_finder import ThresholdHitPlugin
    from waveform_analysis.core.plugins.builtin.cpu.peak_finding import HitFinderPlugin
    from waveform_analysis.core.plugins.builtin.cpu.s1_s2_classifier import S1S2ClassifierPlugin
    from waveform_analysis.core.plugins.builtin.cpu.waveform_width import WaveformWidthPlugin

    return [
        HitFinderPlugin(),
        ThresholdHitPlugin(),
        WaveformWidthPlugin(),
        S1S2ClassifierPlugin(),
    ]
