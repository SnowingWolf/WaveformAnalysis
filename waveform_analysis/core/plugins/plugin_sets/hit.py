# DOC: docs/plugins/guides/PLUGIN_SET_PROFILE_GUIDE.md#plugin-sets
"""
Plugin set: Hit detection and merging.

Contains hit detection and hit-level processing only:
- Hit finding and thresholding
- Record masks (asymmetry, detector, veto)
- Hit merging and clustering
- Hit_merged features

Peaklet construction lives in the ``peaks`` plugin set.
"""

from waveform_analysis.core.foundation.utils import exporter

export, __all__ = exporter()


@export
def plugins_hit():
    """Return hit plugin instances in dependency order."""
    from waveform_analysis.core.plugins.builtin.hit import HitFinderPlugin
    from waveform_analysis.core.plugins.builtin.hit_merge_clusters import (
        HitMergeClustersPlugin,
    )
    from waveform_analysis.core.plugins.builtin.hit_merged import HitMergePlugin
    from waveform_analysis.core.plugins.builtin.hit_merged_components import (
        HitMergedComponentsPlugin,
    )
    from waveform_analysis.core.plugins.builtin.hit_merged_features import (
        HitMergedFeaturesPlugin,
    )
    from waveform_analysis.core.plugins.builtin.hit_threshold import ThresholdHitPlugin
    from waveform_analysis.core.plugins.builtin.records_asymmetry_mask import (
        RecordsAsymmetryMaskPlugin,
    )
    from waveform_analysis.core.plugins.builtin.records_detector_mask import (
        RecordsDetectorMaskPlugin,
    )
    from waveform_analysis.core.plugins.builtin.records_veto_mask import (
        RecordsVetoMaskPlugin,
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
    ]
