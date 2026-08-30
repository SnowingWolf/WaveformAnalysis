"""Compatibility alias for :mod:`waveform_analysis.documentation.plugin_doc_generator`."""

from importlib import import_module
import sys

_implementation = import_module("waveform_analysis.documentation.plugin_doc_generator")
sys.modules[__name__] = _implementation
