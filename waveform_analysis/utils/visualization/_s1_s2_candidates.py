"""Compatibility alias for :mod:`waveform_analysis.visualization._s1_s2_candidates`."""

import sys

from waveform_analysis._module_aliases import alias_module

sys.modules[__name__] = alias_module(__name__, "waveform_analysis.visualization._s1_s2_candidates")
