"""Canonical alias for the plugin documentation generator implementation."""

from importlib import import_module
import sys

_implementation = import_module("waveform_analysis.documentation.plugin_docs.generator")
sys.modules[__name__] = _implementation
