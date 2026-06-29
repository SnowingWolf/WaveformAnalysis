# DOC: docs/plugins/guides/PLUGIN_SET_PROFILE_GUIDE.md#plugin-sets
"""
Plugin set: Event grouping and pairing.

Legacy plugins are deprecated. New S1-S2 pairing plugins replace the old event analysis flow.
"""

import warnings

from waveform_analysis.core.foundation.utils import exporter

export, __all__ = exporter()


@export
def plugins_events():
    """Return event-level plugin instances in dependency order.

    New S1-S2 pairing workflow:
    - S1S2PairCandidatesPlugin: Generate all physically allowed S1-S2 pairing candidates
    - S1S2PairSelectionPlugin: Select best pairs from candidates

    .. deprecated::
        Legacy plugins (GroupedEventsPlugin, HitGroupedPlugin, PairedEventsPlugin)
        are deprecated and will be removed in a future version.
    """
    from waveform_analysis.core.plugins.builtin.cpu.s1_s2_pair_candidates import (
        S1S2PairCandidatesPlugin,
    )
    from waveform_analysis.core.plugins.builtin.cpu.s1_s2_pair_selection import (
        S1S2PairSelectionPlugin,
    )

    plugins = [
        # New S1-S2 pairing workflow (2-stage)
        S1S2PairCandidatesPlugin(),  # Stage 1: Generate candidates
        S1S2PairSelectionPlugin(),  # Stage 2: Select best pairs
    ]

    # Legacy deprecated plugins (kept for backward compatibility)
    try:
        from waveform_analysis.core.plugins.builtin.cpu.event_analysis import (
            GroupedEventsPlugin,
            HitGroupedPlugin,
            PairedEventsPlugin,
        )

        warnings.warn(
            "plugins_events() now includes deprecated legacy plugins "
            "(GroupedEventsPlugin, HitGroupedPlugin, PairedEventsPlugin). "
            "These will be removed in a future version.",
            DeprecationWarning,
            stacklevel=2,
        )

        plugins.extend(
            [
                GroupedEventsPlugin(),  # deprecated
                HitGroupedPlugin(),  # deprecated
                PairedEventsPlugin(),  # deprecated
            ]
        )
    except ImportError:
        pass  # Legacy plugins already removed

    return plugins
