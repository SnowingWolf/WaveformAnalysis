# DOC: docs/plugins/guides/PLUGIN_SET_PROFILE_GUIDE.md#plugin-sets
"""
Plugin set: Peak construction and classification.

Contains peak-level processing:
- Peak construction from peaklets
- Waveform width computation
- S1/S2 classification
- Peak classification
"""

from waveform_analysis.core.foundation.utils import exporter

export, __all__ = exporter()


@export
def plugins_peaks():
    """Return peak-related plugin instances in dependency order."""
    from waveform_analysis.core.plugins.builtin.cpu.peak_classification import (
        PeakClassificationPlugin,
    )
    from waveform_analysis.core.plugins.builtin.cpu.peaklets import PeaksPlugin
    from waveform_analysis.core.plugins.builtin.cpu.s1_s2_classifier import S1S2ClassifierPlugin
    from waveform_analysis.core.plugins.builtin.cpu.waveform_width import WaveformWidthPlugin

    return [
        PeaksPlugin(),
        WaveformWidthPlugin(),
        S1S2ClassifierPlugin(),
        PeakClassificationPlugin(),
    ]
