# DOC: docs/features/plugin/PLUGIN_SET_PROFILE_GUIDE.md#plugin-sets
"""
Plugin set: Event grouping and pairing.
"""

from waveform_analysis.core.foundation.utils import exporter

export, __all__ = exporter()


@export
def plugins_events():
    """Return event-level plugin instances in dependency order."""
    from waveform_analysis.core.plugins.builtin.cpu.event_analysis import (
        GroupedEventsPlugin,
        PairedEventsPlugin,
    )

    return [
        GroupedEventsPlugin(),
        PairedEventsPlugin(),
    ]
