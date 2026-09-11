"""Compatibility alias for :mod:`waveform_analysis.acquisition.daq`."""

import sys

from waveform_analysis._module_aliases import alias_module, register_module_aliases

_CANONICAL = "waveform_analysis.acquisition.daq"
register_module_aliases(
    {f"{__name__}.{leaf}": f"{_CANONICAL}.{leaf}" for leaf in ("daq", "daq_analyzer", "daq_run")}
)
sys.modules[__name__] = alias_module(__name__, _CANONICAL)
