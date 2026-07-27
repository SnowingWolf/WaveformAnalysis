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
    - PositionReconstructionPlugin: Reconstruct 3D position from S1-S2 pairs (v0.0.0)
    - EventPlugin: Complete event reconstruction (v0.0.0)

    .. deprecated::
        Legacy plugins (GroupedEventsPlugin, HitGroupedPlugin, PairedEventsPlugin)
        are deprecated and will be removed in a future version.
        GroupedEventsPlugin and PairedEventsPlugin have been moved to the
        ``tabular`` plugin set because they produce DataFrame (tabular) outputs.
    """
    from waveform_analysis.core.plugins.builtin.cpu.event import EventPlugin
    from waveform_analysis.core.plugins.builtin.cpu.position_reconstruction import (
        PositionReconstructionPlugin,
    )
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
        # Position and event reconstruction (v0.0.0)
        PositionReconstructionPlugin(),  # Stage 3: Position reconstruction
        EventPlugin(),  # Stage 4: Complete event reconstruction
    ]

    # Legacy deprecated plugins (kept for backward compatibility)
    # NOTE: GroupedEventsPlugin and PairedEventsPlugin have been moved to the
    # ``tabular`` plugin set (they emit DataFrame tabular outputs).
    try:
        from waveform_analysis.core.plugins.builtin.hit.hit_grouped import HitGroupedPlugin

        warnings.warn(
            "plugins_events() now includes deprecated legacy plugins "
            "(HitGroupedPlugin). These will be removed in a future version.",
            DeprecationWarning,
            stacklevel=2,
        )

        plugins.extend(
            [
                HitGroupedPlugin(),  # deprecated
            ]
        )
    except ImportError:
        pass  # Legacy plugins already removed

    return plugins
