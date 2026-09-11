"""Compatibility alias for :mod:`waveform_analysis.acquisition.formats`."""

import sys

from waveform_analysis._module_aliases import alias_module, register_module_aliases

_CANONICAL = "waveform_analysis.acquisition.formats"
register_module_aliases(
    {
        f"{__name__}.{leaf}": f"{_CANONICAL}.{leaf}"
        for leaf in (
            "adapter",
            "base",
            "directory",
            "generic",
            "registry",
            "v1725",
            "v1725_numba",
            "vx2730",
        )
    }
)
sys.modules[__name__] = alias_module(__name__, _CANONICAL)
