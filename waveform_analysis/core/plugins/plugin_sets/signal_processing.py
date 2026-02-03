# DOC: docs/features/plugin/PLUGIN_SET_PROFILE_GUIDE.md#plugin-sets
"""
Plugin set: Optional signal-processing extensions.
"""

from waveform_analysis.core.foundation.utils import exporter

export, __all__ = exporter()


@export
def plugins_signal_processing():
    """Return signal-processing plugin instances in dependency order."""
    from waveform_analysis.core.plugins.builtin.cpu.waveform_width import WaveformWidthPlugin
    from waveform_analysis.core.plugins.builtin.cpu.s1_s2_classifier import S1S2ClassifierPlugin

    return [
        WaveformWidthPlugin(),
        S1S2ClassifierPlugin(),
    ]
