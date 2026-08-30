"""Compatibility alias for :mod:`waveform_analysis.documentation.doc_coverage`."""

from importlib import import_module
import sys

_implementation = import_module("waveform_analysis.documentation.doc_coverage")
sys.modules[__name__] = _implementation
