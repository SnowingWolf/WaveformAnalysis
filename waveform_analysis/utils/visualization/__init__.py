"""Compatibility alias for :mod:`waveform_analysis.visualization`."""

import sys

from waveform_analysis._module_aliases import alias_module, register_module_aliases

_CANONICAL = "waveform_analysis.visualization"
register_module_aliases(
    {
        f"{__name__}.{child}": f"{_CANONICAL}.{child}"
        for child in (
            "_s1_s2_candidates",
            "lineage_visualizer",
            "pdf_export",
            "statistical_plots",
            "waveform_visualizer",
        )
    }
)
sys.modules[__name__] = alias_module(__name__, _CANONICAL)
