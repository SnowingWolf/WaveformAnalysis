# DOC: docs/features/plugin/PLUGIN_SET_PROFILE_GUIDE.md#plugin-sets
"""
Plugin set: Optional signal-processing extensions.
"""

import warnings

from waveform_analysis.core.foundation.utils import exporter

export, __all__ = exporter()


@export
def plugins_signal_processing():
    """Deprecated alias of plugins_peaks()."""
    warnings.warn(
        "plugins_signal_processing is deprecated; use plugins_peaks or "
        "get_plugin_set('peaks') instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    from waveform_analysis.core.plugins.plugin_sets.peaks import plugins_peaks

    return plugins_peaks()
