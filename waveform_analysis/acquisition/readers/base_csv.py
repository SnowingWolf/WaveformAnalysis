"""Compatibility alias for :mod:`waveform_analysis.acquisition.file_io.csv_pandas`."""

import sys

from waveform_analysis._module_aliases import alias_module

sys.modules[__name__] = alias_module(__name__, "waveform_analysis.acquisition.file_io.csv_pandas")
