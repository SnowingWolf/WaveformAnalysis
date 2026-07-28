# DOC: docs/plugins/guides/PLUGIN_SET_PROFILE_GUIDE.md#plugin-sets
"""
Plugin set: Peaklet construction, peak building and classification.

Contains peaklet-level and peak-level processing:
- Peaklet components, peaklets, waveforms, pool, features, channels
- Peak construction from peaklets
- Waveform width computation
- S1/S2 classification (deprecated)
- Peak classification

.. note::
    S1S2ClassifierPlugin is deprecated. For S1-S2 analysis, use the modern
    pairing workflow in plugins_events: S1S2PairCandidatesPlugin and
    S1S2PairSelectionPlugin.
"""

import warnings

from waveform_analysis.core.foundation.utils import exporter

export, __all__ = exporter()


@export
def plugins_peaks():
    """Return peak and peaklet plugin instances in dependency order.

    .. deprecated::
        S1S2ClassifierPlugin is deprecated and will be removed in a future version.
        Use S1S2PairCandidatesPlugin and S1S2PairSelectionPlugin instead.
    """
    from waveform_analysis.core.plugins.builtin.cpu.peak_classification import (
        PeakClassificationPlugin,
    )
    from waveform_analysis.core.plugins.builtin.cpu.s1_s2_classifier import S1S2ClassifierPlugin
    from waveform_analysis.core.plugins.builtin.cpu.waveform_width import WaveformWidthPlugin
    from waveform_analysis.core.plugins.builtin.peaks.peaklet_channels import PeakletChannelsPlugin
    from waveform_analysis.core.plugins.builtin.peaks.peaklets import (
        PeakletComponentsPlugin,
        PeakletFeaturesPlugin,
        PeakletPlugin,
        PeakletWaveformPlugin,
        PeakletWaveformPoolPlugin,
        PeaksPlugin,
    )

    warnings.warn(
        "plugins_peaks() includes S1S2ClassifierPlugin which is deprecated. "
        "For S1-S2 analysis, use S1S2PairCandidatesPlugin and S1S2PairSelectionPlugin instead.",
        DeprecationWarning,
        stacklevel=2,
    )

    return [
        PeakletComponentsPlugin(),
        PeakletPlugin(),
        PeakletWaveformPlugin(),
        PeakletWaveformPoolPlugin(),
        PeakletFeaturesPlugin(),
        PeakletChannelsPlugin(),
        PeaksPlugin(),
        WaveformWidthPlugin(),
        S1S2ClassifierPlugin(),  # deprecated
        PeakClassificationPlugin(),
    ]
