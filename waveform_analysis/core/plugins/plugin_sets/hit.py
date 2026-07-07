# DOC: docs/plugins/guides/PLUGIN_SET_PROFILE_GUIDE.md#plugin-sets
"""
Plugin set: Hit detection and peaklet construction.

Contains the complete pipeline from hit detection through peaklet construction:
- Hit finding and thresholding
- Record masks (asymmetry, detector, veto)
- Hit merging and clustering
- Peaklet construction and features
"""

from waveform_analysis.core.foundation.utils import exporter

export, __all__ = exporter()


@export
def plugins_hit():
    """Return hit and peaklet plugin instances in dependency order."""
    from waveform_analysis.core.plugins.builtin.cpu.peak_finding import HitFinderPlugin
    from waveform_analysis.core.plugins.builtin.cpu.records_asymmetry import (
        RecordsAsymmetryMaskPlugin,
    )
    from waveform_analysis.core.plugins.builtin.cpu.records_channel_role import (
        RecordsDetectorMaskPlugin,
        RecordsVetoMaskPlugin,
    )
    from waveform_analysis.core.plugins.builtin.hit.hit_finder import ThresholdHitPlugin
    from waveform_analysis.core.plugins.builtin.hit.hit_merge import (
        HitMergeClustersPlugin,
        HitMergedComponentsPlugin,
        HitMergePlugin,
    )
    from waveform_analysis.core.plugins.builtin.hit.hit_merged_features import (
        HitMergedFeaturesPlugin,
    )
    from waveform_analysis.core.plugins.builtin.peaks.peaklet_channels import PeakletChannelsPlugin
    from waveform_analysis.core.plugins.builtin.peaks.peaklets import (
        PeakletComponentsPlugin,
        PeakletFeaturesPlugin,
        PeakletPlugin,
        PeakletWaveformPlugin,
        PeakletWaveformPoolPlugin,
    )

    return [
        HitFinderPlugin(),
        RecordsAsymmetryMaskPlugin(),
        RecordsDetectorMaskPlugin(),
        RecordsVetoMaskPlugin(),
        ThresholdHitPlugin(),
        HitMergeClustersPlugin(),
        HitMergePlugin(),
        HitMergedComponentsPlugin(),
        HitMergedFeaturesPlugin(),
        PeakletPlugin(),
        PeakletComponentsPlugin(),
        PeakletWaveformPlugin(),
        PeakletWaveformPoolPlugin(),
        PeakletFeaturesPlugin(),
        PeakletChannelsPlugin(),
    ]
