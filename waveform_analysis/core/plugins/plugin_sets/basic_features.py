# DOC: docs/plugins/PLUGIN_SYSTEM_OVERVIEW.md#plugin-sets
"""
Plugin set: Basic feature extraction.
"""

from waveform_analysis.core.foundation.utils import exporter

export, __all__ = exporter()


@export
def plugins_basic_features():
    """Return basic feature plugin instances in dependency order."""
    from waveform_analysis.core.plugins.builtin.basic_features import BasicFeaturesPlugin
    from waveform_analysis.core.plugins.builtin.waveform_width_integral import (
        WaveformWidthIntegralPlugin,
    )

    return [
        BasicFeaturesPlugin(),
        WaveformWidthIntegralPlugin(),
    ]
