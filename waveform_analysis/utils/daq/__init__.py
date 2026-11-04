"""Compatibility alias for :mod:`waveform_analysis.acquisition.daq`."""

import sys

from waveform_analysis._module_aliases import alias_module, register_module_aliases

register_module_aliases(
    {
        f"{__name__}.{legacy}": f"waveform_analysis.acquisition.runs.{canonical}"
        for legacy, canonical in {
            "daq": "adapters",
            "daq_analyzer": "analyzer",
            "daq_run": "run",
            "discovery": "discovery",
        }.items()
    }
)
register_module_aliases(
    {
        f"{__name__}.{leaf}": f"waveform_analysis.acquisition.daq.{leaf}"
        for leaf in ("models", "service", "presentation")
    }
)
sys.modules[__name__] = alias_module(__name__, "waveform_analysis.acquisition.daq")
