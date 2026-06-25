# DOC: docs/plugins/guides/PLUGIN_SET_PROFILE_GUIDE.md#plugin-sets
"""
Plugin set: Event grouping and pairing.

.. deprecated::
    All plugins in this set are deprecated and will be removed in a future version.
"""

import warnings

from waveform_analysis.core.foundation.utils import exporter

export, __all__ = exporter()


@export
def plugins_event():
    """Return event-level plugin instances in dependency order.

    .. deprecated::
        This plugin set is deprecated. All contained plugins will be removed in a future version:
        - GroupedEventsPlugin: deprecated
        - HitGroupedPlugin: deprecated
        - PairedEventsPlugin: deprecated
    """
    warnings.warn(
        "plugins_event() is deprecated and will be removed in a future version. "
        "All event-level plugins (GroupedEventsPlugin, HitGroupedPlugin, PairedEventsPlugin) "
        "are deprecated.",
        DeprecationWarning,
        stacklevel=2,
    )

    from waveform_analysis.core.plugins.builtin.cpu.event_analysis import (
        GroupedEventsPlugin,
        HitGroupedPlugin,
        PairedEventsPlugin,
    )

    return [
        GroupedEventsPlugin(),  # deprecated
        HitGroupedPlugin(),  # deprecated
        PairedEventsPlugin(),  # deprecated
    ]
