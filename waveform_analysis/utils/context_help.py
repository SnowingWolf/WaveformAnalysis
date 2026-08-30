"""Compatibility alias for :mod:`waveform_analysis.documentation.context_help`."""

from importlib import import_module
import sys

_implementation = import_module("waveform_analysis.documentation.context_help")
sys.modules[__name__] = _implementation
