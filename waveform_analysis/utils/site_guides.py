"""Compatibility alias for :mod:`waveform_analysis.documentation.site_guides`."""

from importlib import import_module
import sys

_implementation = import_module("waveform_analysis.documentation.site_guides")
sys.modules[__name__] = _implementation
