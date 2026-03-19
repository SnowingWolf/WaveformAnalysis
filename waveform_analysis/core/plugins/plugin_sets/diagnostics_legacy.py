# DOC: docs/plugins/guides/PLUGIN_SET_PROFILE_GUIDE.md#plugin-sets
"""
Plugin set: Diagnostics and legacy plugin shims.
"""

from waveform_analysis.core.foundation.utils import exporter

export, __all__ = exporter()


@export
def plugins_diagnostics_legacy():
    """Return diagnostics and legacy plugin instances."""
    from waveform_analysis.core.plugins.builtin.cpu.cache_analysis import CacheAnalysisPlugin
    from waveform_analysis.core.plugins.builtin.cpu.events import EventsPlugin

    return [
        CacheAnalysisPlugin(),
        EventsPlugin(),
    ]
