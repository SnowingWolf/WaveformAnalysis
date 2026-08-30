"""Compatibility alias for :mod:`waveform_analysis.documentation.doc_links`."""

from importlib import import_module
import sys

_implementation = import_module("waveform_analysis.documentation.doc_links")
sys.modules[__name__] = _implementation
