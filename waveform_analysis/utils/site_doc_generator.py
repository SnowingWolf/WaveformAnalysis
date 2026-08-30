"""Compatibility alias for :mod:`waveform_analysis.documentation.site_doc_generator`."""

from importlib import import_module
import sys

_implementation = import_module("waveform_analysis.documentation.site_doc_generator")
sys.modules[__name__] = _implementation
